#!/usr/bin/env python3.11
"""
VÉLØ Daily Pipeline — Phase 2.2 Hardened
==========================================
Runs daily at 06:00am UTC to:
1. Open a pipeline_run record (observability)
2. Fetch all UK/Ireland racecards from the Racing API
3. Archive every raw API response to raw_payload_archive (safety)
4. Write races and runners to Supabase
5. Upsert entity profiles (horse, trainer, jockey, owner, course)
6. Populate runner_race_facts (master fact table)
7. Parse spotlight comments through the NLP parser
8. Write horse_comments flags to Supabase
9. Reconcile results for today AND the prior 2 days (delayed result resilience)
10. Close the pipeline_run record with final status

Usage:
    python3.11 workers/daily_pipeline.py [--date YYYY-MM-DD]

Environment variables REQUIRED (no fallbacks — will crash if absent):
    RACING_API_USERNAME
    RACING_API_PASSWORD
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
"""
import os
import sys
import json
import time
import hashlib
import logging
import argparse
import traceback
import requests
from datetime import datetime, date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("velo.daily_pipeline")

PARSER_VERSION = "2.2.0"

# ── FAIL-FAST ENVIRONMENT LOADING ─────────────────────────────────────────────
# No fallbacks. No hardcoded secrets. If an env var is missing, crash immediately.
_REQUIRED_ENV = [
    "RACING_API_USERNAME",
    "RACING_API_PASSWORD",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
]
_missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
if _missing:
    log.critical(f"FATAL: Missing required environment variables: {_missing}")
    log.critical("Set them in Railway environment variables. Refusing to start.")
    sys.exit(2)

RACING_API_USER = os.environ["RACING_API_USERNAME"]
RACING_API_PASS = os.environ["RACING_API_PASSWORD"]
SUPABASE_URL    = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY     = os.environ["SUPABASE_SERVICE_KEY"]

_BASE_HEADERS = {
    "Authorization": f"Bearer {SERVICE_KEY}",
    "apikey": SERVICE_KEY,
    "Content-Type": "application/json",
}
SUPABASE_HEADERS = {
    **_BASE_HEADERS,
    "Prefer": "resolution=merge-duplicates,return=minimal",
}

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
RESULTS_RETRY_DAYS = 2          # Reconcile results for today + prior N days
MAX_RETRIES        = 3          # Retry attempts for Supabase writes
RETRY_BACKOFF      = [1, 2, 4]  # Seconds between retries
BATCH_SIZE         = 50         # Max rows per batch upsert

NEGATIVE_PHRASES = [
    "needs to improve", "well held", "out of depth", "struggling",
    "pulled up", "unseated", "fell", "refused", "never dangerous",
    "tailed off", "weakened", "faded", "beaten a long way",
    "non-stayer", "stamina doubtful", "trip too far", "trip too short",
    "headstrong", "hard to predict", "quirky", "awkward",
    "market drifter", "drifted in market", "weak in market",
    "fitness doubts", "not fully fit", "needed the run",
    "wind operation", "breathing problem",
]
POSITIVE_PHRASES = [
    "eye-catching", "eye catching", "caught the eye", "unlucky",
    "hampered", "short of room", "checked", "squeezed out",
    "course specialist", "loves this track", "course and distance winner",
    "in form", "trainer in form", "yard in form", "yard firing",
    "top jockey booking", "booking of note", "significant jockey booking",
    "progressive", "open to improvement", "unexposed",
    "well handicapped", "off a good mark", "dropped in class",
    "class dropper", "step down in class",
]
STAMINA_DOUBT_PHRASES = [
    "non-stayer", "stamina doubtful", "trip too far", "may not stay",
    "likely non-stayer", "stamina suspect", "bred for shorter",
]
BEHAVIOUR_RISK_PHRASES = [
    "headstrong", "hard to predict", "quirky", "awkward at start",
    "refused", "bolted", "unseated", "erratic",
]


# ── SHARED HELPERS ────────────────────────────────────────────────────────────

def safe_int(val):
    if val is None:
        return None
    try:
        return int(float(str(val).replace(',', '').strip()))
    except (ValueError, TypeError):
        return None


def safe_float(val):
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None


