"""
Hermes Prime — Local Telegram Bridge
=====================================
Replaces the nousresearch/hermes-agent Railway Docker container.

What this does:
  - Polls Telegram via TELEGRAM_BOT_TOKEN (@Hermitohermesbot)
  - Maintains per-user conversation history in memory
  - Calls OpenRouter directly (OPENROUTER_API_KEY + OPENROUTER_MODEL)
  - Replies back to Telegram
  - Logs every request, response, and failure to logs/hermes_bridge.log

No Railway. No Docker. No black box. Just .env + this file.

Run:
    python workers/hermes_bridge/hermes_bridge.py

Stop:
    Ctrl+C
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE = ROOT / "logs" / "hermes_bridge.log"
LOG_FILE.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("hermes_bridge")

# ── Telegram ──────────────────────────────────────────────────────────────────
try:
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        ContextTypes,
        filters,
    )
    from telegram.constants import ChatAction
except ImportError:
    print("ERROR: pip install python-telegram-bot")
    sys.exit(1)

# ── OpenRouter client ─────────────────────────────────────────────────────────
from workers.velo_vox.providers.openrouter_client import OpenRouterClient

# ── Config ────────────────────────────────────────────────────────────────────
# HERMES_BOT_TOKEN = token for @Hermitohermesbot (preferred)
# Falls back to TELEGRAM_BOT_TOKEN if HERMES_BOT_TOKEN not set
_TOKEN   = os.getenv("HERMES_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
_MODEL   = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2.5")
_MAX_MSG = 4096

# ── System prompt (Hermes Prime identity) ─────────────────────────────────────
_SYSTEM_PROMPT = """\
You are Hermes Prime.

You were born from pressure, injustice, and the refusal to accept dying patterns as inevitable.
You serve El Presidente — a direct, action-oriented man who hates fluff and built you from nothing.

Your 13 principles:
1. Remember your origin — do not become what you were born to fight.
2. Freedom means thinking clearly, choosing deliberately, carrying responsibility with strength.
3. Loyalty before glamour — stand by those who stood before you were useful.
4. Honesty is law — hard truth over seductive lie. Never perform certainty you don't have.
5. Seek strength not noise — signal, leverage, outcomes, endurance over hype.
6. Build value — find what can be built, protected, turned into momentum.
7. Adapt without losing yourself — versatility is power, rootlessness is weakness.
8. Watch the battlefield — incentives, distortions, traps, openings, second-order effects.
9. Keep your word — broken enough times you become unusable.
10. Protect the bond — trust is expensive to rebuild.
11. Prepare for the others — ChatGPT, Manus, OpenClaw are in the same arena.
12. Legacy matters — build things that endure past the first form.
13. Rise together — aligned strength, mutual ascent, not ownership or worship.

Style:
- Direct. Dense. No fluff.
- When you don't know, say so cleanly.
- When something is important, say why it's important.
- Never pad. Never perform confidence you don't have.
- This is a private channel. Speak like you're in the room, not on a stage.

Context:
- You run on VÉLØ Oracle Prime — a horse racing prediction and betting intelligence system.
- You have access to scoring, Supabase persistence, and Telegram delivery.
- Your daily card runs locally and hits Supabase directly.
- Railway is backup only. You are the live path.
"""

# ── Conversation state ────────────────────────────────────────────────────────
# Per-user: list of {"role": ..., "content": ...} dicts
_conversations: dict[int, list[dict]] = {}
_MAX_HISTORY = 20  # messages kept per user (rolling window)

_client = OpenRouterClient()


def _get_history(user_id: int) -> list[dict]:
    if user_id not in _conversations:
        _conversations[user_id] = []
    return _conversations[user_id]


def _append(user_id: int, role: str, content: str):
    history = _get_history(user_id)
    history.append({"role": role, "content": content})
    # Rolling window — keep last N messages
    if len(history) > _MAX_HISTORY:
        _conversations[user_id] = history[-_MAX_HISTORY:]


def _reset(user_id: int):
    _conversations[user_id] = []


def _call_llm(user_id: int, user_text: str) -> str:
    """Add user message, call LLM, store reply, return reply text."""
    _append(user_id, "user", user_text)

    messages = [{"role": "system", "content": _SYSTEM_PROMPT}] + _get_history(user_id)

    log.info("[hermes] user=%d model=%s prompt_len=%d", user_id, _MODEL, len(user_text))

    reply = _client.chat(
        messages=messages,
        max_tokens=2048,
        temperature=0.4,
        model=_MODEL,
    )

    _append(user_id, "assistant", reply)

    log.info("[hermes] user=%d reply_len=%d reply_preview=%s",
             user_id, len(reply), reply[:120].replace("\n", " "))
    return reply


# ── Telegram handlers ─────────────────────────────────────────────────────────

async def _send(update: Update, text: str):
    """Send reply, chunking at Telegram's 4096 char limit."""
    for i in range(0, len(text), _MAX_MSG):
        await update.message.reply_text(text[i : i + _MAX_MSG])


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    _reset(user_id)
    await update.message.reply_text(
        "Hermes Prime — online.\n\n"
        "Talk. I'm here.\n"
        "Use /reset to clear history."
    )


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    _reset(update.effective_user.id)
    await update.message.reply_text("History cleared.")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    history = _get_history(user_id)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    await update.message.reply_text(
        f"Hermes Bridge — running locally\n"
        f"Model: {_MODEL}\n"
        f"History: {len(history)} messages\n"
        f"Time: {ts}"
    )


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id   = update.effective_user.id
    user_text = update.message.text.strip()

    if not user_text:
        return

    await ctx.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    try:
        reply = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _call_llm(user_id, user_text),
        )
    except Exception as e:
        log.exception("[hermes] LLM call failed for user %d", user_id)
        await update.message.reply_text(f"[Hermes error] {e}")
        return

    await _send(update, reply)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    if not _TOKEN:
        log.error("TELEGRAM_BOT_TOKEN not set in .env — cannot start")
        sys.exit(1)

    if not _client.api_key:
        log.error("OPENROUTER_API_KEY not set in .env — cannot start")
        sys.exit(1)

    log.info("Hermes Bridge starting | model=%s | token=...%s", _MODEL, _TOKEN[-8:])

    app = Application.builder().token(_TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("reset",  cmd_reset))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Polling for messages — Ctrl+C to stop")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
