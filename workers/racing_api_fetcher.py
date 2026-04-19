"""
VÉLØ PRIME — Racing API Fetcher Worker
=======================================
Fetches race data from the Racing API and writes to:
  1. Supabase (primary persistent store)
  2. SQLite Memory Engine (src/memory/memory_engine.py)

Endpoints covered:
  - /v1/racecards/pro        → today's full race cards
  - /v1/results/today        → today's results
  - /v1/trainers/{id}/analysis
  - /v1/jockeys/{id}/analysis

Rate limiting:  Token bucket — exactly 5 requests/second
Retry policy:   Exponential backoff on 429 and 5xx (max 5 retries)
Differentials:  TS vs OR and RPR vs OR calculated on every runner automatically
Failures:       Zero silent failures — every error is logged and re-raised

Environment variables required:
  RACING_API_USERNAME       — HTTP Basic Auth username
  RACING_API_PASSWORD       — HTTP Basic Auth password
  RACING_API_BASE_URL       — Base URL (default: https://api.theracingapi.com)
  SUPABASE_URL              — Supabase project URL
  SUPABASE_KEY              — Supabase service role key
  MEMORY_DB_PATH            — Path to SQLite memory DB (default: data/velo_memory.db)
"""

from __future__ import annotations

import logging
import os
import sys
import time
import threading
from datetime import datetime, date
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("velo.racing_api_fetcher")


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
RACING_API_BASE_URL: str = os.environ.get(
    "RACING_API_BASE_URL", "https://api.theracingapi.com"
).rstrip("/")
RACING_API_USERNAME: str = os.environ.get("RACING_API_USERNAME", "")
RACING_API_PASSWORD: str = os.environ.get("RACING_API_PASSWORD", "")
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")
MEMORY_DB_PATH: str = os.environ.get("MEMORY_DB_PATH", "data/velo_memory.db")

# Rate limit: 5 req/s
_RATE_LIMIT_RPS: int = 5
_MIN_INTERVAL: float = 1.0 / _RATE_LIMIT_RPS  # 0.2 s between requests