def clean_prize(val):
    if not val:
        return 0
    digits = ''.join(filter(str.isdigit, str(val)))
    return int(digits) if digits else 0


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def supabase_upsert(table: str, rows, conflict_keys=None, run_id=None, stats=None):
    """
    Shared upsert helper with retry/backoff and structured anomaly logging.

    Args:
        table:         Supabase table name
        rows:          Single dict or list of dicts
        conflict_keys: List of column names for conflict resolution (unused in REST API,
                       handled by Prefer: resolution=merge-duplicates)
        run_id:        Current pipeline_run_id for anomaly logging
        stats:         Stats dict to increment failure counters

    Returns:
        True if successful, False otherwise
    """
    if isinstance(rows, dict):
        rows = [rows]
    if not rows:
        return True

    # Build URL — pass on_conflict for composite key resolution
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if conflict_keys:
        url += f"?on_conflict={','.join(conflict_keys)}"

    # Batch writes
    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start:batch_start + BATCH_SIZE]
        last_error = None
        for attempt, delay in enumerate(RETRY_BACKOFF[:MAX_RETRIES]):
            try:
                r = requests.post(
                    url,
                    headers=SUPABASE_HEADERS,
                    json=batch if len(batch) > 1 else batch[0],
                    timeout=15,
                )
                if r.status_code in (200, 201, 204):
                    break
                last_error = f"HTTP {r.status_code}: {r.text[:200]}"
                log.warning(f"[{table}] Attempt {attempt+1} failed: {last_error}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
            except requests.exceptions.RequestException as exc:
                last_error = str(exc)
                log.warning(f"[{table}] Attempt {attempt+1} exception: {last_error}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
        else:
            # All retries exhausted — log anomaly
            log.error(f"[{table}] All retries failed: {last_error}")
            _log_anomaly(run_id, table, "upsert_failure", last_error, batch[0] if batch else {})
            if stats is not None:
                stats["write_errors"] = stats.get("write_errors", 0) + 1
            return False
    return True


def _log_anomaly(run_id, table_name, anomaly_type, detail, context_row=None):
    """Write a structured anomaly record to ingestion_anomalies."""
    try:
        row = {
            "pipeline_run_id": run_id,
            "table_name": table_name,
            "anomaly_type": anomaly_type,
            "detail": str(detail)[:500],
            "context_snapshot": context_row if context_row else {},
            "severity": "warning",
        }
        requests.post(
            f"{SUPABASE_URL}/rest/v1/ingestion_anomalies",
            headers=SUPABASE_HEADERS,
            json=row,
            timeout=5,
        )
    except Exception:
        pass  # Never let anomaly logging crash the pipeline


# ── PIPELINE RUN MANAGEMENT ───────────────────────────────────────────────────

def open_pipeline_run(run_type, source_date):
    row = {
        "service_name": "ingestion-spine",
        "run_type": run_type,
        "status": "in_progress",
        "source_date": source_date,
        "environment": os.environ.get("RAILWAY_ENVIRONMENT", "production"),
    }
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/pipeline_runs",
        headers={**_BASE_HEADERS, "Prefer": "return=representation"},
        json=row,
        timeout=10,
    )
    if r.status_code in (200, 201):
        data = r.json()
        run_id = data[0]["id"] if isinstance(data, list) else data.get("id")
        log.info(f"[pipeline_runs] Opened run: {run_id}")
        return run_id
    log.error(f"[pipeline_runs] Failed to open run: {r.status_code} {r.text[:200]}")
    return None


def close_pipeline_run(run_id, status, stats, error_msg=None, error_trace=None):
    if not run_id:
        return
    patch = {
        "finished_at": datetime.utcnow().isoformat() + "Z",
        "status": status,
        "races_processed":   stats.get("races_ok", 0),
        "runners_processed": stats.get("runners_ok", 0),
        "comments_processed": stats.get("spotlight_ok", 0),
        "results_processed": stats.get("results_ok", 0),
        "raw_payload_count": stats.get("raw_payloads", 0),
    }
    if error_msg:
        patch["error_message"] = error_msg[:500]
    if error_trace:
        patch["error_trace"] = error_trace[:2000]
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/pipeline_runs?id=eq.{run_id}",
        headers=SUPABASE_HEADERS,
        json=patch,
        timeout=10,
    )
    if r.status_code in (200, 201, 204):
        log.info(f"[pipeline_runs] Closed run {run_id} status={status}")
    else:
        log.error(f"[pipeline_runs] Failed to close run: {r.status_code} {r.text[:200]}")


