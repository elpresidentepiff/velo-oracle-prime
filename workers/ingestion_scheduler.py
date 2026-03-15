#!/usr/bin/env python3.11
"""
VÉLØ Phase II — Ingestion Scheduler
=====================================
Runs as a Railway cron worker. Executes disciplined data pulls
from the Racing API at exact times and writes to Supabase.

Schedule (UTC):
  06:00 — racecards/standard (morning card + runners)
  09:00 — odds snapshot (T-3hrs)
  11:00 — odds snapshot (T-1hr)
  12:30 — odds snapshot (T-30min)
  13:10 — odds snapshot (T-10min)
  post-race — results/{race_id}
  23:00 — entity enrichment (horses/trainers/jockeys/sires/dams)

Usage:
  python3 workers/ingestion_scheduler.py --job <job_name>

Jobs:
  morning_card      — 06:00 pull
  odds_snapshot     — any of the 4 odds pulls
  results           — post-race results
  entity_enrichment — 23:00 enrichment
  create_tables     — one-time schema migration
"""

import os
import sys
import json
import logging
import argparse
import requests
from datetime import datetime, date, timezone
from typing import Optional

# ─── Configuration ────────────────────────────────────────────────────────────

RACING_API_BASE = "https://api.theracingapi.com"
RACING_API_USER = os.environ.get("RACING_API_USERNAME", "cHHxKCt4ePK3TpFrWNq3sax6")
RACING_API_PASS = os.environ.get("RACING_API_PASSWORD", "D2Zlg9VcD4Sjbjcb7pMzpwwy")
RACING_API_AUTH = (RACING_API_USER, RACING_API_PASS)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ltbsxbvfsxtnharjvqcm.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx0YnN4YnZmc3h0bmhhcmp2cWNtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzQ4ODM2OSwiZXhwIjoyMDc5MDY0MzY5fQ.MmQiC3kt6UJ0e2BQ6k32oWbSNbWmv2U0G9E6l6k2C18"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("velo.scheduler")

# ─── Supabase Helpers ─────────────────────────────────────────────────────────

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal"
    }


def sb_upsert(table: str, records: list, conflict_col: str = None) -> dict:
    """Upsert records into a Supabase table."""
    if not records:
        return {"inserted": 0}
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = sb_headers()
    if conflict_col:
        headers["Prefer"] = f"resolution=merge-duplicates,return=minimal"
    r = requests.post(url, headers=headers, json=records, timeout=30)
    if r.status_code not in (200, 201):
        log.error(f"Supabase upsert to {table} failed: {r.status_code} {r.text[:300]}")
        return {"error": r.text, "inserted": 0}
    return {"inserted": len(records)}


def sb_insert(table: str, records: list) -> dict:
    """Insert records into Supabase, ignoring conflicts."""
    if not records:
        return {"inserted": 0}
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = sb_headers()
    headers["Prefer"] = "return=minimal"
    r = requests.post(url, headers=headers, json=records, timeout=30)
    if r.status_code not in (200, 201):
        log.error(f"Supabase insert to {table} failed: {r.status_code} {r.text[:300]}")
        return {"error": r.text, "inserted": 0}
    return {"inserted": len(records)}