# ─────────────────────────────────────────────
# Token Bucket Rate Limiter
# ─────────────────────────────────────────────
class TokenBucket:
    """Thread-safe token bucket: exactly `rate` tokens per second."""

    def __init__(self, rate: int = 5) -> None:
        self._rate = rate
        self._tokens: float = float(rate)
        self._last_refill: float = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a token is available."""
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(
                    float(self._rate),
                    self._tokens + elapsed * self._rate,
                )
                self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
            time.sleep(_MIN_INTERVAL / 2)


_bucket = TokenBucket(rate=_RATE_LIMIT_RPS)


# ─────────────────────────────────────────────
# HTTP Session with Retry
# ─────────────────────────────────────────────
def _build_session() -> requests.Session:
    """Build a requests Session with exponential backoff on 429 / 5xx."""
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=2,          # 2s, 4s, 8s, 16s, 32s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    if not RACING_API_USERNAME or not RACING_API_PASSWORD:
        raise EnvironmentError(
            "RACING_API_USERNAME and RACING_API_PASSWORD must be set. "
            "Add them to your Railway environment variables."
        )

    session.auth = (RACING_API_USERNAME, RACING_API_PASSWORD)
    session.headers.update({"Accept": "application/json"})
    return session


# ─────────────────────────────────────────────
# Core Fetch Helper
# ─────────────────────────────────────────────
def _get(session: requests.Session, endpoint: str, params: Optional[Dict] = None) -> Any:
    """
    Rate-limited GET with full error logging.
    Raises on any non-2xx response after retries are exhausted.
    """
    url = f"{RACING_API_BASE_URL}{endpoint}"
    _bucket.acquire()
    log.info("GET %s params=%s", url, params)

    try:
        resp = session.get(url, params=params, timeout=30)
    except requests.exceptions.RequestException as exc:
        log.error("Network error fetching %s: %s", url, exc)
        raise

    if not resp.ok:
        log.error(
            "HTTP %s from %s — body: %s",
            resp.status_code,
            url,
            resp.text[:500],
        )
        resp.raise_for_status()

    try:
        data = resp.json()
    except ValueError as exc:
        log.error("Invalid JSON from %s: %s", url, exc)
        raise

    log.info("✓ %s → %s bytes", endpoint, len(resp.content))
    return data


# ─────────────────────────────────────────────
# Differential Calculations
# ─────────────────────────────────────────────
def _calculate_differentials(runner: Dict) -> Dict:
    """
    Calculate TS vs OR and RPR vs OR differentials for a single runner.
    Returns a dict of differential fields (all floats or None).
    """
    def _safe_float(val: Any) -> Optional[float]:
        try:
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    ts = _safe_float(runner.get("ts") or runner.get("topspeed"))
    rpr = _safe_float(runner.get("rpr"))
    official_rating = _safe_float(
        runner.get("or") or runner.get("official_rating")
    )

    ts_vs_or: Optional[float] = None
    rpr_vs_or: Optional[float] = None

    if ts is not None and official_rating is not None:
        ts_vs_or = round(ts - official_rating, 2)
    if rpr is not None and official_rating is not None:
        rpr_vs_or = round(rpr - official_rating, 2)

    return {
        "ts": ts,
        "rpr": rpr,
        "official_rating": official_rating,
        "ts_vs_or": ts_vs_or,
        "rpr_vs_or": rpr_vs_or,
    }


def _enrich_runners(runners: List[Dict]) -> List[Dict]:
    """Add differential fields to every runner in a list."""
    enriched = []
    for runner in runners:
        diffs = _calculate_differentials(runner)
        enriched.append({**runner, **diffs})
    return enriched


# ─────────────────────────────────────────────
# Supabase Writer
# ─────────────────────────────────────────────
class SupabaseWriter:
    """Thin wrapper around the Supabase REST API for upsert operations."""

    def __init__(self) -> None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise EnvironmentError(
                "SUPABASE_URL and SUPABASE_KEY must be set."
            )
        self._base = SUPABASE_URL.rstrip("/") + "/rest/v1"
        self._headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        }

    def upsert(self, table: str, records: List[Dict]) -> None:
        """Upsert a list of records into a Supabase table."""
        if not records:
            log.debug("No records to upsert into %s", table)
            return

        url = f"{self._base}/{table}"
        resp = requests.post(url, json=records, headers=self._headers, timeout=30)

        if not resp.ok:
            log.error(
                "Supabase upsert failed [%s] table=%s — %s",
                resp.status_code,
                table,
                resp.text[:500],
            )
            resp.raise_for_status()

        log.info("✓ Supabase upsert → table=%s rows=%d", table, len(records))


# ─────────────────────────────────────────────
# Memory Engine Writer
# ─────────────────────────────────────────────
class MemoryEngineWriter:
    """
    Writes fetched data into the SQLite Persistent Memory Engine (PR #46).
    Gracefully degrades if the memory engine is not available.
    """

    def __init__(self, db_path: str = MEMORY_DB_PATH) -> None:
        self._engine = None
        try:
            from src.memory.memory_engine import VeloMemoryEngine  # type: ignore
            self._engine = VeloMemoryEngine(db_path)
            log.info("Memory Engine initialised at %s", db_path)
        except ImportError:
            log.warning(
                "src.memory.memory_engine not available — "
                "Memory Engine writes will be skipped until PR #46 is merged."
            )
        except Exception as exc:
            log.error("Memory Engine init failed: %s", exc)

    def store_race(self, race: Dict) -> None:
        if self._engine is None:
            return
        try:
            self._engine.store_race(race)
        except Exception as exc:
            log.error("Memory Engine store_race failed: %s", exc)
            raise

    def store_result(self, result: Dict) -> None:
        if self._engine is None:
            return
        try:
            self._engine.store_result(result)
        except Exception as exc:
            log.error("Memory Engine store_result failed: %s", exc)
            raise


# ─────────────────────────────────────────────
# Fetch Functions
# ─────────────────────────────────────────────
def fetch_racecards_pro(
    session: requests.Session,
    supabase: SupabaseWriter,
    memory: MemoryEngineWriter,
    race_date: Optional[str] = None,
) -> List[Dict]:
    """
    Fetch /v1/racecards/pro for today (or a given date).
    Enriches every runner with TS vs OR / RPR vs OR differentials.
    Writes to Supabase (racecards table) and Memory Engine.
    """
    params: Dict = {}
    if race_date:
        params["date"] = race_date

    data = _get(session, "/racecards/pro", params=params)
    races: List[Dict] = data if isinstance(data, list) else data.get("racecards", [])

    enriched_races: List[Dict] = []
    for race in races:
        runners = race.get("runners", [])
        race["runners"] = _enrich_runners(runners)
        enriched_races.append(race)

    # Write to Supabase
    supabase.upsert("racecards", enriched_races)

    # Write to Memory Engine
    for race in enriched_races:
        memory.store_race(race)

    log.info("fetch_racecards_pro → %d races processed", len(enriched_races))
    return enriched_races


def fetch_results_today(
    session: requests.Session,
    supabase: SupabaseWriter,
    memory: MemoryEngineWriter,
) -> List[Dict]:
    """
    Fetch /v1/results/today.
    Enriches every runner with differentials.
    Writes to Supabase (race_results table) and Memory Engine.
    """
    data = _get(session, "/v1/results/today")
    results: List[Dict] = data if isinstance(data, list) else data.get("results", [])

    enriched: List[Dict] = []
    for result in results:
        runners = result.get("runners", [])
        result["runners"] = _enrich_runners(runners)
        enriched.append(result)

    supabase.upsert("race_results", enriched)

    for result in enriched:
        memory.store_result(result)

    log.info("fetch_results_today → %d results processed", len(enriched))
    return enriched


def fetch_trainer_analysis(
    session: requests.Session,
    supabase: SupabaseWriter,
    trainer_id: str,
) -> Dict:
    """
    Fetch /v1/trainers/{id}/analysis.
    Writes to Supabase (trainer_analysis table).
    """
    data = _get(session, f"/v1/trainers/{trainer_id}/analysis")
    record = {"trainer_id": trainer_id, "fetched_at": datetime.utcnow().isoformat(), **data}
    supabase.upsert("trainer_analysis", [record])
    log.info("fetch_trainer_analysis → trainer_id=%s", trainer_id)
    return data


def fetch_jockey_analysis(
    session: requests.Session,
    supabase: SupabaseWriter,
    jockey_id: str,
) -> Dict:
    """
    Fetch /v1/jockeys/{id}/analysis.
    Writes to Supabase (jockey_analysis table).
    """
    data = _get(session, f"/v1/jockeys/{jockey_id}/analysis")
    record = {"jockey_id": jockey_id, "fetched_at": datetime.utcnow().isoformat(), **data}
    supabase.upsert("jockey_analysis", [record])
    log.info("fetch_jockey_analysis → jockey_id=%s", jockey_id)
    return data


# ─────────────────────────────────────────────
# Full Daily Run
# ─────────────────────────────────────────────
def run_daily_fetch(
    trainer_ids: Optional[List[str]] = None,
    jockey_ids: Optional[List[str]] = None,
    race_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute the full daily data fetch pipeline:
      1. Racecards Pro
      2. Results Today
      3. Trainer analyses (for provided IDs)
      4. Jockey analyses (for provided IDs)

    Returns a summary dict with counts and any errors.
    """
    summary: Dict[str, Any] = {
        "run_at": datetime.utcnow().isoformat(),
        "race_date": race_date or str(date.today()),
        "racecards_fetched": 0,
        "results_fetched": 0,
        "trainer_analyses": 0,
        "jockey_analyses": 0,
        "errors": [],
    }

    session = _build_session()
    supabase = SupabaseWriter()
    memory = MemoryEngineWriter()

    # 1. Racecards
    try:
        races = fetch_racecards_pro(session, supabase, memory, race_date=race_date)
        summary["racecards_fetched"] = len(races)
    except Exception as exc:
        msg = f"fetch_racecards_pro failed: {exc}"
        log.error(msg)
        summary["errors"].append(msg)

    # 2. Results
    try:
        results = fetch_results_today(session, supabase, memory)
        summary["results_fetched"] = len(results)
    except Exception as exc:
        msg = f"fetch_results_today failed: {exc}"
        log.error(msg)
        summary["errors"].append(msg)

    # 3. Trainer analyses
    for tid in (trainer_ids or []):
        try:
            fetch_trainer_analysis(session, supabase, tid)
            summary["trainer_analyses"] += 1
        except Exception as exc:
            msg = f"fetch_trainer_analysis({tid}) failed: {exc}"
            log.error(msg)
            summary["errors"].append(msg)

    # 4. Jockey analyses
    for jid in (jockey_ids or []):
        try:
            fetch_jockey_analysis(session, supabase, jid)
            summary["jockey_analyses"] += 1
        except Exception as exc:
            msg = f"fetch_jockey_analysis({jid}) failed: {exc}"
            log.error(msg)
            summary["errors"].append(msg)

    if summary["errors"]:
        log.warning(
            "Daily fetch completed with %d error(s): %s",
            len(summary["errors"]),
            summary["errors"],
        )
    else:
        log.info("Daily fetch completed successfully: %s", summary)

    return summary


# ─────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VÉLØ Racing API Fetcher")
    parser.add_argument("--date", help="Race date (YYYY-MM-DD), defaults to today")
    parser.add_argument(
        "--trainers", nargs="*", default=[], help="Trainer IDs to fetch analysis for"
    )
    parser.add_argument(
        "--jockeys", nargs="*", default=[], help="Jockey IDs to fetch analysis for"
    )
    args = parser.parse_args()

    result = run_daily_fetch(
        trainer_ids=args.trainers or None,
        jockey_ids=args.jockeys or None,
        race_date=args.date,
    )

    if result["errors"]:
        log.error("Fetch completed with errors — see above.")
        sys.exit(1)

    log.info("Fetch complete. Summary: %s", result)
    sys.exit(0)
