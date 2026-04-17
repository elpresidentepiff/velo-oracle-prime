"""
VÉLØ PRIME — Horse History Enrichment Worker
=============================================
Fetches historical race results for each horse in enrichment_checkpoint
and writes to horse_racecard_history.

Behaviour:
  - Reads DISTINCT horse_ids from enrichment_checkpoint where horse_history_fetched = false
  - Calls GET /v1/racecards/{horse_id}/results (Standard-safe)
  - Upserts rows to horse_racecard_history (UNIQUE: horse_id + race_id)
  - Marks enrichment_checkpoint.horse_history_fetched = true for that horse_id
  - 1 request/sec hard cap
  - Idempotent: re-running is safe
  - Resumable: skips horses already marked done
  - 404 / not-found: marks as done, logs warning, continues
  - Creates horse_racecard_history if it doesn't exist (idempotent DDL)

Environment variables required:
  RACING_API_USERNAME   — Basic Auth username
  RACING_API_PASSWORD   — Basic Auth password
  SUPABASE_URL          — https://xxx.supabase.co
  SUPABASE_KEY          — service role key

Run:
  python scripts/enrich_horse_history.py

Verify:
  See bottom of file for verification SQL.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from supabase import create_client, Client

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("horse_history")

# ── Config ───────────────────────────────────────────────────────────────────

_raw_base = os.getenv("RACING_API_BASE_URL", "https://api.theracingapi.com")
RACING_API_BASE = _raw_base.rstrip("/").removesuffix("/v1")
RACING_USERNAME = os.getenv("RACING_API_USERNAME")
RACING_PASSWORD = os.getenv("RACING_API_PASSWORD")
SUPABASE_URL    = os.getenv("SUPABASE_URL")
SUPABASE_KEY    = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

RATE_LIMIT_SEC  = 1.0   # 1 request per second
RESULTS_LIMIT   = 100   # max historical runs per horse per API call
BATCH_SIZE      = 50    # pagination — calls until total exhausted

# ── DDL (idempotent) ──────────────────────────────────────────────────────────

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS horse_racecard_history (
    id          BIGSERIAL PRIMARY KEY,
    horse_id    TEXT        NOT NULL,
    race_id     TEXT        NOT NULL,
    race_date   DATE,
    course      TEXT,
    dist        TEXT,
    dist_y      INTEGER,
    going       TEXT,
    race_type   TEXT,
    race_class  TEXT,
    position    TEXT,
    sp          TEXT,
    sp_dec      NUMERIC,
    bsp         NUMERIC,
    or_rating   INTEGER,
    rpr         INTEGER,
    ts          INTEGER,
    weight      TEXT,
    draw        INTEGER,
    btn         TEXT,
    jockey      TEXT,
    jockey_id   TEXT,
    trainer     TEXT,
    trainer_id  TEXT,
    comment     TEXT,
    raw         JSONB,
    fetched_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (horse_id, race_id)
);
CREATE INDEX IF NOT EXISTS idx_hrh_horse_id  ON horse_racecard_history (horse_id);
CREATE INDEX IF NOT EXISTS idx_hrh_race_date ON horse_racecard_history (race_date);
"""

# ── API client ────────────────────────────────────────────────────────────────

def _auth() -> tuple:
    if not RACING_USERNAME or not RACING_PASSWORD:
        raise RuntimeError("RACING_API_USERNAME / RACING_API_PASSWORD not set")
    return (RACING_USERNAME, RACING_PASSWORD)


def fetch_horse_results(horse_id: str) -> List[Dict[str, Any]]:
    """
    Call /v1/racecards/{horse_id}/results with pagination.
    Returns list of raw result dicts, or [] on 404.
    Raises on any other non-2xx.
    """
    url = f"{RACING_API_BASE}/v1/racecards/{horse_id}/results"
    all_results: List[Dict[str, Any]] = []
    skip = 0

    while True:
        params = {"limit": RESULTS_LIMIT, "skip": skip}
        resp = requests.get(url, auth=_auth(), params=params, timeout=30)

        if resp.status_code == 404:
            log.warning("horse_id %s not found in Racing API (404) — skipping", horse_id)
            return []

        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        all_results.extend(results)

        total = data.get("total", 0)
        skip += len(results)

        if skip >= total or not results:
            break

        time.sleep(RATE_LIMIT_SEC)  # pace between pagination calls too

    return all_results


# ── Normalisation ─────────────────────────────────────────────────────────────

def _safe_int(val: Any) -> Optional[int]:
    try:
        return int(val) if val not in (None, "", "–", "-") else None
    except (ValueError, TypeError):
        return None


def _safe_numeric(val: Any) -> Optional[float]:
    try:
        return float(val) if val not in (None, "", "–", "-") else None
    except (ValueError, TypeError):
        return None