def sb_select(table: str, params: dict = None) -> list:
    """Select records from a Supabase table."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.get(url, headers=sb_headers(), params=params, timeout=15)
    if r.status_code != 200:
        log.error(f"Supabase select from {table} failed: {r.status_code}")
        return []
    return r.json()


def sb_run_sql(sql: str, access_token: str) -> dict:
    """Run raw SQL via Supabase Management API."""
    PROJECT_REF = "ltbsxbvfsxtnharjvqcm"
    r = requests.post(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={"query": sql},
        timeout=30
    )
    return r.json()


# ─── Racing API Helpers ───────────────────────────────────────────────────────

def api_get(path: str, params: dict = None) -> Optional[dict]:
    """Fetch from Racing API with error handling."""
    url = f"{RACING_API_BASE}{path}"
    try:
        r = requests.get(url, auth=RACING_API_AUTH, params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        log.error(f"Racing API {path} returned {r.status_code}: {r.text[:200]}")
        return None
    except Exception as e:
        log.error(f"Racing API request failed for {path}: {e}")
        return None


def save_raw_payload(endpoint: str, payload: dict, label: str = "") -> None:
    """Store raw API response in raw_payloads table for audit/recovery."""
    record = {
        "endpoint": endpoint,
        "label": label,
        "payload": json.dumps(payload),
        "fetched_at": datetime.now(timezone.utc).isoformat()
    }
    # Best-effort — don't fail the pipeline if raw archive fails
    try:
        sb_insert("raw_payloads", [record])
    except Exception as e:
        log.warning(f"Failed to archive raw payload for {endpoint}: {e}")


# ─── Job: Morning Card (06:00) ────────────────────────────────────────────────

def job_morning_card():
    """
    Pull racecards/standard for today's UK/Ireland races.
    Writes to: races, runners, comments_archive, gear_medical_events
    """
    log.info("=== JOB: morning_card ===")
    today = date.today().isoformat()

    # Fetch GB and Ireland separately (API does not support comma-separated region codes)
    data_gb = api_get("/v1/racecards/standard", {"day": "today", "region_codes": "gb"})
    data_ire = api_get("/v1/racecards/standard", {"day": "today", "region_codes": "ire"})
    if not data_gb and not data_ire:
        log.error("Failed to fetch morning card for both GB and Ireland. Aborting.")
        return

    races_payload = []
    if data_gb:
        races_payload.extend(data_gb.get("racecards", []))
    if data_ire:
        races_payload.extend(data_ire.get("racecards", []))
    log.info(f"Fetched {len(races_payload)} races for {today}")

    races, runners, comments, gear_events = [], [], [], []
    now = datetime.now(timezone.utc).isoformat()

    for race in races_payload:
        race_id = race.get("race_id", "")
        if not race_id:
            continue

        # ── Race record ──
        races.append({
            "race_id": race_id,
            "course": race.get("course", ""),
            "date": race.get("date", today),
            "time": race.get("off_time", ""),
            "race_type": race.get("type", ""),
            "distance_f": int(_parse_distance(race.get("distance_f", race.get("distance", "0")))),
            "going": race.get("going", ""),
            "class": str(race.get("class", "")),
            "prize_money": _parse_int(race.get("prize", "0")),
            "runners_count": len(race.get("runners", [])),
        })

        # ── Runner records ──
        for runner in race.get("runners", []):
            horse_id = runner.get("horse_id", "")
            horse_name = runner.get("horse", "")

            runners.append({
                "race_id": race_id,
                "horse_name": horse_name,
                "horse_id": horse_id,
                "trainer": runner.get("trainer", ""),
                "trainer_id": runner.get("trainer_id", ""),
                "jockey": runner.get("jockey", ""),
                "jockey_id": runner.get("jockey_id", ""),
                "draw": _parse_int(runner.get("draw", 0)),
                "weight": str(runner.get("weight", "")),
                "age": _parse_int(runner.get("age", 0)),
                "sex": runner.get("sex", ""),
                "or_rating": _parse_int(runner.get("official_rating", 0)),
                "ts_rating": _parse_int(runner.get("ts", 0)),
                "rpr": _parse_int(runner.get("rpr", 0)),
                "form": runner.get("form", ""),
                "headgear": runner.get("headgear", ""),
                "wind_surgery": bool(runner.get("wind_surgery")) if runner.get("wind_surgery") not in (None, "", False) else None,
                "wind_surgery_run": _parse_int(runner.get("wind_surgery_run", 0)),
                "sire": runner.get("sire", ""),
                "sire_id": runner.get("sire_id", ""),
                "dam": runner.get("dam", ""),
                "dam_id": runner.get("dam_id", ""),
                "damsire": runner.get("damsire", ""),
                "damsire_id": runner.get("damsire_id", ""),
                "owner": runner.get("owner", ""),
                "owner_id": runner.get("owner_id", ""),
                "rpd_evidence": runner.get("spotlight", runner.get("comment", "")),
                "created_at": now,
            })

            # ── Comments archive ──
            spotlight = runner.get("spotlight", "")
            comment = runner.get("comment", "")
            if spotlight or comment:
                comments.append({
                    "horse_id": horse_id,
                    "horse_name": horse_name,
                    "race_id": race_id,
                    "spotlight": spotlight,
                    "comment": comment,
                    "stable_tour": runner.get("stable_tour", ""),
                    "quotes": runner.get("quotes", ""),
                    "fetched_at": now,
                })

            # ── Gear / medical events ──
            headgear = runner.get("headgear", "")
            wind_surgery = runner.get("wind_surgery", False)
            if headgear or wind_surgery:
                gear_events.append({
                    "horse_id": horse_id,
                    "horse_name": horse_name,
                    "race_id": race_id,
                    "headgear": headgear,
                    "headgear_run": _parse_int(runner.get("headgear_run", 0)),
                    "wind_surgery": bool(wind_surgery),
                    "wind_surgery_run": _parse_int(runner.get("wind_surgery_run", 0)),
                    "detected_at": now,
                })

    # ── Write to Supabase ──
    log.info(f"Writing {len(races)} races, {len(runners)} runners, {len(comments)} comments, {len(gear_events)} gear events")
    sb_upsert("races", races)
    sb_upsert("runners", runners)
    sb_insert("comments_archive", comments)
    sb_insert("gear_medical_events", gear_events)

    log.info("morning_card complete.")


# ─── Job: Odds Snapshot ───────────────────────────────────────────────────────

def job_odds_snapshot():
    """
    Pull current odds for all today's races.
    Writes to: odds_snapshots
    """
    log.info("=== JOB: odds_snapshot ===")
    today = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()

    # Fetch GB and Ireland separately
    data_gb = api_get("/v1/racecards/standard", {"day": "today", "region_codes": "gb"})
    data_ire = api_get("/v1/racecards/standard", {"day": "today", "region_codes": "ire"})
    if not data_gb and not data_ire:
        log.error("Failed to fetch odds snapshot. Aborting.")
        return

    all_racecards = []
    if data_gb:
        all_racecards.extend(data_gb.get("racecards", []))
    if data_ire:
        all_racecards.extend(data_ire.get("racecards", []))

    snapshots = []
    for race in all_racecards:
        race_id = race.get("race_id", "")
        for runner in race.get("runners", []):
            horse_id = runner.get("horse_id", "")
            sp = runner.get("sp", runner.get("odds", None))
            if sp:
                snapshots.append({
                    "race_id": race_id,
                    "horse_id": horse_id,
                    "horse_name": runner.get("horse", ""),
                    "decimal_odds": _parse_float(sp),
                    "fractional_odds": str(sp),
                    "bookmaker": "Racing API SP",
                    "snapshot_time": now,
                })

    log.info(f"Writing {len(snapshots)} odds snapshots")
    sb_insert("odds_snapshots", snapshots)
    log.info("odds_snapshot complete.")


# ─── Job: Results ─────────────────────────────────────────────────────────────

def job_results():
    """
    Pull today's results and write to results table.
    """
    log.info("=== JOB: results ===")
    now = datetime.now(timezone.utc).isoformat()

    data = api_get("/v1/results/today")
    if not data:
        log.error("Failed to fetch results. Aborting.")
        return

    results = []
    for race in data.get("results", []):
        race_id = race.get("race_id", "")
        for runner in race.get("runners", []):
            results.append({
                "race_id": race_id,
                "horse_id": runner.get("horse_id", ""),
                "horse_name": runner.get("horse", ""),
                "position": _parse_int(runner.get("position", 0)),
                "win_bsp": _parse_float(runner.get("bsp", 0)),
                "isp": str(runner.get("sp", "")),
                "place_bsp": _parse_float(runner.get("place_bsp", 0)),
                "created_at": now,
            })

    log.info(f"Writing {len(results)} results")
    sb_upsert("results", results)
    log.info("results complete.")


# ─── Job: Entity Enrichment (23:00) ──────────────────────────────────────────

def job_entity_enrichment():
    """
    Enrich horse/trainer/jockey entities for all runners seen today.
    Writes to: horses, trainers, jockeys
    """
    log.info("=== JOB: entity_enrichment ===")
    today = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()

    # Get all unique horse/trainer/jockey IDs from today's runners
    runners = sb_select("runners", {"date": f"eq.{today}"})
    if not runners:
        # Try by created_at date
        runners = sb_select("runners", {"created_at": f"gte.{today}"})

    if not runners:
        log.warning("No runners found for today. Skipping enrichment.")
        return

    horse_ids = list(set(r.get("horse_id", "") for r in runners if r.get("horse_id")))
    trainer_ids = list(set(r.get("trainer_id", "") for r in runners if r.get("trainer_id")))
    jockey_ids = list(set(r.get("jockey_id", "") for r in runners if r.get("jockey_id")))

    log.info(f"Enriching {len(horse_ids)} horses, {len(trainer_ids)} trainers, {len(jockey_ids)} jockeys")

    # ── Enrich horses ──
    horses = []
    for horse_id in horse_ids[:50]:  # Rate limit: max 50 per run
        data = api_get(f"/v1/horses/{horse_id}/standard")
        if data:
            horses.append({
                "horse_id": horse_id,
                "horse_name": data.get("horse", ""),
                "age": _parse_int(data.get("age", 0)),
                "sex": data.get("sex", ""),
                "sire_id": data.get("sire_id", ""),
                "sire": data.get("sire", ""),
                "dam_id": data.get("dam_id", ""),
                "dam": data.get("dam", ""),
                "damsire_id": data.get("damsire_id", ""),
                "damsire": data.get("damsire", ""),
                "trainer_id": data.get("trainer_id", ""),
                "trainer": data.get("trainer", ""),
                "owner_id": data.get("owner_id", ""),
                "owner": data.get("owner", ""),
                "country": data.get("country", ""),
                "colour": data.get("colour", ""),
                "updated_at": now,
            })

    if horses:
        sb_upsert("horses", horses)
        log.info(f"Enriched {len(horses)} horses")

    log.info("entity_enrichment complete.")


# ─── Job: Create Tables (One-Time Migration) ──────────────────────────────────

def job_create_tables():
    """
    One-time migration to create all Phase II tables.
    Requires SUPABASE_ACCESS_TOKEN env var.
    """
    log.info("=== JOB: create_tables ===")
    access_token = os.environ.get("SUPABASE_ACCESS_TOKEN", "sbp_ce68eebbcf70f9a73c6e1efdfb43f4ede19ff949")

    migrations = [
        # Raw payloads archive
        """
        CREATE TABLE IF NOT EXISTS raw_payloads (
            id BIGSERIAL PRIMARY KEY,
            endpoint TEXT NOT NULL,
            label TEXT,
            payload JSONB NOT NULL,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_raw_payloads_endpoint ON raw_payloads(endpoint);
        CREATE INDEX IF NOT EXISTS idx_raw_payloads_fetched ON raw_payloads(fetched_at);
        """,

        # Odds snapshots
        """
        CREATE TABLE IF NOT EXISTS odds_snapshots (
            id BIGSERIAL PRIMARY KEY,
            race_id TEXT NOT NULL,
            horse_id TEXT NOT NULL,
            horse_name TEXT,
            decimal_odds NUMERIC,
            fractional_odds TEXT,
            bookmaker TEXT DEFAULT 'Racing API SP',
            snapshot_time TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_odds_race ON odds_snapshots(race_id);
        CREATE INDEX IF NOT EXISTS idx_odds_horse ON odds_snapshots(horse_id);
        CREATE INDEX IF NOT EXISTS idx_odds_time ON odds_snapshots(snapshot_time);
        """,

        # Comments archive
        """
        CREATE TABLE IF NOT EXISTS comments_archive (
            id BIGSERIAL PRIMARY KEY,
            horse_id TEXT,
            horse_name TEXT,
            race_id TEXT,
            spotlight TEXT,
            comment TEXT,
            stable_tour TEXT,
            quotes TEXT,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_comments_horse ON comments_archive(horse_id);
        CREATE INDEX IF NOT EXISTS idx_comments_race ON comments_archive(race_id);
        """,

        # Gear and medical events
        """
        CREATE TABLE IF NOT EXISTS gear_medical_events (
            id BIGSERIAL PRIMARY KEY,
            horse_id TEXT,
            horse_name TEXT,
            race_id TEXT,
            headgear TEXT,
            headgear_run INTEGER DEFAULT 0,
            wind_surgery BOOLEAN DEFAULT FALSE,
            wind_surgery_run INTEGER DEFAULT 0,
            detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_gear_horse ON gear_medical_events(horse_id);
        """,

        # Trainer switch events
        """
        CREATE TABLE IF NOT EXISTS trainer_switch_events (
            id BIGSERIAL PRIMARY KEY,
            horse_id TEXT NOT NULL,
            horse_name TEXT,
            prev_trainer_id TEXT,
            prev_trainer TEXT,
            new_trainer_id TEXT,
            new_trainer TEXT,
            detected_date DATE NOT NULL DEFAULT CURRENT_DATE
        );
        CREATE INDEX IF NOT EXISTS idx_trainer_switch_horse ON trainer_switch_events(horse_id);
        """,

        # Horses entity table
        """
        CREATE TABLE IF NOT EXISTS horses (
            horse_id TEXT PRIMARY KEY,
            horse_name TEXT,
            age INTEGER,
            sex TEXT,
            colour TEXT,
            country TEXT,
            sire_id TEXT,
            sire TEXT,
            dam_id TEXT,
            dam TEXT,
            damsire_id TEXT,
            damsire TEXT,
            trainer_id TEXT,
            trainer TEXT,
            owner_id TEXT,
            owner TEXT,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,

        # Trainers entity table
        """
        CREATE TABLE IF NOT EXISTS trainers (
            trainer_id TEXT PRIMARY KEY,
            trainer_name TEXT,
            country TEXT,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,

        # Jockeys entity table
        """
        CREATE TABLE IF NOT EXISTS jockeys (
            jockey_id TEXT PRIMARY KEY,
            jockey_name TEXT,
            country TEXT,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,

        # VÉLØ features table (feature factory output)
        """
        CREATE TABLE IF NOT EXISTS velo_features (
            id BIGSERIAL PRIMARY KEY,
            runner_id TEXT,
            race_id TEXT NOT NULL,
            horse_id TEXT,
            horse_name TEXT,
            trainer_heat_score NUMERIC,
            jockey_trainer_combo_score NUMERIC,
            wind_op_run_number INTEGER,
            headgear_delta NUMERIC,
            stable_switch_flag BOOLEAN DEFAULT FALSE,
            breeding_stamina_score NUMERIC,
            breeding_class_score NUMERIC,
            going_suitability_score NUMERIC,
            course_suitability_score NUMERIC,
            market_steam_class TEXT,
            computed_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_velo_features_runner_race ON velo_features(race_id, horse_id);
        """,

        # Post-race reviews (learning loop)
        """
        CREATE TABLE IF NOT EXISTS post_race_reviews (
            id BIGSERIAL PRIMARY KEY,
            race_id TEXT NOT NULL,
            verdict_id TEXT,
            expected_winner TEXT,
            actual_winner TEXT,
            velo_correct BOOLEAN,
            miss_reason TEXT,
            signal_analysis JSONB,
            learning_patch TEXT,
            reviewed_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_post_race_race ON post_race_reviews(race_id);
        """,

        # Add horse_id column to runners if it doesn't exist
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='runners' AND column_name='horse_id') THEN
                ALTER TABLE runners ADD COLUMN horse_id TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='runners' AND column_name='trainer_id') THEN
                ALTER TABLE runners ADD COLUMN trainer_id TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='runners' AND column_name='jockey_id') THEN
                ALTER TABLE runners ADD COLUMN jockey_id TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='runners' AND column_name='age') THEN
                ALTER TABLE runners ADD COLUMN age INTEGER;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='runners' AND column_name='sex') THEN
                ALTER TABLE runners ADD COLUMN sex TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='runners' AND column_name='headgear') THEN
                ALTER TABLE runners ADD COLUMN headgear TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='runners' AND column_name='wind_surgery') THEN
                ALTER TABLE runners ADD COLUMN wind_surgery BOOLEAN DEFAULT FALSE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='runners' AND column_name='wind_surgery_run') THEN
                ALTER TABLE runners ADD COLUMN wind_surgery_run INTEGER DEFAULT 0;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='runners' AND column_name='sire') THEN
                ALTER TABLE runners ADD COLUMN sire TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='runners' AND column_name='sire_id') THEN
                ALTER TABLE runners ADD COLUMN sire_id TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='runners' AND column_name='dam') THEN
                ALTER TABLE runners ADD COLUMN dam TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='runners' AND column_name='dam_id') THEN
                ALTER TABLE runners ADD COLUMN dam_id TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='runners' AND column_name='damsire') THEN
                ALTER TABLE runners ADD COLUMN damsire TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='runners' AND column_name='damsire_id') THEN
                ALTER TABLE runners ADD COLUMN damsire_id TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='runners' AND column_name='owner') THEN
                ALTER TABLE runners ADD COLUMN owner TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name='runners' AND column_name='owner_id') THEN
                ALTER TABLE runners ADD COLUMN owner_id TEXT;
            END IF;
        END $$;
        """,
    ]

    PROJECT_REF = "ltbsxbvfsxtnharjvqcm"
    success_count = 0
    for i, sql in enumerate(migrations):
        r = requests.post(
            f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"query": sql.strip()},
            timeout=30
        )
        if r.status_code in (200, 201):
            log.info(f"Migration {i+1}/{len(migrations)}: OK")
            success_count += 1
        else:
            log.error(f"Migration {i+1}/{len(migrations)} failed: {r.status_code} {r.text[:200]}")

    log.info(f"create_tables complete. {success_count}/{len(migrations)} migrations succeeded.")


# ─── Utility Functions ────────────────────────────────────────────────────────

def _parse_int(val) -> int:
    try:
        return int(float(str(val).replace(",", "").replace("£", "").strip()))
    except (ValueError, TypeError):
        return 0


def _parse_float(val) -> float:
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0


def _parse_distance(val) -> float:
    """Parse distance string to furlongs as float."""
    try:
        return float(str(val).replace("f", "").strip())
    except (ValueError, TypeError):
        return 0.0


# ─── Entry Point ─────────────────────────────────────────────────────────────

JOB_MAP = {
    "morning_card": job_morning_card,
    "odds_snapshot": job_odds_snapshot,
    "results": job_results,
    "entity_enrichment": job_entity_enrichment,
    "create_tables": job_create_tables,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VÉLØ Ingestion Scheduler")
    parser.add_argument("--job", required=True, choices=list(JOB_MAP.keys()),
                        help="The job to run")
    args = parser.parse_args()

    log.info(f"Starting job: {args.job}")
    start = datetime.now(timezone.utc)
    try:
        JOB_MAP[args.job]()
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        log.info(f"Job {args.job} completed in {elapsed:.1f}s")
    except Exception as e:
        log.error(f"Job {args.job} failed with exception: {e}", exc_info=True)
        sys.exit(1)
