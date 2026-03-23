"""
hk_daily_ingest.py
VÉLØ HK Research Lane — Daily Ingestion Script

Purpose: Archive HK racecards, runners, results, and entity history.
Location: workers/hk_daily_ingest.py
Schedule: 08:00 UTC daily (after UK race day ends, HK races are live)

Rules:
- hk_research schema ONLY. Never writes to public. or velo_* tables.
- No production verdict authority. No doctrine learning.
- Service role key only. No anon writes.
- Idempotent: upsert on race_id + horse_id. Safe to re-run.
- UK_ALLOWED filter must NEVER be applied here — HK is HK, UK is UK.

Usage:
  python -m workers.hk_daily_ingest --date 2026-03-23
  python -m workers.hk_daily_ingest   # defaults to yesterday
"""

import argparse
import logging
from datetime import date, datetime, timezone
from pathlib import Path
import sys

import requests
from supabase import Client, create_client

log = logging.getLogger("velo.hk_ingest")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── Config ──────────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.getenv("SUPABASE_URL")
SUPABASE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # service role ONLY
RA_USERNAME: str = os.getenv("RACING_API_USERNAME")
RA_PASSWORD: str = os.getenv("RACING_API_PASSWORD")

HK_COURSES: set = {"Happy Valley", "Sha Tin"}  # explicit allowlist

if not all([SUPABASE_URL, SUPABASE_KEY, RA_USERNAME, RA_PASSWORD]):
    raise EnvironmentError("Missing env vars: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, RACING_API_USERNAME, RACING_API_PASSWORD")


# ── Supabase ────────────────────────────────────────────────────────────────
db: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

SCHEMA = "hk_research"


def upsert_race(race: dict) -> int:
    """Upsert one HK race. Returns runner count."""
    row = {
        "race_id":        race["race_id"],
        "meeting_date":   race.get("date"),
        "course":         race.get("course"),
        "region":         race.get("region", "HK"),
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
        "big_race":       race.get("big_race", False),
        "is_abandoned":   race.get("is_abandoned", False),
        "race_status":    race.get("race_status"),
    }
    db.table(f"{SCHEMA}.hk_races").upsert(row, on_conflict="race_id").execute()
    return len(race.get("runners", []))


def upsert_runners(race_id: str, runners: list) -> int:
    """Upsert runner snapshots for a race. Returns count."""
    rows = []
    for r in runners:
        rows.append({
            "race_id":       race_id,
            "horse_id":     r.get("horse_id"),
            "horse_name":   r.get("horse_name"),
            "draw":         r.get("draw"),
            "weight_kg":    r.get("weight_kg") or r.get("weight"),
            "rating":       r.get("rating"),
            "age":          r.get("age"),
            "sex":          r.get("sex"),
            "jockey_id":    r.get("jockey_id"),
            "jockey_name":  r.get("jockey_name"),
            "trainer_id":   r.get("trainer_id"),
            "trainer_name": r.get("trainer_name"),
            "barrier":      r.get("barrier"),
            "odds_open":    _first_odds(r.get("odds")),
            "odds_live":    _last_odds(r.get("odds")),
            "fav_flag":     r.get("fav_flag"),
            "rpr":          r.get("rpr"),
            "ts":           r.get("ts"),
            "or_rating":    r.get("or_rating"),
            "form":         r.get("form"),
            "comment":      r.get("comment"),
        })
    if rows:
        db.table(f"{SCHEMA}.hk_runners").upsert(rows, on_conflict="race_id,horse_id").execute()
    return len(rows)


def upsert_results(race_id: str, results: list) -> int:
    """Upsert results for a race. Returns count."""
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
            "weight_carried": r.get("weight_carried"),
        })
    if rows:
        db.table(f"{SCHEMA}.hk_results").upsert(rows, on_conflict="race_id,horse_id").execute()
    return len(rows)


