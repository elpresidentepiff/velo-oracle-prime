"""
VELO Post-Run Persistence Check
================================
Run after every race-day workflow completion.
Compares verdicts generated (local JSON) vs rows written to Supabase.
Exits non-zero and sends Telegram FAIL alert if counts do not match.

Usage:
    python scripts/post_run_persistence_check.py
    python scripts/post_run_persistence_check.py --date 2026-03-17
"""
import sys
import os
import json
import argparse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Load .env
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def tg_alert(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        body = json.dumps({"chat_id": chat_id, "text": text[:4096]}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def get_local_count(date_tag: str) -> tuple[int, str]:
    """Return (count, path) from local JSON file for the date.
    Checks PRIME output first (velo_prime_verdicts_*), then orchestrator output.
    """
    for name in (f"velo_prime_verdicts_{date_tag}.json", f"velo_verdicts_{date_tag}.json"):
        json_path = ROOT / "data" / name
        if json_path.exists():
            try:
                data = json.loads(json_path.read_text())
                return len(data), str(json_path)
            except Exception:
                return 0, str(json_path)
    # Neither file exists — return the PRIME path as the expected location
    return 0, str(ROOT / "data" / f"velo_prime_verdicts_{date_tag}.json")


def get_supabase_count(date_str: str) -> tuple[int, str]:
    """Return (count, error_or_ok) from Supabase velo_verdicts for the date."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return -1, "Supabase credentials missing"
    try:
        query_url = (
            f"{url}/rest/v1/velo_verdicts"
            f"?select=count"
            f"&generated_at=gte.{date_str}T00:00:00"
            f"&generated_at=lt.{date_str}T23:59:59"
        )
        req = urllib.request.Request(
            query_url,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Prefer": "count=exact",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            content_range = r.headers.get("Content-Range", "")
            # Content-Range: 0-0/N or */N
            if "/" in content_range:
                count = int(content_range.split("/")[1])
                return count, "ok"
            return -1, f"unexpected Content-Range: {content_range}"
    except Exception as e:
        return -1, str(e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    date_tag = date_str.replace("-", "_")

    print(f"\nVELO POST-RUN PERSISTENCE CHECK — {date_str}\n")

    # 1. Count local verdicts
    local_count, json_path = get_local_count(date_tag)
    print(f"  Local JSON:  {local_count} verdicts  ({json_path})")

    # 2. Count Supabase rows
    sb_count, sb_status = get_supabase_count(date_str)
    if sb_count == -1:
        print(f"  Supabase:    ERROR — {sb_status}")
    else:
        print(f"  Supabase:    {sb_count} rows in velo_verdicts for {date_str}")

    print()

    # 3. Compare
    if local_count == 0:
        print("FAIL  No local verdicts found — has the race-day script been run?")
        tg_alert(
            f"VELO PERSISTENCE FAIL — {date_str}\n"
            f"No local verdicts found.\n"
            f"Has run_todays_races.py been run?"
        )
        sys.exit(1)

    if sb_count == -1:
        print(f"FAIL  Cannot reach Supabase: {sb_status}")
        tg_alert(
            f"VELO PERSISTENCE FAIL — {date_str}\n"
            f"Supabase unreachable: {sb_status}\n"
            f"Local verdicts: {local_count}  Supabase: UNKNOWN"
        )
        sys.exit(1)

    if sb_count == local_count:
        print(f"PASS  expected={local_count}  actual={sb_count}  delta=0")
        tg_alert(
            f"VELO PERSISTENCE PASS — {date_str}\n"
            f"Races generated: {local_count}\n"
            f"Rows in Supabase: {sb_count}\n"
            f"Table: velo_verdicts\n"
            f"Status: COMPLETE"
        )
        sys.exit(0)
    else:
        deficit = local_count - sb_count
        print(f"FAIL  expected={local_count}  actual={sb_count}  deficit={deficit}")
        tg_alert(
            f"VELO PERSISTENCE FAIL — {date_str}\n"
            f"Races generated: {local_count}\n"
            f"Rows in Supabase: {sb_count}\n"
            f"DEFICIT: {deficit} races NOT persisted\n"
            f"Table: velo_verdicts\n"
            f"Action required: investigate persist_race_predictions() failures in logs"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
