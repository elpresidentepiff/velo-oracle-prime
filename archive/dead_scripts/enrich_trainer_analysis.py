"""
VELO PRIME -- Trainer Analysis Enrichment Worker
=================================================
Fetches course + distance analysis per trainer from Racing API and writes to:
  - trainer_course_analysis   (PRIMARY KEY: trainer_id, course)
  - trainer_distance_analysis (PRIMARY KEY: trainer_id, dist)

Behaviour:
  - Reads DISTINCT trainer_ids from enrichment_checkpoint where trainer_fetched = false
  - Calls GET /v1/trainers/{trainer_id}/analysis/courses
  - Calls GET /v1/trainers/{trainer_id}/analysis/distances
  - Upserts both result sets
  - Sets trainer_fetched = true ONLY if both endpoints succeed
  - 1 request/sec hard cap
  - Idempotent: re-running is safe
  - Resumable: skips trainers already marked done
  - 404 / not-found: marks as done, logs warning, continues
  - Non-fatal errors: logs, increments error count, continues

Environment variables required:
  RACING_API_USERNAME       -- Basic Auth username
  RACING_API_PASSWORD       -- Basic Auth password
  SUPABASE_URL              -- https://xxx.supabase.co
  SUPABASE_SERVICE_ROLE_KEY -- service role key

Run:
  python scripts/enrich_trainer_analysis.py
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

# -- Logging ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("trainer_analysis")

# -- Config -------------------------------------------------------------------

_raw_base = os.getenv("RACING_API_BASE_URL", "https://api.theracingapi.com")
RACING_API_BASE = _raw_base.rstrip("/").removesuffix("/v1")
RACING_USERNAME = os.getenv("RACING_API_USERNAME")
RACING_PASSWORD = os.getenv("RACING_API_PASSWORD")
SUPABASE_URL    = os.getenv("SUPABASE_URL")
SUPABASE_KEY    = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

RATE_LIMIT_SEC = 1.0


# -- Auth ---------------------------------------------------------------------

def _auth() -> tuple:
    if not RACING_USERNAME or not RACING_PASSWORD:
        raise RuntimeError("RACING_API_USERNAME / RACING_API_PASSWORD not set")
    return (RACING_USERNAME, RACING_PASSWORD)


# -- API fetchers -------------------------------------------------------------

def fetch_course_analysis(trainer_id: str) -> Optional[Dict[str, Any]]:
    """
    GET /v1/trainers/{trainer_id}/analysis/courses
    Returns parsed JSON dict, or None on 404.
    Raises on other non-2xx.
    """
    url = f"{RACING_API_BASE}/v1/trainers/{trainer_id}/analysis/courses"
    resp = requests.get(url, auth=_auth(), timeout=30)
    if resp.status_code == 404:
        log.warning("trainer_id %s not found (courses 404) -- skipping", trainer_id)
        return None
    resp.raise_for_status()
    return resp.json()


def fetch_distance_analysis(trainer_id: str) -> Optional[Dict[str, Any]]:
    """
    GET /v1/trainers/{trainer_id}/analysis/distances
    Returns parsed JSON dict, or None on 404.
    Raises on other non-2xx.
    """
    url = f"{RACING_API_BASE}/v1/trainers/{trainer_id}/analysis/distances"
    resp = requests.get(url, auth=_auth(), timeout=30)
    if resp.status_code == 404:
        log.warning("trainer_id %s not found (distances 404) -- skipping", trainer_id)
        return None
    resp.raise_for_status()
    return resp.json()


# -- Normalisation ------------------------------------------------------------

def _safe_int(val: Any) -> Optional[int]:
    try:
        return int(val) if val not in (None, "", "-", "--") else None
    except (ValueError, TypeError):
        return None


def _safe_numeric(val: Any) -> Optional[float]:
    try:
        return float(val) if val not in (None, "", "-", "--") else None
    except (ValueError, TypeError):
        return None


def normalise_course_rows(
    trainer_id: str, trainer_name: Optional[str], data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Map GET /v1/trainers/{id}/analysis/courses response to trainer_course_analysis rows.

    Expected shape:
      { "courses": [ { "course": str, "course_id": str, "region": str,
                       "runners": int, "1st": int, "2nd": int, "3rd": int, "4th": int,
                       "a/e": float, "win_%": float, "p/l": float }, ... ] }
    """
    rows = []
    for entry in data.get("courses", []):
        course = entry.get("course")
        if not course:
            continue
        rows.append({
            "trainer_id":   trainer_id,
            "trainer_name": trainer_name,
            "course":       course,
            "course_id":    entry.get("course_id"),
            "region":       entry.get("region"),
            "runners":      _safe_int(entry.get("runners")),
            "wins_1st":     _safe_int(entry.get("1st")),
            "wins_2nd":     _safe_int(entry.get("2nd")),
            "wins_3rd":     _safe_int(entry.get("3rd")),
            "wins_4th":     _safe_int(entry.get("4th")),
            "ae":           _safe_numeric(entry.get("a/e")),
            "win_pct":      _safe_numeric(entry.get("win_%")),
            "pl_1":         _safe_numeric(entry.get("p/l")),
            "fetched_at":   datetime.now(timezone.utc).isoformat(),
        })
    return rows


