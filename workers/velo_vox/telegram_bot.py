"""
VÉLØ VOX Telegram Bot — @Velovoxbot

A full conversational intelligence agent. Not a command bot.
Talk to it like you talk to Claude — ask about races, horses, trainers, form.
It fetches what it needs, reasons over it, and answers you.

Install:
    pip install python-telegram-bot

Run:
    python workers/velo_vox/telegram_bot.py

Auto-send:
    Daily card fires at 09:00 UTC via JobQueue.
    Use /daily [venue] to trigger immediately.
"""
import os
import sys
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from telegram import Update
    from telegram.ext import (
        Application, CommandHandler, MessageHandler,
        ContextTypes, filters,
    )
    from telegram.constants import ChatAction
except ImportError:
    print("ERROR: pip install python-telegram-bot")
    sys.exit(1)

from workers.velo_vox.agent_loop import VoxAgent
from workers.velo_vox.daily_sender import send_daily_card

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("velo_vox_bot")

_TOKEN = os.getenv("TELEGRAM_VOX_TOKEN", "")
_MAX_MSG = 4096

# One agent instance per user — maintains conversation history
_agents: dict[int, VoxAgent] = {}


def _get_agent(user_id: int) -> VoxAgent:
    if user_id not in _agents:
        _agents[user_id] = VoxAgent(user_id=user_id)
    return _agents[user_id]


async def _send(update: Update, text: str):
    """Send message, splitting at Telegram's 4096 char limit."""
    for i in range(0, len(text), _MAX_MSG):
        await update.message.reply_text(
            text[i:i+_MAX_MSG],
            parse_mode="Markdown",
        )


# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    agent = _get_agent(update.effective_user.id)
    agent.reset()
    await update.message.reply_text(
        "*VÉLØ VOX — Intelligence Online*\n\n"
        "Talk to me. Ask about today's races, a horse, a trainer, or tell me what you're looking at.\n\n"
        "I have access to:\n"
        "• Today's live racecards (Racing API)\n"
        "• RPD-C intelligence tags — 253,000 historical runs tagged\n"
        "• Trainer and horse profiles\n"
        "• Full VÉLØ briefing generation\n\n"
        "Just ask. No commands needed.",
        parse_mode="Markdown",
    )


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    agent = _get_agent(update.effective_user.id)
    agent.reset()
    await update.message.reply_text("Conversation cleared. Fresh start.")


async def cmd_races(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Quick shortcut — but now routes through the agent."""
    venue = " ".join(ctx.args) if ctx.args else ""
    query = f"List today's races{' at ' + venue if venue else ''}."
    await handle_message_text(update, ctx, override_text=query)


async def cmd_brief(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /brief <race_id>")
        return
    race_id = ctx.args[0].strip()
    await handle_message_text(update, ctx, override_text=f"Give me the full briefing for race {race_id}.")


async def cmd_card(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /card <venue>")
        return
    venue = " ".join(ctx.args)
    await handle_message_text(update, ctx, override_text=f"Give me the full card briefing for {venue} today.")


async def cmd_daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Manually trigger today's full card send — same as the 09:00 auto-send."""
    venue = " ".join(ctx.args) if ctx.args else ""
    chat_id = str(update.effective_chat.id)
    await update.message.reply_text(
        f"🏇 *Generating today's card briefing{' for ' + venue if venue else ''}…*\n"
        "_This may take a couple of minutes — generating full briefings for each race._",
        parse_mode="Markdown",
    )
    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: send_daily_card(venue_filter=venue, dry_run=False, chat_id=chat_id),
        )
    except Exception as e:
        log.exception("daily card error")
        await update.message.reply_text(f"⚠️ Error generating card: {e}")


async def _scheduled_morning_cockpit(ctx: ContextTypes.DEFAULT_TYPE):
    """Called by JobQueue every day at 15:00 UTC — morning operator brief."""
    log.info("[scheduler] Morning cockpit firing")
    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: __import__("scripts.velo_morning_cockpit", fromlist=["run"]).run(),
        )
    except Exception as e:
        log.exception(f"[scheduler] Morning cockpit failed: {e}")


async def _scheduled_daily_send(ctx: ContextTypes.DEFAULT_TYPE):
    """Called by JobQueue every day at 09:00 UTC."""
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "7516350009")
    log.info(f"[scheduler] Daily card firing → chat {chat_id}")
    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: send_daily_card(dry_run=False, chat_id=chat_id),
        )
    except Exception as e:
        log.exception(f"[scheduler] Daily card failed: {e}")


async def handle_message_text(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    override_text: str = "",
):
    user_id   = update.effective_user.id
    user_text = override_text or update.message.text

    agent = _get_agent(user_id)

    # Show typing indicator
    await ctx.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    log.info(f"User {user_id}: {user_text[:80]}")

    # Status callback — sends interim "thinking" messages for long operations
    async def status_update(msg: str):
        try:
            await update.message.reply_text(msg, parse_mode="Markdown")
            await ctx.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.TYPING,
            )
        except Exception:
            pass

    try:
        # Run the agent (synchronous — Telegram handler is async but agent.chat is sync)
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: agent.chat(user_text),
        )
    except Exception as e:
        log.exception(f"Agent error for user {user_id}")
        await update.message.reply_text(f"VOX error: {e}")
        return

    await _send(update, response)


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await handle_message_text(update, ctx)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not _TOKEN:
        print("ERROR: TELEGRAM_VOX_TOKEN not set in .env")
        sys.exit(1)

    app = Application.builder().token(_TOKEN).build()

    # Commands (all route through agent now)
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("reset",  cmd_reset))
    app.add_handler(CommandHandler("races",  cmd_races))
    app.add_handler(CommandHandler("brief",  cmd_brief))
    app.add_handler(CommandHandler("card",   cmd_card))
    app.add_handler(CommandHandler("daily",  cmd_daily))

    # Natural language — the main interface
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Schedule daily card at 09:00 UTC every day
    # Schedule morning cockpit at 15:00 UTC (08:00 PDT) every day
    if app.job_queue:
        import datetime
        app.job_queue.run_daily(
            _scheduled_daily_send,
            time=datetime.time(hour=9, minute=0, tzinfo=datetime.timezone.utc),
            name="daily_card",
        )
        app.job_queue.run_daily(
            _scheduled_morning_cockpit,
            time=datetime.time(hour=15, minute=0, tzinfo=datetime.timezone.utc),
            name="morning_cockpit",
        )
        log.info("Daily card scheduled at 09:00 UTC | Morning cockpit at 15:00 UTC")
    else:
        log.warning("JobQueue not available — install python-telegram-bot[job-queue] for auto-send")

    log.info("VÉLØ VOX Agent starting — polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
