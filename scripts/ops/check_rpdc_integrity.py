#!/usr/bin/env python3
"""
RPDC Integrity Loop (L3) — READ-ONLY checker
=============================================
Proves RPDC is genuine from attach to Supabase, per race, per date.

Compares three layers:
  1. runner_release_candidates (RPDC build output, Supabase)
  2. local backup verdicts data/velo_prime_verdicts_{date}.json
     (rpdc_lookup_status + attached fields — what scoring actually saw)
  3. velo_verdicts rows in Supabase (what persistence actually wrote)

Statuses:
  RPDC_OK           — local attach and Supabase rows agree
  RPDC_LOCAL_ONLY   — attached locally, Supabase row has no RPDC at all
  RPDC_PERSIST_GAP  — attached locally, Supabase rpdc fields empty/default
  RPDC_CORRUPTED    — Supabase rpdc fields contain foreign data
                      (PDF_PLOT / PLOT: / intent-signal hijack signature)
  RPDC_UNKNOWN      — cannot determine (missing artifacts or query failure)

Usage:
    PYTHONPATH=. python scripts/ops/check_rpdc_integrity.py --date YYYY-MM-DD

Outputs:
    data/current/rpdc_integrity_latest.json
    data/reports/rpdc_integrity_{date}.md

Hard constraints: GET-only Supabase access; no writes outside its two
output files; no scoring imports; cannot repair anything (the historical
repair tool is separate and operator-gated).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Hijack signature (fda78d4 era): PDF plot/intent data in RPDC columns.
_FOREIGN_TAG_MARKERS = ("PDF_PLOT", "PLOT:")
_GENUINE_TAGS = {
    "MARK_READY", "BELOW_LAST_WIN_MARK", "MARK_NEAR", "CYCLE_RUN_1", "CYCLE_RUN_2",
    "CYCLE_RUN_3", "FRESH_RETURN", "LONG_ABSENCE", "STABLE_WARM", "COURSE_RETURN",
    "DISTANCE_RETURN", "WIN_STREAK", "PLACE_FORM", "CASH_WINDOW", "FORM_REVERSAL",
}


def _load_env() -> dict:
    env: dict[str, str] = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _sb_get(env: dict, path: str) -> list | None:
    url = env.get("SUPABASE_URL") or (
        f"https://{env['SUPABASE_PROJECT_ID']}.supabase.co" if env.get("SUPABASE_PROJECT_ID") else ""
    )
    key = env.get("SUPABASE_SERVICE_KEY") or env.get("SUPABASE_KEY") or ""
    if not url or not key:
        return None
    req = urllib.request.Request(
        f"{url.rstrip('/')}/rest/v1/{path}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _classify_row(local_top: dict, sb_row: dict | None) -> str:
    local_attached = local_top.get("rpdc_lookup_status") == "attached"
    if sb_row is None:
        return "RPDC_LOCAL_ONLY" if local_attached else "RPDC_UNKNOWN"

    sb_tags = sb_row.get("rpdc_tags") or []
    sb_primary = sb_row.get("rpdc_primary_tag")

    # Foreign data in RPDC columns = corruption, regardless of local state.
    if sb_primary == "PDF_PLOT" or any(
        any(m in str(t) for m in _FOREIGN_TAG_MARKERS) for t in sb_tags
    ):
        return "RPDC_CORRUPTED"
    if sb_tags and any(str(t) not in _GENUINE_TAGS for t in sb_tags):
        return "RPDC_CORRUPTED"

    if not local_attached:
        # Nothing to persist; empty Supabase fields are correct.
        return "RPDC_OK" if not sb_tags and sb_primary is None else "RPDC_UNKNOWN"

    # Local attached — Supabase must agree field-by-field.
    if not sb_tags and sb_primary is None and not sb_row.get("rpdc_tag_count"):
        return "RPDC_PERSIST_GAP"
    if (
        sb_primary == local_top.get("rpdc_primary_tag")
        and list(sb_tags) == list(local_top.get("rpdc_tags") or [])
        and float(sb_row.get("rpdc_release_score") or 0) == float(local_top.get("rpdc_release_score") or 0)
    ):
        return "RPDC_OK"
    return "RPDC_CORRUPTED"


def check_date(date_str: str) -> dict:
    date_und = date_str.replace("-", "_")
    result: dict = {
        "date": date_str,
        "generated_at": datetime.now(UTC).isoformat(),
        "read_only_confirmed": True,
        "races": [],
        "counts": {},
        "status": "RPDC_UNKNOWN",
    }

    backup = ROOT / "data" / f"velo_prime_verdicts_{date_und}.json"
    if not backup.exists():
        result["detail"] = f"no local backup at {backup.name}"
        return result
    try:
        races = json.loads(backup.read_text())
        races = races if isinstance(races, list) else races.get("races", [])
    except Exception as e:
        result["detail"] = f"local backup unreadable: {e}"
        return result

    env = _load_env()
    # race_id membership, not a generated_at window -- generated_at is WRITE
    # time and returns nothing for any day scored outside its own calendar date.
    # See docs/current/ONE_TRUTH.md, generated_at write-date-vs-race-date class.
    sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None
    from src.velo.verdict_loader import race_id_filter
    day_filter = race_id_filter(date_str, ROOT)
    if day_filter is None:
        result["status"] = "UNVERIFIED_NO_RACECARD_CACHE"
        result.setdefault("gaps", []).append(
            f"RACE_ID_SET_UNKNOWN: no racecard cache for {date_str} -- refusing to "
            "report RPDC counts from a generated_at window."
        )
        return result
    sb_rows = _sb_get(
        env,
        f"velo_verdicts?select=race_id,rpdc_primary_tag,rpdc_tags,rpdc_tag_count,"
        f"rpdc_release_score,rpdc_cash_window_flag&{day_filter}&limit=200",
    )
    sb_by_race = {r["race_id"]: r for r in (sb_rows or [])}
    sb_available = sb_rows is not None

    statuses: dict[str, int] = {}
    local_attached_count = 0
    for race in races:
        top = race.get("top") or race.get("top_pick") or {}
        rid = str(race.get("race_id", ""))
        if top.get("rpdc_lookup_status") == "attached":
            local_attached_count += 1
        st = _classify_row(top, sb_by_race.get(rid)) if sb_available else "RPDC_UNKNOWN"
        statuses[st] = statuses.get(st, 0) + 1
        result["races"].append(
            {
                "race_id": rid,
                "status": st,
                "local": {
                    "lookup_status": top.get("rpdc_lookup_status"),
                    "primary_tag": top.get("rpdc_primary_tag"),
                    "tag_count": top.get("rpdc_tag_count"),
                },
                "supabase": {
                    "primary_tag": (sb_by_race.get(rid) or {}).get("rpdc_primary_tag"),
                    "tag_count": (sb_by_race.get(rid) or {}).get("rpdc_tag_count"),
                },
            }
        )

    result["counts"] = {
        "races_local": len(races),
        "local_attached": local_attached_count,
        "supabase_rows": len(sb_by_race),
        "by_status": statuses,
    }

    # Date-level attach check: candidates existed but scoring attached nothing
    # anywhere — a silent attach failure (e.g. race-ID mismatch on bypass days).
    # Chain integrity cannot be affirmed; the consistent-empty rows are NOT "OK".
    candidates = _sb_get(env, f"runner_release_candidates?select=id&run_date=eq.{date_str}&limit=1")
    candidates_exist = bool(candidates)

    if not sb_available:
        result["status"] = "RPDC_UNKNOWN"
        result["detail"] = "Supabase unreachable or credentials missing"
    elif local_attached_count == 0 and candidates_exist and races:
        result["status"] = "RPDC_UNKNOWN"
        result["detail"] = (
            "ATTACH_FAILURE_SUSPECTED: runner_release_candidates rows exist for the "
            "date but every race attached no_data at scoring time (race-ID mismatch?)"
        )
    elif statuses.get("RPDC_CORRUPTED"):
        result["status"] = "RPDC_CORRUPTED"
    elif statuses.get("RPDC_PERSIST_GAP"):
        result["status"] = "RPDC_PERSIST_GAP"
    elif statuses.get("RPDC_LOCAL_ONLY"):
        result["status"] = "RPDC_LOCAL_ONLY"
    elif statuses.get("RPDC_UNKNOWN"):
        result["status"] = "RPDC_UNKNOWN"
    else:
        result["status"] = "RPDC_OK"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    result = check_date(args.date)

    out = ROOT / "data/current/rpdc_integrity_latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))

    c = result.get("counts", {})
    lines = [
        f"# RPDC Integrity — {args.date}",
        "",
        f"**Status:** {result['status']} · generated {result['generated_at']} · READ-ONLY",
        "",
        f"- Races (local backup): {c.get('races_local')}",
        f"- Locally attached: {c.get('local_attached')}",
        f"- Supabase rows: {c.get('supabase_rows')}",
        f"- Per-status: {json.dumps(c.get('by_status', {}))}",
        f"- Detail: {result.get('detail', '—')}",
        "",
        "Statuses: RPDC_OK / RPDC_LOCAL_ONLY / RPDC_PERSIST_GAP / RPDC_CORRUPTED / RPDC_UNKNOWN.",
        "Repair path: operator-gated historical repair tool (dry-run first). This checker cannot write.",
    ]
    reports = ROOT / "data/reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / f"rpdc_integrity_{args.date}.md").write_text("\n".join(lines))

    print(f"RPDC integrity [{args.date}]: {result['status']}")
    print(f"  counts: {json.dumps(c.get('by_status', {}))}")
    print(f"  -> {out}")
    return 0 if result["status"] == "RPDC_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
