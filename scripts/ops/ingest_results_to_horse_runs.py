"""
ingest_results_to_horse_runs.py
--------------------------------
Reads a results JSON file (data/results_YYYY-MM-DD.json) and upserts all
runner outcomes into racing_horse_runs.

This keeps the RPDC pipeline current. Run daily AFTER run_results_sigma.py.

Usage:
  source venv/bin/activate
  PYTHONPATH=. python scripts/ingest_results_to_horse_runs.py --date YYYY-MM-DD
"""
import argparse
import json
import logging
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

log = logging.getLogger("velo.ingest_horse_runs")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

TODAY = datetime.now(timezone.utc).strftime("%Y_%m_%d")

SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}


def _sb_upsert_batch(rows: list[dict], conflict_col: str = "race_id,horse_id") -> int:
    if not rows or not SB_URL or not SB_KEY:
        return 0
    url = f"{SB_URL}/rest/v1/racing_horse_runs?on_conflict={conflict_col}"
    body = json.dumps(rows).encode()
    headers = {**SB_HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"}
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        urllib.request.urlopen(req, timeout=30)
        return len(rows)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode(errors="replace")[:500]
        log.warning("Batch upsert failed (%d rows): HTTP %s — %s", len(rows), e.code, err_body)
        return 0
    except Exception as e:
        log.warning("Batch upsert failed (%d rows): %s", len(rows), e)
        return 0


def _position_int(pos) -> int | None:
    try:
        return int(pos)
    except (TypeError, ValueError):
        return None


def _to_float(v) -> float | None:
    try:
        f = float(str(v).replace("f", "").strip())
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def _to_int(v) -> int | None:
    try:
        i = int(float(str(v).strip()))
        return i
    except (TypeError, ValueError):
        return None


def _class_int(v) -> int | None:
    if v is None:
        return None
    s = str(v).lower().replace("class", "").strip()
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def ingest_results(date_str: str) -> None:
    date_tag = date_str.replace("-", "_")
    # Canonical path from parse_rp_results_capture.py output
    results_path = ROOT / "data" / "results" / f"rp_results_{date_tag}.json"
    if not results_path.exists():
        # Legacy fallback path
        results_path = ROOT / "data" / f"results_{date_tag}.json"
    if not results_path.exists():
        log.error("Results file not found: %s", results_path)
        return

    with open(results_path) as f:
        data = json.load(f)

    # Support both {"results": [...]} and bare list formats
    if isinstance(data, list):
        races = data
    else:
        races = data.get("results") or []
    log.info("Loaded %d races from %s", len(races), results_path.name)

    rows = []
    for race in races:
        race_id = race.get("race_id", "")
        course = race.get("course", "")
        course_id = race.get("course_id", "")
        region = race.get("region", "")
        race_name = race.get("race_name", "")
        race_type = race.get("type", "")
        distance = race.get("dist", "")
        distance_f = race.get("dist_f")
        going = race.get("going", "")
        race_class = race.get("class")
        pattern = race.get("pattern", "")

        for runner in race.get("runners") or []:
            pos_raw = runner.get("position")
            pos_int = _position_int(pos_raw)
            is_win = pos_int == 1
            is_place = pos_int is not None and pos_int <= 3

            sp_dec = None
            try:
                sp_dec = float(runner.get("sp_dec") or 0) or None
            except (TypeError, ValueError):
                pass

            rows.append({
                "horse_id": runner.get("horse_id", ""),
                "horse": runner.get("horse", ""),
                "race_id": race_id,
                "run_date": date_str,
                "course": course,
                "course_id": str(course_id),
                "region": region,
                "race_name": race_name,
                "race_type": race_type,
                "distance": distance,
                "distance_f": _to_float(distance_f),
                "going": going,
                "race_class": _class_int(race_class),
                "pattern": pattern,
                "position": str(pos_raw) if pos_raw is not None else None,
                "position_int": pos_int,
                # is_win and is_place are GENERATED columns in Supabase
                # (auto-computed from position_int) — do not insert
                "official_rating": _to_int(runner.get("or")),
                "rpr": _to_int(runner.get("rpr")),
                "tsr": _to_int(runner.get("tsr")),
                "sp": runner.get("sp"),
                "sp_dec": sp_dec,
                "btn": _to_float(runner.get("btn")),
                "weight": runner.get("weight"),
                "weight_lbs": _to_int(runner.get("weight_lbs")),
                "headgear": runner.get("headgear", "") or "",
                "jockey_id": runner.get("jockey_id", ""),
                "jockey": runner.get("jockey", ""),
                "trainer_id": runner.get("trainer_id", ""),
                "trainer": runner.get("trainer", ""),
                "owner_id": runner.get("owner_id", ""),
                "owner": runner.get("owner", ""),
                "prize": _to_float(runner.get("prize")),
                "in_running_comment": runner.get("in_running_comment", "") or "",
            })

    # Filter out rows with no horse_id
    rows = [r for r in rows if r.get("horse_id")]

    # Dedupe on the upsert conflict key (race_id, horse_id). Duplicate race
    # entries can reach the results file when a page is captured twice across
    # batch restarts; Postgres rejects intra-batch conflict-key duplicates
    # (error 21000), which silently dropped a whole 200-row batch on 2026-06-10.
    deduped: dict[tuple, dict] = {}
    for r in rows:
        deduped[(r["race_id"], r["horse_id"])] = r
    if len(deduped) != len(rows):
        log.info("Deduped %d duplicate runner rows (duplicate race captures)", len(rows) - len(deduped))
    rows = list(deduped.values())
    log.info("Built %d unique runner rows for upsert", len(rows))

    # Upsert in batches of 200
    written = 0
    failed_batches = 0
    for i in range(0, len(rows), 200):
        batch = rows[i:i + 200]
        n = _sb_upsert_batch(batch)
        if n == 0 and batch:
            failed_batches += 1
        written += n

    log.info("racing_horse_runs: %d rows written for %s", written, date_str)
    print(f"\nINGEST COMPLETE — {date_str}" if not failed_batches else f"\nINGEST INCOMPLETE — {date_str}")
    print(f"  Races: {len(races)}")
    print(f"  Runners written: {written}")
    if failed_batches:
        print(f"  FAILED BATCHES: {failed_batches} — learned history is PARTIAL, do not mark day complete")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="YYYY-MM-DD")
    args = parser.parse_args()
    date_str = args.date or TODAY.replace("_", "-")
    ingest_results(date_str)


if __name__ == "__main__":
    main()
