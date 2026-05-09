"""
audit_railway_supabase_run_status.py

Determines whether Railway scored for a given race date.
Three distinct states:
  deployed  = code pushed to main and deployed on Railway
  scored    = verdict rows exist in Supabase velo_verdicts
  hydrated  = data/velo_prime_verdicts_YYYY_MM_DD.json written locally

Usage: python scripts/audit_railway_supabase_run_status.py --date YYYY-MM-DD
"""
import argparse
import json
import os
import subprocess
import urllib.request
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT / ".env")

SB_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
HEADERS = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Accept": "application/json"}


def _get(path: str, params: dict | None = None) -> list:
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _count(path: str, params: dict | None = None) -> int:
    url = f"{SB_URL}/rest/v1/{path}"
    p = dict(params or {})
    p["select"] = "id"
    url += "?" + urllib.parse.urlencode(p)
    headers = dict(HEADERS)
    headers["Prefer"] = "count=exact"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        ct = r.headers.get("Content-Range", "")
        total = ct.split("/")[-1] if "/" in ct else "?"
        return int(total) if total.isdigit() else len(json.loads(r.read()))


def local_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="Race date YYYY-MM-DD")
    args = ap.parse_args()

    target = args.date
    d = date.fromisoformat(target)
    next_d = d + timedelta(days=1)

    print(f"\n{'='*60}")
    print(f"Railway/Supabase Run Status Audit — {target}")
    print(f"{'='*60}\n")

    # 1. Latest verdict overall
    latest_rows = _get("velo_verdicts", {
        "select": "generated_at,engine_version,git_commit_sha,environment",
        "order": "generated_at.desc",
        "limit": "5",
    })
    latest_ts = latest_rows[0]["generated_at"] if latest_rows else None
    latest_sha = latest_rows[0].get("git_commit_sha") if latest_rows else None
    latest_env = latest_rows[0].get("environment") if latest_rows else None
    latest_ver = latest_rows[0].get("engine_version") if latest_rows else None

    print(f"Latest verdict in DB:  {latest_ts}")
    print(f"Latest engine_version: {latest_ver}")
    print(f"Latest git_commit_sha: {latest_sha}")
    print(f"Latest environment:    {latest_env}")

    local_sha = local_head()
    sha_match = (latest_sha or "")[:7] == local_sha[:7] if latest_sha else False
    print(f"Local HEAD:            {local_sha[:7]}")
    print(f"SHA match:             {'YES' if sha_match else 'NO / UNKNOWN'}\n")

    # 2. Verdict count for target date — UK window (03:00Z to next 03:00Z)
    uk_start = f"{target}T03:00:00Z"
    uk_end = f"{next_d.isoformat()}T03:00:00Z"
    utc_start = f"{target}T00:00:00Z"
    utc_end = f"{next_d.isoformat()}T00:00:00Z"

    url_uk = (f"{SB_URL}/rest/v1/velo_verdicts?select=id"
              f"&generated_at=gte.{uk_start}&generated_at=lt.{uk_end}")
    req = urllib.request.Request(url_uk, headers={**HEADERS, "Prefer": "count=exact"})
    with urllib.request.urlopen(req, timeout=20) as r:
        ct = r.headers.get("Content-Range", "0/0")
        verdicts_uk = int(ct.split("/")[-1]) if "/" in ct and ct.split("/")[-1].isdigit() else 0

    url_utc = (f"{SB_URL}/rest/v1/velo_verdicts?select=id"
               f"&generated_at=gte.{utc_start}&generated_at=lt.{utc_end}")
    req = urllib.request.Request(url_utc, headers={**HEADERS, "Prefer": "count=exact"})
    with urllib.request.urlopen(req, timeout=20) as r:
        ct = r.headers.get("Content-Range", "0/0")
        verdicts_utc = int(ct.split("/")[-1]) if "/" in ct and ct.split("/")[-1].isdigit() else 0

    print(f"Verdict count (UK window {uk_start}–{uk_end}): {verdicts_uk}")
    print(f"Verdict count (UTC day   {utc_start}–{utc_end}): {verdicts_utc}")
    verdicts_found = max(verdicts_uk, verdicts_utc)

    # 3. Races in DB for target date (PK is race_id, not id)
    url_races = f"{SB_URL}/rest/v1/races?select=race_id&date=eq.{target}"
    req = urllib.request.Request(url_races, headers={**HEADERS, "Prefer": "count=exact"})
    with urllib.request.urlopen(req, timeout=20) as r:
        ct = r.headers.get("Content-Range", "0/0")
        races_for_date = int(ct.split("/")[-1]) if "/" in ct and ct.split("/")[-1].isdigit() else 0
        race_rows = json.loads(r.read())
    race_ids = [r["race_id"] for r in race_rows]

    print(f"Races in DB for {target}:   {races_for_date}")

    # 4. If races exist, check how many have verdicts
    verdicts_by_race_id = 0
    if race_ids:
        id_list = ",".join(race_ids[:50])
        url_v = f"{SB_URL}/rest/v1/velo_verdicts?select=race_id&race_id=in.({id_list})"
        req = urllib.request.Request(url_v, headers={**HEADERS, "Prefer": "count=exact"})
        with urllib.request.urlopen(req, timeout=20) as r:
            ct = r.headers.get("Content-Range", "0/0")
            verdicts_by_race_id = int(ct.split("/")[-1]) if "/" in ct and ct.split("/")[-1].isdigit() else 0
        print(f"Verdicts matched by race_id join: {verdicts_by_race_id}")

    # 5. Local file
    local_file = ROOT / "data" / f"velo_prime_verdicts_{target.replace('-', '_')}.json"
    print(f"Local verdict file:    {'EXISTS' if local_file.exists() else 'MISSING'} ({local_file.name})\n")

    # 6. Status classification
    print("─" * 60)
    any_verdicts = max(verdicts_found, verdicts_by_race_id)

    if any_verdicts > 0 and verdicts_found > 0:
        status = "SCORED_AND_SYNC_READY"
    elif any_verdicts > 0 and verdicts_found == 0:
        status = "SCORED_BUT_DATE_FILTER_WRONG"
    elif any_verdicts == 0 and races_for_date > 0:
        if sha_match:
            status = "DEPLOY_ONLY_NOT_SCORED"
        else:
            status = "SCORING_FAILED_NO_VERDICTS"
    elif any_verdicts == 0 and races_for_date == 0:
        status = "DEPLOY_ONLY_NOT_SCORED"
    else:
        status = "UNKNOWN_NEEDS_RAILWAY_LOGS"

    print(f"STATUS: {status}")
    print("─" * 60)

    if status == "SCORED_AND_SYNC_READY":
        print("Run: python scripts/sync_verdicts_from_supabase.py --date", target)
    elif status == "DEPLOY_ONLY_NOT_SCORED":
        print("Railway deployed but scoring cron has not fired yet.")
        print(f"Scoring cron runs at 06:00 UTC. Latest verdict in DB: {latest_ts}")
    elif status == "SCORED_BUT_DATE_FILTER_WRONG":
        print("Verdicts matched via race_id join but not by generated_at window.")
        print("Use sync_verdicts_from_supabase.py — it tries the race_id join path.")
    elif status in ("SCORING_FAILED_NO_VERDICTS", "UNKNOWN_NEEDS_RAILWAY_LOGS"):
        print(f"Latest verdict in DB: {latest_ts}")
        print("Check Railway deployment logs for errors.")
    print()


if __name__ == "__main__":
    main()
