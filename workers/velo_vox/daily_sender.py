"""
VÉLØ VOX — Daily Card Sender

Fetches today's feature meeting, generates full-card briefing in Carlisle template
format, splits into Telegram-safe chunks, and sends to the owner's chat.

Usage:
    python workers/velo_vox/daily_sender.py                    # auto-pick feature meeting
    python workers/velo_vox/daily_sender.py --venue Carlisle   # specific venue
    python workers/velo_vox/daily_sender.py --dry-run          # print, don't send

Schedule (cron-friendly):
    python workers/velo_vox/daily_sender.py --hour 09:00

Called by Railway cron or APScheduler in telegram_bot.py background task.
"""
import argparse
import os
import sys
import time
import textwrap
import requests
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from workers.velo_vox.velo_vox_agent import generate_briefing, save_briefing

# ── Config ─────────────────────────────────────────────────────────────────────

_RAPI_USER = os.getenv("RACING_API_USERNAME", "")
_RAPI_PASS = os.getenv("RACING_API_PASSWORD", "")
_RAPI_BASE = os.getenv("RACING_API_BASE_URL", "https://api.theracingapi.com/v1")

# VOX bot sends to owner's personal chat
_TG_TOKEN   = os.getenv("TELEGRAM_VOX_TOKEN", "")
_TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7516350009")   # owner personal chat

# Telegram message limit is 4096 chars; keep chunks smaller for readability
_TG_CHUNK = 3800


# ── Racing API helpers ──────────────────────────────────────────────────────────