# ── PAYLOAD ARCHIVING ─────────────────────────────────────────────────────────

def archive_payload(run_id, endpoint, params, race_date, payload):
    payload_str = json.dumps(payload, sort_keys=True)
    row = {
        "pipeline_run_id": run_id,
        "endpoint": endpoint,
        "request_params": params,
        "race_date": race_date,
        "payload_json": payload,
        "checksum": sha256(payload_str),
        "parse_status": "pending",
        "parser_version": PARSER_VERSION,
    }
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/raw_payload_archive",
        headers={**_BASE_HEADERS, "Prefer": "return=representation"},
        json=row,
        timeout=15,
    )
    if r.status_code in (200, 201):
        data = r.json()
        return data[0]["id"] if isinstance(data, list) else data.get("id")
    log.warning(f"[raw_payload_archive] Failed: {r.status_code} {r.text[:200]}")
    return None


def mark_payload_parsed(archive_id, status="success"):
    if not archive_id:
        return
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/raw_payload_archive?id=eq.{archive_id}",
        headers=SUPABASE_HEADERS,
        json={"parse_status": status},
        timeout=10,
    )


# ── ENTITY PROFILE UPSERTS ────────────────────────────────────────────────────

def upsert_horse_profile(runner, race_date, run_id, stats):
    horse_id = runner.get("horse_id")
    if not horse_id:
        return
    supabase_upsert("horse_profiles", {
        "id": horse_id, "name": runner.get("horse", ""),
        "sex": runner.get("sex", ""), "sex_code": runner.get("sex_code", ""),
        "colour": runner.get("colour", ""), "region": runner.get("region", ""),
        "breeder": runner.get("breeder", ""), "sire_id": runner.get("sire_id", ""),
        "sire_name": runner.get("sire", ""), "dam_id": runner.get("dam_id", ""),
        "dam_name": runner.get("dam", ""), "damsire_id": runner.get("damsire_id", ""),
        "damsire_name": runner.get("damsire", ""), "silk_url": runner.get("silk_url", ""),
        "first_seen_date": race_date,
        "last_updated_at": datetime.utcnow().isoformat() + "Z",
    }, run_id=run_id, stats=stats)


def upsert_trainer_profile(runner, race_date, run_id, stats):
    tid = runner.get("trainer_id")
    if not tid:
        return
    supabase_upsert("trainer_profiles", {
        "id": tid, "name": runner.get("trainer", ""),
        "location": runner.get("trainer_location", ""),
        "first_seen_date": race_date,
        "last_updated_at": datetime.utcnow().isoformat() + "Z",
    }, run_id=run_id, stats=stats)


def upsert_jockey_profile(runner, race_date, run_id, stats):
    jid = runner.get("jockey_id")
    if not jid:
        return
    supabase_upsert("jockey_profiles", {
        "id": jid, "name": runner.get("jockey", ""),
        "first_seen_date": race_date,
        "last_updated_at": datetime.utcnow().isoformat() + "Z",
    }, run_id=run_id, stats=stats)


def upsert_owner_profile(runner, race_date, run_id, stats):
    oid = runner.get("owner_id")
    if not oid:
        return
    supabase_upsert("owner_profiles", {
        "id": oid, "name": runner.get("owner", ""),
        "first_seen_date": race_date,
        "last_updated_at": datetime.utcnow().isoformat() + "Z",
    }, run_id=run_id, stats=stats)


def upsert_course_profile(race, run_id, stats):
    cid = race.get("course_id")
    if not cid:
        return
    supabase_upsert("course_profiles", {
        "id": cid, "name": race.get("course", ""),
        "region": race.get("region", ""), "surface": race.get("surface", ""),
        "country": race.get("region", ""),
        "last_updated_at": datetime.utcnow().isoformat() + "Z",
    }, run_id=run_id, stats=stats)


# ── RUNNER RACE FACTS ─────────────────────────────────────────────────────────