def upsert_horse_history(race_id: str, results: list) -> int:
    """Append historical run for each horse in results."""
    # Fetch race metadata for context
    race_resp = db.table(f"{SCHEMA}.hk_races").select("*").eq("race_id", race_id).maybe_single().execute()
    if not race_resp.data:
        return 0
    race_meta = race_resp.data

    rows = []
    for r in results:
        rows.append({
            "horse_id":        r.get("horse_id"),
            "horse_name":      r.get("horse_name"),
            "race_id":         race_id,
            "meeting_date":    race_meta.get("meeting_date"),
            "course":          race_meta.get("course"),
            "distance_f":      race_meta.get("distance_f"),
            "surface":         race_meta.get("surface"),
            "race_class":      race_meta.get("race_class"),
            "going":           race_meta.get("going"),
            "draw":            r.get("draw"),
            "finish_position": r.get("position"),
            "position_text":   r.get("position_text"),
            "sp":              r.get("sp"),
            "weight_kg":       r.get("weight_kg"),
            "jockey_name":     r.get("jockey_name"),
            "trainer_name":    r.get("trainer_name"),
            "rpr":             r.get("rpr"),
            "ts":              r.get("ts"),
            "form":            r.get("form"),
        })
    if rows:
        db.table(f"{SCHEMA}.hk_horse_history").upsert(rows, on_conflict="horse_id,race_id").execute()
    return len(rows)


def log_ingestion(run_date: str, races: int, runners: int, results: int, status: str, error: str = None):
    db.table(f"{SCHEMA}.hk_ingestion_log").insert({
        "run_date":       run_date,
        "races_fetched":  races,
        "runners_fetched":runners,
        "results_fetched":results,
        "status":         status,
        "error_message":  error,
    }).execute()


def fetch_hk_racecards(api_date: str) -> list:
    """Fetch all HK races from Racing API for a given date."""
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

    hk_races = [r for r in all_races if r.get("region") == "HK"]
    log.info(f"API returned {len(all_races)} races, {len(hk_races)} HK for {api_date}")
    return hk_races


def fetch_hk_results(api_date: str) -> dict:
    """
    Fetch HK results from Racing API.
    Returns dict: race_id -> list of runner result rows.
    """
    resp = requests.get(
        "https://api.theracingapi.com/v1/results",
        auth=(RA_USERNAME, RA_PASSWORD),
        params={"date": api_date},
        timeout=30,
    )
    if resp.status_code in (429, 422):
        log.warning(f"Results not yet available ({resp.status_code})")
        return {}

    resp.raise_for_status()
    data = resp.json()

    # Try "results" key first, then top-level list
    if isinstance(data, dict):
        all_results = data.get("results", data.get("data", []))
    else:
        all_results = data

    # Filter to HK races only
    hk_by_race = {}
    for row in all_results:
        if row.get("region") == "HK":
            rid = row.get("race_id")
            if rid not in hk_by_race:
                hk_by_race[rid] = []
            hk_by_race[rid].append(row)

    log.info(f"API returned {len(all_results)} result rows, {len(hk_by_race)} HK races with results")
    return hk_by_race


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
    """
    Main ingestion for HK races on target_date (YYYY-MM-DD).
    Writes to hk_research.* only. Returns summary dict.
    """
    log.info(f"=== VÉLØ HK Daily Ingest — {target_date} ===")

    total_races = 0
    total_runners = 0
    total_results = 0

    try:
        hk_races = fetch_hk_racecards(target_date)
    except Exception as e:
        log.error(f"Failed to fetch HK racecards: {e}")
        log_ingestion(target_date, 0, 0, 0, "failed", str(e))
        raise

    if not hk_races:
        log.warning("No HK races found for this date — skipping.")
        log_ingestion(target_date, 0, 0, 0, "partial", "No HK races found")
        return {"races": 0, "runners": 0, "results": 0}

    # Fetch results (may not be available for today's races yet)
    hk_results_by_race = {}
    try:
        hk_results_by_race = fetch_hk_results(target_date)
    except Exception as e:
        log.warning(f"Results fetch failed (non-fatal): {e}")

    for race in hk_races:
        race_id = race["race_id"]
        runner_count = upsert_race(race)
        total_races += 1

        runners = race.get("runners", [])
        if runners:
            uc = upsert_runners(race_id, runners)
            total_runners += uc

        # Upsert results if available
        race_results = hk_results_by_race.get(race_id, [])
        if race_results:
            uc = upsert_results(race_id, race_results)
            total_results += uc
            upsert_horse_history(race_id, race_results)

    log_ingestion(target_date, total_races, total_runners, total_results, "success")
    log.info(f"=== HK Ingest Complete: {total_races} races, {total_runners} runners, {total_results} results ===")

    return {"races": total_races, "runners": total_runners, "results": total_results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VÉLØ HK Daily Ingestion")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (default: yesterday)")
    args = parser.parse_args()

    target = args.date
    if not target:
        yesterday = date.today() - timedelta(days=1)
        target = yesterday.isoformat()

    result = run(target)
    print(f"HK Ingest result: {result}")
