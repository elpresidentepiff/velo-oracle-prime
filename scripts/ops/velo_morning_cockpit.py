"""
VÉLØ Morning Cockpit — Daily operator brief
Queries the 5 truth tables and sends one Telegram message.

Run: python scripts/velo_morning_cockpit.py
Schedule: 15:00 UTC daily (08:00 PDT) — after sigma closes at 21:30 UTC previous night.

5 questions answered in order:
  Q1. Did Service B run and finish?
  Q2. What was picked last scoring run?
  Q3. What did sigma close?
  Q4. What did Playbook G learn?
  Q5. How did doctrine move?
"""
import os
import sys
import json
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

_SB_URL = os.getenv("SUPABASE_URL", "")
_SB_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY")
           or os.getenv("SUPABASE_SERVICE_KEY")
           or os.getenv("SUPABASE_KEY", ""))
_TG_TOKEN = os.getenv("TELEGRAM_VOX_TOKEN", "")
_TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "7516350009")


def _sb():
    from supabase import create_client
    return create_client(_SB_URL, _SB_KEY)


def _tg(text: str):
    if not _TG_TOKEN:
        print("[cockpit] TELEGRAM_VOX_TOKEN not set — printing only")
        print(text)
        return
    url = f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": _TG_CHAT,
        "text": text,
        "parse_mode": "Markdown",
    }, timeout=15)


def _window():
    """48-hour lookback window (ISO string)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    return cutoff.isoformat()


def q1_service_b(db) -> str:
    """Did Service B run and finish?"""
    try:
        rows = (db.table("pipeline_runs")
                .select("service_name, status, source_date, races_processed, runners_processed, started_at, finished_at, error_message")
                .eq("service_name", "velo-prime-scoring")
                .gte("started_at", _window())
                .order("started_at", desc=True)
                .limit(3)
                .execute()).data
        if not rows:
            return "SERVICE B: NO RUN in last 48h ⚠"
        r = rows[0]
        status = r.get("status", "?").upper()
        date = r.get("source_date", "?")
        races = r.get("races_processed") or "?"
        runners = r.get("runners_processed") or "?"
        err = f" | ⚠ {r['error_message'][:60]}" if r.get("error_message") else ""
        icon = "✓" if status == "COMPLETED" else ("⚠" if status == "PARTIAL" else "✗")
        return f"SERVICE B: {icon} {status} | {date} | {races} races | {runners} runners{err}"
    except Exception as e:
        return f"SERVICE B: query failed ({e})"


def q2_verdicts(db) -> str:
    """What was picked last scoring run?"""
    try:
        rows = (db.table("velo_verdicts")
                .select("race_id, decision_tier, confidence_level, velo_prime_prob, generated_at")
                .gte("generated_at", _window())
                .order("generated_at", desc=True)
                .limit(50)
                .execute()).data
        if not rows:
            return "VERDICTS: none in last 48h"
        n = len(rows)
        tier_counts = {}
        for r in rows:
            t = r.get("decision_tier") or "?"
            tier_counts[t] = tier_counts.get(t, 0) + 1
        tier_str = " | ".join(f"{k}:{v}" for k, v in sorted(tier_counts.items()))
        top = rows[0]
        return (f"VERDICTS: {n} scored (48h)\n"
                f"  Tiers: {tier_str}\n"
                f"  Latest top: prob={top.get('velo_prime_prob', '?')} "
                f"tier={top.get('decision_tier', '?')} conf={top.get('confidence_level', '?')}")
    except Exception as e:
        return f"VERDICTS: query failed ({e})"


def q3_sigma(db) -> str:
    """What did sigma close?"""
    try:
        rows = (db.table("sigma_audits")
                .select("race_id, date, outcome, miss_reason, decision_tier, created_at")
                .gte("created_at", _window())
                .order("created_at", desc=True)
                .limit(60)
                .execute()).data
        if not rows:
            return "SIGMA: no reviews in last 48h"
        outcomes = {}
        miss_reasons: dict = {}
        for r in rows:
            o = r.get("outcome") or "?"
            outcomes[o] = outcomes.get(o, 0) + 1
            if o == "MISS" and r.get("miss_reason"):
                mr = r["miss_reason"]
                miss_reasons[mr] = miss_reasons.get(mr, 0) + 1

        wins   = outcomes.get("WIN", 0)
        placed = outcomes.get("PLACED", 0)
        misses = outcomes.get("MISS", 0)
        total  = sum(outcomes.values())
        top_miss = max(miss_reasons, key=miss_reasons.get) if miss_reasons else "none"
        dates_seen = sorted({r.get("date","?") for r in rows if r.get("date")})
        date_range = f"{dates_seen[-1]}" if dates_seen else "?"
        return (f"SIGMA: {total} reviewed (48h) | Latest: {date_range}\n"
                f"  {wins}W / {placed}PL / {misses}M  SR={100*wins//total if total else 0}%\n"
                f"  Top miss: {top_miss}")
    except Exception as e:
        return f"SIGMA: query failed ({e})"


def q4_playbook_g(db) -> str:
    """What did Playbook G learn?"""
    try:
        rows = (db.table("learned_patterns")
                .select("pattern_name, occurrences, confidence_level, last_observed, conditions")
                .gte("last_observed", _window())
                .neq("pattern_name", "SENTIENT_STATE_BACKUP")
                .order("last_observed", desc=True)
                .limit(20)
                .execute()).data
        n = len(rows)
        names = [r["pattern_name"][:30] for r in rows[:3]]
        sample = ", ".join(names) if names else "none"
        return (f"PLAYBOOK G: {n} patterns updated (48h)\n"
                f"  Sample: {sample}")
    except Exception as e:
        return f"PLAYBOOK G: query failed ({e})"


def q5_doctrine(db) -> str:
    """How did doctrine move?"""
    try:
        rows = (db.table("learned_patterns")
                .select("conditions, confidence_level, last_observed, occurrences")
                .eq("pattern_name", "SENTIENT_STATE_BACKUP")
                .limit(1)
                .execute()).data
        if not rows:
            return "DOCTRINE: SENTIENT_STATE_BACKUP not found ⚠"
        r = rows[0]
        state = r.get("conditions") or {}
        if isinstance(state, str):
            try:
                state = json.loads(state)
            except Exception:
                pass
        races = state.get("total_races_observed", "?")
        appetite = state.get("appetite_state", {})
        aggression = appetite.get("aggression_level", "?")
        last = r.get("last_observed", "?")
        if isinstance(last, str):
            last = last[:16]
        return (f"DOCTRINE STATE:\n"
                f"  Races observed: {races}\n"
                f"  Aggression: {aggression}\n"
                f"  Last updated: {last}")
    except Exception as e:
        return f"DOCTRINE: query failed ({e})"


def run():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    header = f"*VÉLØ MORNING BRIEF — {today} (48h window)*\n{'━' * 40}"

    if not _SB_URL or not _SB_KEY:
        _tg(f"{header}\nSUPABASE CREDENTIALS MISSING — cannot run cockpit")
        return

    db = _sb()

    sections = [
        q1_service_b(db),
        q2_verdicts(db),
        q3_sigma(db),
        q4_playbook_g(db),
        q5_doctrine(db),
    ]

    body = "\n\n".join(sections)
    message = f"{header}\n\n{body}\n\n{'━' * 40}"

    print(message)
    _tg(message)


if __name__ == "__main__":
    run()
