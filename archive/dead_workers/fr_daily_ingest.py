"""
fr_daily_ingest.py
VÉLØ FR Cold Archive — Daily Ingestion Script

Purpose: Archive FR racecards, runners, results, and odds.
        Cold storage only. No entity enrichment. No active build.
Location: workers/fr_daily_ingest.py
Schedule: 07:00 UTC daily (after UK race day ends)

Rules:
- fr_research schema ONLY. Never writes to public. or velo_* tables.
- Cold archive. No production verdict authority. No doctrine learning.
- Service role key only.
- Idempotent: upsert on race_id + horse_id.
- Lightweight: no trainer/jockey stats, no horse history building.

Usage:
  python -m workers.fr_daily_ingest --date 2026-03-23
  python -m workers.fr_daily_ingest   # defaults to yesterday
"""

import argparse
import logging
import os
from datetime import date, datetime, timedelta, timezone

import requests
from supabase import Client, create_client

log = logging.getLogger("velo.fr_ingest")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SUPABASE_URL: str = os.getenv("SUPABASE_URL")
SUPABASE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
RA_USERNAME: str = os.getenv("RACING_API_USERNAME")
RA_PASSWORD: str = os.getenv("RACING_API_PASSWORD")

if not all([SUPABASE_URL, SUPABASE_KEY, RA_USERNAME, RA_PASSWORD]):
    raise EnvironmentError("Missing env vars")

db: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
SCHEMA = "fr_research"


def upsert_race(race: dict) -> int:
    row = {
        "race_id":        race["race_id"],
        "meeting_date":   race.get("date"),
        "course":         race.get("course"),
        "region":         "FR",
        "off_time":       race.get("off_time"),
        "off_dt":         race.get("off_dt"),
        "race_name":      race.get("race_name"),
        "distance_round": race.get("distance_round"),
        "distance_f":     race.get("distance_f"),
        "pattern":        race.get("pattern"),
        "race_class":     race.get("race_class"),
        "race_type":      race.get("type"),
        "age_band":       race.get("age_band"),
        "prize":          race.get("prize"),
        "field_size":     race.get("field_size"),
        "going":          race.get("going"),
        "surface":        race.get("surface"),
        "weather":        race.get("weather"),
        "is_abandoned":   race.get("is_abandoned", False),
        "race_status":    race.get("race_status"),
    }
    db.table(f"{SCHEMA}.fr_races").upsert(row, on_conflict="race_id").execute()
    return len(race.get("runners", []))


def upsert_runners(race_id: str, runners: list) -> int:
    rows = []
    for r in runners:
        rows.append({
            "race_id":      race_id,
            "horse_id":    r.get("horse_id"),
            "horse_name":  r.get("horse_name"),
            "draw":        r.get("draw"),
            "weight_kg":   r.get("weight_kg") or r.get("weight"),
            "age":         r.get("age"),
            "sex":         r.get("sex"),
            "jockey_id":   r.get("jockey_id"),
            "jockey_name": r.get("jockey_name"),
            "trainer_id":  r.get("trainer_id"),
            "trainer_name":r.get("trainer_name"),
            "odds_open":   _first_odds(r.get("odds")),
            "odds_live":   _last_odds(r.get("odds")),
            "fav_flag":    r.get("fav_flag"),
            "rpr":         r.get("rpr"),
            "ts":          r.get("ts"),
            "or_rating":   r.get("or_rating"),
            "form":        r.get("form"),
            "comment":     r.get("comment"),
        })
    if rows:
        db.table(f"{SCHEMA}.fr_runners").upsert(rows, on_conflict="race_id,horse_id").execute()
    return len(rows)


def upsert_market_snapshots(race_id: str, runners: list, fetched_at: datetime) -> int:
    """Archive odds at ingestion time. Lightweight — no entity enrichment."""
    rows = []
    for r in runners:
        odds_val = _last_odds(r.get("odds"))
        if odds_val:
            rows.append({
                "race_id":       race_id,
                "horse_id":     r.get("horse_id"),
                "snapshot_time": fetched_at.isoformat(),
                "odds":         odds_val,
                "source":       "api",
            })
    if rows:
        db.table(f"{SCHEMA}.fr_market_snapshots").upsert(rows, on_conflict="race_id,horse_id").execute()
    return len(rows)


def upsert_results(race_id: str, results: list) -> int:
    rows = []
    for r in results:
        rows.append({
            "race_id":         race_id,
            "horse_id":       r.get("horse_id"),
            "horse_name":     r.get("horse_name"),
            "finish_position": r.get("position"),
            "position_text":  r.get("position_text"),
            "beaten_distance":r.get("beaten_distance"),
            "sp":             r.get("sp"),
            "win_flag":       r.get("is_winner"),
            "place_flag":     r.get("is_placed"),
            "result_status":  r.get("result_status"),
            "jockey_name":    r.get("jockey_name"),
            "trainer_name":   r.get("trainer_name"),
        })
    if rows:
        db.table(f"{SCHEMA}.fr_results").upsert(rows, on_conflict="race_id,horse_id").execute()
    return len(rows)