def _rapi(endpoint: str, params: dict = None) -> dict | list:
    r = requests.get(
        f"{_RAPI_BASE}/{endpoint.lstrip('/')}",
        auth=(_RAPI_USER, _RAPI_PASS),
        params=params or {},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _get_todays_races() -> list[dict]:
    data = _rapi("racecards")
    return data if isinstance(data, list) else data.get("racecards", [])


# ── Feature meeting selection ───────────────────────────────────────────────────

# Priority venue list — pick first that appears on today's card
_FEATURE_PRIORITY = [
    "Cheltenham", "Ascot", "Newmarket", "Goodwood", "Sandown", "Kempton",
    "Doncaster", "York", "Haydock", "Newbury", "Leicester", "Nottingham",
    "Carlisle", "Catterick", "Musselburgh", "Ayr", "Chester",
    "Lingfield", "Wolverhampton", "Southwell",
]


def pick_feature_venue(races: list[dict], preferred: str = "") -> str:
    """Return the course name for today's feature meeting."""
    courses_today = {r.get("course", "") for r in races}

    if preferred:
        for c in courses_today:
            if preferred.lower() in c.lower():
                return c
        print(f"[sender] Preferred venue '{preferred}' not found today — falling back.")

    for pv in _FEATURE_PRIORITY:
        for c in courses_today:
            if pv.lower() in c.lower():
                return c

    # Fallback: venue with most races
    from collections import Counter
    ctr = Counter(r.get("course", "") for r in races)
    return ctr.most_common(1)[0][0] if ctr else ""


# ── Telegram sender ─────────────────────────────────────────────────────────────

def _tg_send(text: str, chat_id: str = _TG_CHAT_ID, parse_mode: str = "Markdown") -> None:
    """Send a single Telegram message. Raises on HTTP error."""
    r = requests.post(
        f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    if not r.ok:
        # Retry once with plain text if Markdown parse fails
        r2 = requests.post(
            f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=20,
        )
        r2.raise_for_status()


def _send_in_chunks(text: str, chat_id: str = _TG_CHAT_ID) -> int:
    """Split long text into chunks and send sequentially. Returns chunk count."""
    chunks = []
    while text:
        if len(text) <= _TG_CHUNK:
            chunks.append(text)
            break
        # Break at a newline boundary within the limit
        cut = text.rfind("\n", 0, _TG_CHUNK)
        if cut == -1:
            cut = _TG_CHUNK
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")

    for i, chunk in enumerate(chunks):
        _tg_send(chunk, chat_id=chat_id)
        if i < len(chunks) - 1:
            time.sleep(0.4)   # stay under Telegram rate limit

    return len(chunks)


# ── Main sender ─────────────────────────────────────────────────────────────────

def send_daily_card(
    venue_filter: str = "",
    dry_run: bool = False,
    chat_id: str = _TG_CHAT_ID,
) -> None:
    """
    Full pipeline:
      1. Fetch today's racecards
      2. Pick feature venue
      3. Generate per-race briefings (VOX Carlisle template)
      4. Assemble card header + all briefings
      5. Send to Telegram in chunks
    """
    today = str(date.today())
    print(f"[sender] Daily card — {today}")

    races = _get_todays_races()
    if not races:
        msg = f"⚠️ *VÉLØ VOX* — No races found for {today}. Racing API returned empty card."
        print(f"[sender] {msg}")
        if not dry_run:
            _tg_send(msg, chat_id=chat_id)
        return

    venue = pick_feature_venue(races, preferred=venue_filter)
    venue_races = [r for r in races if r.get("course", "") == venue]

    print(f"[sender] Feature venue: {venue} ({len(venue_races)} races)")

    # Card header
    header = (
        f"🏇 *VÉLØ ORACLE PRIME — DAILY INTELLIGENCE BRIEFING*\n"
        f"📅 {today} | 📍 {venue} | {len(venue_races)}-Race Card\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_Classification: Full-Spectrum Strategic Analysis_\n"
    )

    if dry_run:
        print(header)
        print(f"\n[sender] DRY RUN — would generate briefings for:")
        for r in venue_races:
            print(f"  {r.get('off_time','')} | {r.get('race_id','')} | {r.get('race_name','')}")
        return

    # Send header first
    _tg_send(header, chat_id=chat_id)
    time.sleep(0.5)

    errors = []
    for race in venue_races:
        race_id = race.get("race_id") or race.get("id", "")
        if not race_id:
            continue

        off_time   = race.get("off_time", "")
        race_name  = race.get("race_name", "")[:60]
        num_runners = len(race.get("runners", []))

        # Race divider header
        divider = (
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 *{off_time}* — {race_name}\n"
            f"_{num_runners} runners_\n"
        )
        _tg_send(divider, chat_id=chat_id)
        time.sleep(0.3)

        print(f"  [sender] Generating briefing for {race_id} ({off_time} {race_name})")
        try:
            briefing = generate_briefing(str(race_id), dry_run=False)

            # Save locally too
            filename = f"{today}_{venue.lower().replace(' ', '_')}_{off_time.replace(':', '')}.md"
            save_briefing(briefing, filename)

            # Send briefing in chunks
            n_chunks = _send_in_chunks(briefing, chat_id=chat_id)
            print(f"    → Sent ({n_chunks} chunk{'s' if n_chunks > 1 else ''})")
            time.sleep(0.5)

        except Exception as e:
            err_msg = f"⚠️ *VOX error* for {off_time} {race_name[:40]}: `{e}`"
            errors.append(err_msg)
            _tg_send(err_msg, chat_id=chat_id)
            print(f"    → ERROR: {e}")
            time.sleep(0.3)

    # Footer
    footer = (
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ *{venue} card complete* — {len(venue_races) - len(errors)}/{len(venue_races)} races briefed\n"
        f"_Information only — independent decision required._"
    )
    _tg_send(footer, chat_id=chat_id)
    print(f"[sender] Done. {len(errors)} error(s).")


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VÉLØ VOX Daily Card Sender")
    parser.add_argument("--venue",   default="", help="Preferred venue (partial match)")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without calling LLM or Telegram")
    parser.add_argument("--chat-id", default=_TG_CHAT_ID, help="Override Telegram chat ID")
    args = parser.parse_args()

    send_daily_card(
        venue_filter=args.venue,
        dry_run=args.dry_run,
        chat_id=args.chat_id,
    )


if __name__ == "__main__":
    main()