def normalise_distance_rows(
    trainer_id: str, trainer_name: Optional[str], data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Map GET /v1/trainers/{id}/analysis/distances response to trainer_distance_analysis rows.

    Expected shape:
      { "distances": [ { "dist": str, "dist_y": int, "dist_m": float, "dist_f": str,
                         "runners": int, "1st": int, "2nd": int, "3rd": int, "4th": int,
                         "a/e": float, "win_%": float, "p/l": float }, ... ] }
    """
    rows = []
    for entry in data.get("distances", []):
        dist = entry.get("dist")
        if not dist:
            continue
        rows.append({
            "trainer_id":   trainer_id,
            "trainer_name": trainer_name,
            "dist":         dist,
            "dist_y":       _safe_int(entry.get("dist_y")),
            "dist_m":       _safe_int(entry.get("dist_m")),
            "dist_f":       entry.get("dist_f"),
            "runners":      _safe_int(entry.get("runners")),
            "wins_1st":     _safe_int(entry.get("1st")),
            "wins_2nd":     _safe_int(entry.get("2nd")),
            "wins_3rd":     _safe_int(entry.get("3rd")),
            "wins_4th":     _safe_int(entry.get("4th")),
            "ae":           _safe_numeric(entry.get("a/e")),
            "win_pct":      _safe_numeric(entry.get("win_%")),
            "pl_1":         _safe_numeric(entry.get("p/l")),
            "fetched_at":   datetime.now(timezone.utc).isoformat(),
        })
    return rows


# -- Supabase helpers ---------------------------------------------------------

def upsert_course_rows(db: Client, rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    db.table("trainer_course_analysis").upsert(
        rows, on_conflict="trainer_id,course"
    ).execute()
    return len(rows)


def upsert_distance_rows(db: Client, rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    db.table("trainer_distance_analysis").upsert(
        rows, on_conflict="trainer_id,dist"
    ).execute()
    return len(rows)


def mark_trainer_done(db: Client, trainer_id: str) -> None:
    db.table("enrichment_checkpoint").update({
        "trainer_fetched": True,
    }).eq("trainer_id", trainer_id).execute()


def get_pending_trainers(db: Client) -> List[str]:
    """Return distinct trainer_ids where trainer_fetched = false."""
    result = (
        db.table("enrichment_checkpoint")
        .select("trainer_id")
        .eq("trainer_fetched", False)
        .not_.is_("trainer_id", "null")
        .execute()
    )
    seen = set()
    trainers = []
    for row in (result.data or []):
        tid = row.get("trainer_id")
        if tid and tid not in seen:
            seen.add(tid)
            trainers.append(tid)
    return trainers


def get_trainer_name(db: Client, trainer_id: str) -> Optional[str]:
    """Try to resolve trainer name from trainer_profiles."""
    try:
        result = (
            db.table("trainer_profiles")
            .select("trainer")
            .eq("id", trainer_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0].get("trainer")
    except Exception:
        pass
    return None


# -- Main ---------------------------------------------------------------------

def main() -> None:
    for var in ("RACING_API_USERNAME", "RACING_API_PASSWORD", "SUPABASE_URL"):
        if not os.getenv(var):
            log.error("Missing required env var: %s", var)
            sys.exit(1)

    db = create_client(SUPABASE_URL, SUPABASE_KEY)

    pending = get_pending_trainers(db)
    total = len(pending)
    log.info("Trainers pending analysis fetch: %d", total)

    if total == 0:
        log.info("All trainers already fetched -- nothing to do.")
        return

    done = 0
    errors = 0
    course_rows_total = 0
    distance_rows_total = 0

    for i, trainer_id in enumerate(pending, 1):
        log.info("[%d/%d] Fetching analysis for %s", i, total, trainer_id)

        trainer_name = get_trainer_name(db, trainer_id)

        try:
            # -- Courses endpoint --
            time.sleep(RATE_LIMIT_SEC)
            course_data = fetch_course_analysis(trainer_id)

            # -- Distances endpoint --
            time.sleep(RATE_LIMIT_SEC)
            dist_data = fetch_distance_analysis(trainer_id)

            # -- Normalise + upsert --
            if course_data is not None:
                course_rows = normalise_course_rows(trainer_id, trainer_name, course_data)
                c_written = upsert_course_rows(db, course_rows)
                course_rows_total += c_written
            else:
                c_written = 0

            if dist_data is not None:
                dist_rows = normalise_distance_rows(trainer_id, trainer_name, dist_data)
                d_written = upsert_distance_rows(db, dist_rows)
                distance_rows_total += d_written
            else:
                d_written = 0

            log.info("  -> courses: %d rows | distances: %d rows", c_written, d_written)

            # -- Mark done only if both calls completed (even if 404 = 0 rows) --
            mark_trainer_done(db, trainer_id)
            done += 1

        except Exception as exc:
            log.error("  -> FAILED for %s: %s", trainer_id, exc)
            errors += 1
            # Continue -- do not mark done, will retry on next run

        # Rate gap between trainers (2 calls already slept above)
        # No extra sleep needed here

    log.info("=" * 60)
    log.info(
        "Complete. Done: %d  Errors: %d  Total: %d  CourseRows: %d  DistRows: %d",
        done, errors, total, course_rows_total, distance_rows_total,
    )


if __name__ == "__main__":
    main()