def log_ingestion(run_date: str, races: int, runners: int, results: int,
                  status: str, error: str, raw_payload: dict):
    db.table(f"{SCHEMA}.fr_ingestion_log").insert({
        "run_date":        run_date,
        "races_fetched":   races,
        "runners_fetched": runners,
        "results_fetched": results,
        "status":          status,
        "error_message":   error,
        "raw_payload":     raw_payload,
        "source_url":      "https://api.theracingapi.com/v1/racecards",
    }).execute()


def fetch_fr_racecards(api_date: str) -> tuple:
    """Fetch FR races from Racing API. Returns (racecards_list, raw_json)."""
    resp = requests.get(
        "https://api.theracingapi.com/v1/racecards",
        auth=(RA_USERNAME, RA_PASSWORD),
        params={"date": api_date},
        timeout=30,
    )
    if resp.status_code == 429:
        raise RuntimeError("Racing API rate limited")
    resp.raise_for_status()
    data = resp.json()
    all_races = data.get("racecards", []) if isinstance(data, dict) else data
    fr_races = [r for r in all_races if r.get("region") == "FR"]
    log.info(f"API returned {len(all_races)} races, {len(fr_races)} FR for {api_date}")
    return fr_races, {"racecards": all_races, "date": api_date}


def fetch_fr_results(api_date: str) -> dict:
    """Fetch FR results. Returns dict: race_id -> list of result rows."""
    resp = requests.get(
        "https://api.theracingapi.com/v1/results",
        auth=(RA_USERNAME, RA_PASSWORD),
        params={"date": api_date},
        timeout=30,
    )
    if resp.status in (429, 422):
        log.warning(f"Results not available ({resp.status_code})")
        return {}

    resp.raise_for_status()
    data = resp.json()
    all_results = data.get("results", data.get("data", [])) if isinstance(data, dict) else data

    fr_by_race = {}
    for row in all_results:
        if row.get("region") == "FR":
            rid = row.get("race_id")
            if rid not in fr_by_race:
                fr_by_race[rid] = []
            fr_by_race[rid].append(row)

    return fr_by_race


def _first_odds(odds_list: list) -> float:
    if not odds_list:
        return None
    try:
        return float(odds_list[0].get("decimal", 0))
    except (IndexError, AttributeError, ValueError):
        return None


def _last_odds(odds_list: list) -> float:
    if not odds_list:
        return None
    try:
        return float(odds_list[-1].get("decimal", 0))
    except (IndexError, AttributeError, ValueError):
        return None


def run(target_date: str) -> dict:
    log.info(f"=== VÉLØ FR Cold Archive Ingest — {target_date} ===")
    fetched_at = datetime.now(timezone.utc)
    total_races = 0
    total_runners = 0
    total_results = 0

    try:
        fr_races, raw_payload = fetch_fr_racecards(target_date)
    except Exception as e:
        log.error(f"Failed to fetch FR racecards: {e}")
        log_ingestion(target_date, 0, 0, 0, "failed", str(e), {})
        raise

    if not fr_races:
        log.warning("No FR races found — skipping.")
        log_ingestion(target_date, 0, 0, 0, "partial", "No FR races found", {})
        return {"races": 0, "runners": 0, "results": 0}

    fr_results_by_race = {}
    try:
        fr_results_by_race = fetch_fr_results(target_date)
    except Exception as e:
        log.warning(f"Results fetch failed (non-fatal): {e}")

    for race in fr_races:
        race_id = race["race_id"]
        rc = upsert_race(race)
        total_races += 1

        runners = race.get("runners", [])
        if runners:
            uc = upsert_runners(race_id, runners)
            total_runners += uc
            upsert_market_snapshots(race_id, runners, fetched_at)

        race_results = fr_results_by_race.get(race_id, [])
        if race_results:
            uc = upsert_results(race_id, race_results)
            total_results += uc

    log_ingestion(target_date, total_races, total_runners, total_results,
                   "success", None, raw_payload)
    log.info(f"=== FR Ingest Complete: {total_races} races, {total_runners} runners, {total_results} results ===")
    return {"races": total_races, "runners": total_runners, "results": total_results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VÉLØ FR Cold Archive Ingestion")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (default: yesterday)")
    args = parser.parse_args()

    target = args.date
    if not target:
        yesterday = date.today() - timedelta(days=1)
        target = yesterday.isoformat()

    result = run(target)
    print(f"FR Ingest result: {result}")