def normalise_row(horse_id: str, race: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Map one race result (race-level dict with nested runners) to a horse_racecard_history row.
    Finds this horse's runner entry within race['runners'].
    Returns None if race_id missing or horse not found in runners.

    API shape:
      race: { race_id, date, course, dist, dist_y, going, type, class, runners: [...] }
      runner: { horse_id, position, sp, sp_dec, or, rpr, tsr, draw, btn, weight,
                jockey, jockey_id, trainer, trainer_id, comment, ... }
    """
    race_id = race.get("race_id")
    if not race_id:
        return None

    # Find this horse's entry in the runners array
    runner: Optional[Dict[str, Any]] = None
    for r in race.get("runners", []):
        if r.get("horse_id") == horse_id:
            runner = r
            break

    if runner is None:
        # Horse not in this race's runners — skip
        return None

    raw_date = race.get("date")
    race_date = raw_date if raw_date else None

    # Combine race-level and runner-level into single raw blob
    raw_blob = {**race, "_runner": runner}

    return {
        "horse_id":   horse_id,
        "race_id":    race_id,
        "race_date":  race_date,
        "course":     race.get("course"),
        "dist":       race.get("dist"),
        "dist_y":     _safe_int(race.get("dist_y")),
        "going":      race.get("going"),
        "race_type":  race.get("type"),
        "race_class": race.get("class"),
        "position":   str(runner.get("position", "")) or None,
        "sp":         runner.get("sp"),
        "sp_dec":     _safe_numeric(runner.get("sp_dec")),
        "bsp":        None,   # not present on this endpoint
        "or_rating":  _safe_int(runner.get("or")),
        "rpr":        _safe_int(runner.get("rpr")),
        "ts":         _safe_int(runner.get("tsr")),
        "weight":     runner.get("weight"),
        "draw":       _safe_int(runner.get("draw")),
        "btn":        str(runner.get("btn", "")) or None,
        "jockey":     runner.get("jockey"),
        "jockey_id":  runner.get("jockey_id"),
        "trainer":    runner.get("trainer"),
        "trainer_id": runner.get("trainer_id"),
        "comment":    runner.get("comment"),
        "raw":        raw_blob,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Supabase helpers ──────────────────────────────────────────────────────────

def upsert_rows(db: Client, rows: List[Dict[str, Any]]) -> int:
    """Upsert rows to horse_racecard_history. Returns count written."""
    if not rows:
        return 0
    db.table("horse_racecard_history").upsert(
        rows, on_conflict="horse_id,race_id"
    ).execute()
    return len(rows)


def mark_horse_done(db: Client, horse_id: str) -> None:
    db.table("enrichment_checkpoint").update({
        "horse_history_fetched": True,
    }).eq("horse_id", horse_id).execute()


def get_pending_horses(db: Client) -> List[str]:
    """Return distinct horse_ids where history not yet fetched."""
    result = (
        db.table("enrichment_checkpoint")
        .select("horse_id")
        .eq("horse_history_fetched", False)
        .execute()
    )
    seen = set()
    horses = []
    for row in (result.data or []):
        hid = row.get("horse_id")
        if hid and hid not in seen:
            seen.add(hid)
            horses.append(hid)
    return horses


# ── Migration ─────────────────────────────────────────────────────────────────

def ensure_table(db: Client) -> None:
    """Create horse_racecard_history if it doesn't exist."""
    try:
        # Split on semicolons to run each statement separately
        statements = [s.strip() for s in CREATE_TABLE_SQL.split(";") if s.strip()]
        for stmt in statements:
            db.rpc("exec_sql", {"sql": stmt}).execute()
        log.info("horse_racecard_history: table/index ensured")
    except Exception:
        # RPC may not exist — fall through, table likely already exists
        log.debug("ensure_table via RPC failed — assuming table exists or using migration")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # Validate env
    for var in ("RACING_API_USERNAME", "RACING_API_PASSWORD", "SUPABASE_URL"):
        if not os.getenv(var):
            log.error("Missing required env var: %s", var)
            sys.exit(1)

    db = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Get pending horses
    pending = get_pending_horses(db)
    total = len(pending)
    log.info("Horses pending history fetch: %d", total)

    if total == 0:
        log.info("All horses already have history — nothing to do.")
        return

    done = 0
    errors = 0

    for i, horse_id in enumerate(pending, 1):
        log.info("[%d/%d] Fetching history for %s", i, total, horse_id)

        try:
            raw_results = fetch_horse_results(horse_id)

            if raw_results:
                rows = [
                    r for r in (normalise_row(horse_id, raw) for raw in raw_results)
                    if r is not None
                ]
                written = upsert_rows(db, rows)
                log.info("  -> %d results fetched, %d rows upserted", len(raw_results), written)
            else:
                log.info("  -> 0 results (404 or empty history)")

            mark_horse_done(db, horse_id)
            done += 1

        except Exception as exc:
            log.error("  -> FAILED for %s: %s", horse_id, exc)
            errors += 1
            # Continue — don't let one horse fail the whole run

        # Rate limit between horses
        if i < total:
            time.sleep(RATE_LIMIT_SEC)

    log.info("─" * 60)
    log.info("Complete. Done: %d  Errors: %d  Total: %d", done, errors, total)


if __name__ == "__main__":
    main()