def upsert_runner_race_fact(race, runner, race_date, run_id, stats):
    horse_id = runner.get("horse_id")
    race_id  = race.get("race_id")
    if not horse_id or not race_id:
        return

    t14 = runner.get("trainer_14_days", {}) or {}
    odds_list = runner.get("odds", []) or []
    morning_odds = None
    try:
        if odds_list:
            morning_odds = safe_float(odds_list[0].get("decimal"))
    except (IndexError, AttributeError):
        pass

    # Build off_dt from race date + off_time
    off_time_str = race.get("off_time", "")
    off_dt = None
    try:
        if race_date and off_time_str:
            off_dt = f"{race_date}T{off_time_str}:00+00:00"
    except Exception:
        pass

    row = {
        "race_id": race_id,
        "horse_id": horse_id,
        "trainer_id": runner.get("trainer_id"),
        "jockey_id": runner.get("jockey_id"),
        "owner_id": runner.get("owner_id"),
        "course_id": race.get("course_id"),
        "race_date": race_date,
        "race_time": off_time_str,
        "off_dt": off_dt,
        "race_type": race.get("type"),
        "race_class": str(race.get("race_class", "") or ""),
        "race_pattern": race.get("pattern"),
        "distance_f": safe_float(race.get("distance_f")),
        "going": race.get("going"),
        "going_detailed": race.get("going_detailed"),
        "surface": race.get("surface"),
        "field_size": safe_int(race.get("field_size")),
        "region": race.get("region"),
        "horse_age": safe_int(runner.get("age")),
        "horse_sex": runner.get("sex"),
        "stall_draw": safe_int(runner.get("draw")),
        "weight_lbs": safe_int(runner.get("lbs")),
        "official_rating": safe_int(runner.get("ofr")),
        "topspeed": safe_int(runner.get("ts")),
        "rpr": safe_int(runner.get("rpr")),
        "trainer_rtf": runner.get("trainer_rtf"),
        "trainer_14_day_wins": safe_int(t14.get("wins")),
        "trainer_14_day_runs": safe_int(t14.get("runs")),
        "last_run_days": safe_int(runner.get("last_run")),
        "form_string": runner.get("form"),
        "headgear": runner.get("headgear"),
        "headgear_run": runner.get("headgear_run"),
        "wind_surgery": runner.get("wind_surgery"),
        "wind_surgery_run": runner.get("wind_surgery_run"),
        "medical_flags": runner.get("medical"),
        "past_results_flags": runner.get("past_results_flags"),
        "spotlight_text": runner.get("spotlight"),
        "horse_comment": runner.get("comment"),
        "stable_tour_text": runner.get("stable_tour"),
        "quotes_text": runner.get("quotes"),
        "betting_forecast": race.get("betting_forecast"),
        "morning_odds_dec": morning_odds,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    supabase_upsert("runner_race_facts", row, conflict_keys=["race_id", "horse_id"], run_id=run_id, stats=stats)


# ── SPOTLIGHT PARSING ─────────────────────────────────────────────────────────

def parse_spotlight(text, horse_name, race_id, race_date):
    if not text:
        return None
    text_lower = text.lower()
    neg_hits = sum(1 for p in NEGATIVE_PHRASES if p in text_lower)
    pos_hits = sum(1 for p in POSITIVE_PHRASES if p in text_lower)
    sentiment = pos_hits - neg_hits
    flags = {
        "flag_stamina_doubt":    any(p in text_lower for p in STAMINA_DOUBT_PHRASES),
        "flag_behaviour_risk":   any(p in text_lower for p in BEHAVIOUR_RISK_PHRASES),
        "flag_class_drop":       any(p in text_lower for p in ["class dropper", "dropped in class", "step down in class"]),
        "flag_market_drifter":   any(p in text_lower for p in ["market drifter", "drifted in market", "weak in market"]),
        "flag_eye_catching":     any(p in text_lower for p in ["eye-catching", "eye catching", "caught the eye", "unlucky", "hampered"]),
        "flag_course_specialist": any(p in text_lower for p in ["course specialist", "loves this track", "course and distance"]),
        "flag_jockey_booking":   any(p in text_lower for p in ["top jockey booking", "booking of note", "significant jockey booking"]),
        "flag_trainer_form":     any(p in text_lower for p in ["trainer in form", "yard in form", "yard firing"]),
        "flag_fitness_doubt":    any(p in text_lower for p in ["fitness doubts", "not fully fit", "needed the run"]),
        "flag_positive_mention": pos_hits > 0,
    }
    return {
        "race_id": race_id, "horse_name": horse_name,
        "spotlight_text": text[:1000], "sentiment_score": sentiment,
        "race_date": race_date, **flags,
    }


# ── RESULTS RECONCILIATION ────────────────────────────────────────────────────

def reconcile_results_for_date(target_date: str, known_race_ids: set, run_id, stats):
    """
    Fetch results for a single date and write to race_results + runner_results.
    Also back-fills runner_race_facts with post-race data.
    """
    log.info(f"[results] Reconciling results for {target_date}")
    try:
        r = requests.get(
            "https://api.theracingapi.com/v1/results",
            auth=(RACING_API_USER, RACING_API_PASS),
            params={"start_date": target_date, "end_date": target_date},
            timeout=30,
        )
        if r.status_code != 200:
            log.warning(f"[results] API {r.status_code} for {target_date}: {r.text[:200]}")
            return
        payload = r.json()
        archive_payload(run_id, "/v1/results", {"start_date": target_date, "end_date": target_date}, target_date, payload)
        results = payload.get("results", [])
        log.info(f"[results] {len(results)} result races returned for {target_date}")

        # Pre-fetch all race_ids we have ingested for this date to avoid FK violations
        # The results API returns all regions; we only store UK/Ireland races
        known_races_r = requests.get(
            f"{SUPABASE_URL}/rest/v1/races",
            headers=SUPABASE_HEADERS,
            params={"date": f"eq.{target_date}", "select": "race_id"},
            timeout=15,
        )
        known_race_ids = set()
        if known_races_r.status_code == 200:
            known_race_ids = {r["race_id"] for r in known_races_r.json()}
        log.info(f"[results] Known race IDs for {target_date}: {len(known_race_ids)}")

        for result_race in results:
            race_id = result_race.get("race_id")
            # Skip races not in our DB (non-UK/Ireland or races we didn't ingest)
            if race_id not in known_race_ids:
                continue
            supabase_upsert("race_results", {
                "race_id": race_id,
                "winning_time_detail": result_race.get("winning_time_detail"),
                "tote_win":      safe_float(result_race.get("tote_win")),
                "tote_place":    result_race.get("tote_pl"),
                "tote_exacta":   safe_float(result_race.get("tote_ex")),
                "tote_csf":      safe_float(result_race.get("tote_csf")),
                "tote_trifecta": safe_float(result_race.get("tote_trifecta")),
                "tote_tricast":  safe_float(result_race.get("tote_tricast")),
                "non_runners":   result_race.get("non_runners"),
            }, run_id=run_id, stats=stats)

            runner_results_batch = []
            rrf_patches = []

            for runner in result_race.get("runners", []):
                pos_raw = runner.get("position", "")
                try:
                    pos_int = int(pos_raw)
                except (ValueError, TypeError):
                    pos_int = None

                runner_results_batch.append({
                    "race_id":   race_id,
                    "horse_id":  runner.get("horse_id", ""),
                    "position":  pos_int,
                    "position_text": str(pos_raw),
                    "sp":        runner.get("sp"),
                    "sp_dec":    safe_float(runner.get("sp_dec")),
                    "bsp":       safe_float(runner.get("bsp")),
                    "btn":       safe_float(runner.get("btn")),
                    "ovr_btn":   safe_float(runner.get("ovr_btn")),
                    "time":      runner.get("time"),
                    "prize":     safe_float(runner.get("prize")),
                    "in_running_comment": runner.get("comment"),
                    "is_winner": pos_int == 1,
                })

                if runner.get("horse_id"):
                    rrf_patches.append({
                        "race_id": race_id,
                        "horse_id": runner["horse_id"],
                        "finishing_position": pos_int,
                        "position_text": str(pos_raw),
                        "sp":    runner.get("sp"),
                        "sp_dec": safe_float(runner.get("sp_dec")),
                        "bsp":   safe_float(runner.get("bsp")),
                        "beaten_distance":     safe_float(runner.get("btn")),
                        "ovr_beaten_distance": safe_float(runner.get("ovr_btn")),
                        "in_running_comment":  runner.get("comment"),
                        "prize_won": safe_float(runner.get("prize")),
                        "is_winner": pos_int == 1,
                        "updated_at": datetime.utcnow().isoformat() + "Z",
                    })

            # Batch write runner_results
            supabase_upsert("runner_results", runner_results_batch, run_id=run_id, stats=stats)
            stats["results_ok"] = stats.get("results_ok", 0) + len(runner_results_batch)

            # Back-fill runner_race_facts via bulk upsert (conflict on race_id + horse_id)
            # This replaces the previous per-runner PATCH loop which caused timeouts.
            if rrf_patches:
                supabase_upsert(
                    "runner_race_facts",
                    rrf_patches,
                    conflict_keys=["race_id", "horse_id"],
                    run_id=run_id,
                    stats=stats,
                )
                log.info(f"[runner_race_facts] Bulk back-fill: {len(rrf_patches)} rows for race {race_id}")

    except Exception as exc:
        log.error(f"[results] Reconciliation failed for {target_date}: {exc}")
        log.error(traceback.format_exc())
        _log_anomaly(run_id, "race_results", "reconciliation_error", str(exc))


# ── MAIN PIPELINE ─────────────────────────────────────────────────────────────

def run_pipeline(target_date=None):
    if not target_date:
        target_date = date.today().isoformat()

    log.info(f"=== VÉLØ DAILY PIPELINE v{PARSER_VERSION} | {target_date} ===")
    stats = {
        "date": target_date,
        "races_total": 0, "races_ok": 0, "races_fail": 0,
        "runners_ok": 0,  "runners_fail": 0,
        "spotlight_ok": 0, "spotlight_fail": 0,
        "results_ok": 0,  "raw_payloads": 0,
        "write_errors": 0,
    }
    run_id = open_pipeline_run("daily_ingestion", target_date)

    try:
        # ── 1. Fetch racecards ────────────────────────────────────────────────
        params = {"day": "today"}
        log.info(f"Fetching racecards for {target_date}...")
        try:
            resp = requests.get(
                "https://api.theracingapi.com/v1/racecards/standard",
                auth=(RACING_API_USER, RACING_API_PASS),
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            log.error(f"Racing API fetch failed: {exc}")
            close_pipeline_run(run_id, "failed", stats, str(exc))
            return {"status": "FAILED", "error": str(exc)}

        # ── 2. Archive raw payload ────────────────────────────────────────────
        archive_id = archive_payload(run_id, "/v1/racecards/standard", params, target_date, data)
        if archive_id:
            stats["raw_payloads"] += 1

        # ── 3. Filter UK/Ireland ──────────────────────────────────────────────
        racecards = data.get("racecards", [])
        uk_ire = [r for r in racecards if r.get("region", "").upper() in ("GB", "IRE")]
        log.info(f"Total races: {len(racecards)} | UK/Ireland: {len(uk_ire)}")
        stats["races_total"] = len(uk_ire)
        ingested_race_ids = set()

        # ── 4. Process each race ──────────────────────────────────────────────
        for race in uk_ire:
            race_id      = race.get("race_id", "")
            distance_raw = race.get("distance_f", 0)
            distance_int = safe_int(float(str(distance_raw or 0)) * 10) if distance_raw else 0

            upsert_course_profile(race, run_id, stats)

            race_row = {
                "race_id":      race_id,
                "course":       race.get("course", ""),
                "date":         target_date,
                "time":         race.get("off_time", ""),
                "race_type":    race.get("type", ""),
                "distance_f":   distance_int,
                "going":        race.get("going", ""),
                "class":        str(race.get("race_class", "") or ""),
                "prize_money":  clean_prize(race.get("prize")),
                "runners_count": len(race.get("runners", [])),
            }
            ok = supabase_upsert("races", race_row, run_id=run_id, stats=stats)
            if ok:
                stats["races_ok"] += 1
                ingested_race_ids.add(race_id)
            else:
                stats["races_fail"] += 1
                log.warning(f"Race insert failed: {race_id}")

            # ── 5. Process runners ────────────────────────────────────────────
            spotlight_batch = []
            runner_rows     = []

            for runner in race.get("runners", []):
                horse_name    = runner.get("horse", "")
                spotlight_text = runner.get("spotlight", "") or runner.get("comment", "")

                upsert_horse_profile(runner, target_date, run_id, stats)
                upsert_trainer_profile(runner, target_date, run_id, stats)
                upsert_jockey_profile(runner, target_date, run_id, stats)
                upsert_owner_profile(runner, target_date, run_id, stats)
                upsert_runner_race_fact(race, runner, target_date, run_id, stats)

                runner_rows.append({
                    "race_id":    race_id,
                    "horse_name": horse_name,
                    "draw":       safe_int(runner.get("draw")),
                    "weight":     safe_int(runner.get("lbs")),
                    "or_rating":  safe_int(runner.get("ofr")),
                    "ts_rating":  safe_int(runner.get("ts")),
                    "rpr":        safe_int(runner.get("rpr")),
                    "trainer":    runner.get("trainer", ""),
                    "jockey":     runner.get("jockey", ""),
                    "form":       runner.get("form", ""),
                    "rpd_tag":    runner.get("run_style", ""),
                    "rpd_evidence": spotlight_text[:500] if spotlight_text else "",
                    "horse_id":   runner.get("horse_id", ""),
                    "trainer_id": runner.get("trainer_id", ""),
                    "jockey_id":  runner.get("jockey_id", ""),
                    "age":        safe_int(runner.get("age")),
                    "sex":        runner.get("sex", ""),
                    "headgear":   runner.get("headgear", ""),
                    "wind_surgery": True if runner.get("wind_surgery") else None,
                    "wind_surgery_run": safe_int(runner.get("wind_surgery_run")) or None,
                    "sire":       runner.get("sire", ""),
                    "sire_id":    runner.get("sire_id", ""),
                    "dam":        runner.get("dam", ""),
                    "dam_id":     runner.get("dam_id", ""),
                    "damsire":    runner.get("damsire", ""),
                    "damsire_id": runner.get("damsire_id", ""),
                    "owner":      runner.get("owner", ""),
                    "owner_id":   runner.get("owner_id", ""),
                })

                if spotlight_text:
                    parsed = parse_spotlight(spotlight_text, horse_name, race_id, target_date)
                    if parsed:
                        flags_json = {k.replace("flag_", ""): v for k, v in parsed.items() if k.startswith("flag_")}
                        spotlight_batch.append({
                            "race_id":     race_id,
                            "horse_name":  horse_name,
                            "horse_id":    runner.get("horse_id", ""),
                            "comment_raw": spotlight_text[:1000],
                            "spotlight_flags": flags_json,
                            "race_date":   target_date,
                        })

            # Batch write runners
            if runner_rows:
                ok = supabase_upsert("runners", runner_rows, run_id=run_id, stats=stats)
                if ok:
                    stats["runners_ok"] += len(runner_rows)
                else:
                    stats["runners_fail"] += len(runner_rows)

            # Batch write spotlight comments
            if spotlight_batch:
                ok = supabase_upsert("horse_comments", spotlight_batch, run_id=run_id, stats=stats)
                if ok:
                    stats["spotlight_ok"] += len(spotlight_batch)
                else:
                    stats["spotlight_fail"] += len(spotlight_batch)

        mark_payload_parsed(archive_id, "success")

        # ── 6. Results reconciliation (today + prior N days) ──────────────────
        reconcile_dates = [
            (date.fromisoformat(target_date) - timedelta(days=i)).isoformat()
            for i in range(RESULTS_RETRY_DAYS + 1)
        ]
        for rdate in reconcile_dates:
            reconcile_results_for_date(rdate, ingested_race_ids, run_id, stats)

        # ── 7. Close run ──────────────────────────────────────────────────────
        log.info("=== PIPELINE COMPLETE ===")
        log.info(f"Races:      {stats['races_ok']} ok / {stats['races_fail']} failed")
        log.info(f"Runners:    {stats['runners_ok']} ok / {stats['runners_fail']} failed")
        log.info(f"Spotlight:  {stats['spotlight_ok']} ok / {stats['spotlight_fail']} failed")
        log.info(f"Results:    {stats['results_ok']} reconciled")
        log.info(f"Payloads:   {stats['raw_payloads']} archived")
        log.info(f"Errors:     {stats['write_errors']} write errors")

        final_status = "success" if stats["write_errors"] == 0 else "partial"
        close_pipeline_run(run_id, final_status, stats)
        return {"status": "OK", "stats": stats}

    except Exception as exc:
        tb = traceback.format_exc()
        log.error(f"Pipeline crashed: {exc}")
        log.error(tb)
        close_pipeline_run(run_id, "failed", stats, str(exc), tb)
        return {"status": "FAILED", "error": str(exc)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VÉLØ Daily Pipeline v2.2")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today)")
    args = parser.parse_args()
    result = run_pipeline(args.date)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "OK" else 1)
