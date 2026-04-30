"""
Racing API Shadow Enrichment — Phase 5 Forward-Test Shadow Logging
==================================================================
Computes Racing API shadow enrichment scores for forward-test ledger.

GOVERNANCE:
  - Logged fields ONLY. Never alters velo_prime_prob, tier, product, router.
  - min runners/rides >= MIN_RUNNERS enforced at cache-build time.
  - Missing groups → null. Never defaults to 0.
  - pnl excluded as primary signal (near-zero correlation, v1+v2 confirmed).
  - shadow_version = RACING_API_ANALYSIS_V1
  - leakage_status = RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK

Usage:
    caches = load_enrichment_caches(sb_url, sb_key)          # once per run
    fields = compute_shadow_enrichment(trainer_id, jockey_id,
                                       course_name, dist_f_raw, caches)
    top.update(fields)    # attach to verdict — does NOT alter scoring fields
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("velo.racing_api_shadow")

SHADOW_VERSION = "RACING_API_ANALYSIS_V1"
LEAKAGE_STATUS = "RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK"
MIN_RUNNERS = 10
_BATCH = 1000

# ── Distance normalisation ───────────────────────────────────────────────────
# races.distance_f has 3 storage formats:
#   ≤ 40   → integer furlongs      (e.g.  8 → 8.0f = 1m)
#   41–500 → tenths of furlongs    (e.g. 95 → 9.5f = 1m1½f)
#   > 500  → yards                 (e.g. 1760 → 8.0f = 1m)
_DIST_MAP: dict[float, str] = {
    4.5: "4½f",
    5.0: "5f",   5.5: "5½f",
    6.0: "6f",   6.5: "6½f",
    7.0: "7f",   7.5: "7½f",
    8.0: "1m",   8.5: "1m½f",
    9.0: "1m1f", 9.5: "1m1½f",
    10.0: "1m2f", 10.5: "1m2½f",
    11.0: "1m3f", 11.5: "1m3½f",
    12.0: "1m4f", 12.5: "1m4½f",
    13.0: "1m5f", 13.5: "1m5½f",
    14.0: "1m6f", 14.5: "1m6½f",
    15.0: "1m7f", 15.5: "1m7½f",
    16.0: "2m",   16.5: "2m½f",
    17.0: "2m1f", 17.5: "2m1½f",
    18.0: "2m2f", 18.5: "2m2½f",
    19.0: "2m3f", 19.5: "2m3½f",
    20.0: "2m4f", 20.5: "2m4½f",
    21.0: "2m5f", 21.5: "2m5½f",
    22.0: "2m6f", 22.5: "2m6½f",
    23.0: "2m7f", 23.5: "2m7½f",
    24.0: "3m",   24.5: "3m½f",
    25.0: "3m1f", 25.5: "3m1½f",
    26.0: "3m2f", 26.5: "3m2½f",
    27.0: "3m3f", 27.5: "3m3½f",
    28.0: "3m4f", 28.5: "3m4½f",
    29.0: "3m5f", 29.5: "3m5½f",
    30.0: "3m6f", 30.5: "3m6½f",
    31.0: "3m7f", 31.5: "3m7½f",
    32.0: "4m",   32.5: "4m½f",
    33.0: "4m1f", 33.5: "4m1½f",
    34.0: "4m2f", 34.5: "4m2½f",
    35.0: "4m3f",
    36.0: "4m4f",
}


def normalize_distance_f(raw: Any) -> float | None:
    """Convert races.distance_f (any storage unit) → float furlongs."""
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    if v <= 40:
        return v
    elif v <= 500:
        return v / 10.0
    else:
        return v / 220.0


def furlongs_to_dist_string(f: float | None) -> str | None:
    """Map furlongs float → Racing API dist string (±0.6f tolerance)."""
    if f is None:
        return None
    closest = min(_DIST_MAP, key=lambda k: abs(k - f))
    if abs(closest - f) <= 0.6:
        return _DIST_MAP[closest]
    return None


def dist_f_to_api_string(raw: Any) -> str | None:
    """Full pipeline: raw distance_f → furlongs → Racing API dist string."""
    return furlongs_to_dist_string(normalize_distance_f(raw))


# ── Cache types ──────────────────────────────────────────────────────────────

@dataclass
class RacingApiEnrichmentCaches:
    """Six in-memory lookup caches, keyed per Racing API endpoint family."""
    trainer_course:   dict[tuple[str, str], dict] = field(default_factory=dict)
    trainer_distance: dict[tuple[str, str], dict] = field(default_factory=dict)
    trainer_jockey:   dict[tuple[str, str], dict] = field(default_factory=dict)
    jockey_course:    dict[tuple[str, str], dict] = field(default_factory=dict)
    jockey_distance:  dict[tuple[str, str], dict] = field(default_factory=dict)
    jockey_trainer:   dict[tuple[str, str], dict] = field(default_factory=dict)
    load_ok: bool = False


def _fetch_all(sb_url: str, sb_key: str, table: str, select: str) -> list[dict]:
    """Paginated REST fetch — returns all rows regardless of table size."""
    base = sb_url.rstrip("/")
    hdrs = {
        "apikey": sb_key,
        "Authorization": f"Bearer {sb_key}",
        "Accept": "application/json",
    }
    rows: list[dict] = []
    offset = 0
    while True:
        url = (
            f"{base}/rest/v1/{table}"
            f"?select={select}&limit={_BATCH}&offset={offset}"
        )
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=60) as r:
                batch = json.loads(r.read().decode())
        except Exception as exc:
            log.warning("Racing API cache fetch error table=%s offset=%d: %s", table, offset, exc)
            break
        if not isinstance(batch, list) or not batch:
            break
        rows.extend(batch)
        if len(batch) < _BATCH:
            break
        offset += _BATCH
    return rows


def load_enrichment_caches(sb_url: str, sb_key: str) -> RacingApiEnrichmentCaches:
    """
    Load all six Racing API analysis tables into memory.
    Filters to MIN_RUNNERS threshold at load time.
    Call once per run — not per race.
    """
    caches = RacingApiEnrichmentCaches()

    try:
        # Trainer × course
        rows = _fetch_all(sb_url, sb_key,
                          "racing_api_trainer_analysis_courses",
                          "entity_id,course,runners_or_rides,win_pct,ae_ratio")
        for r in rows:
            if (r.get("runners_or_rides") or 0) >= MIN_RUNNERS and r.get("entity_id") and r.get("course"):
                caches.trainer_course[(r["entity_id"], r["course"].lower())] = r
        log.info("racing_api shadow: trainer_course cache %d entries", len(caches.trainer_course))

        # Trainer × distance
        rows = _fetch_all(sb_url, sb_key,
                          "racing_api_trainer_analysis_distances",
                          "entity_id,dist,runners_or_rides,win_pct,ae_ratio")
        for r in rows:
            if (r.get("runners_or_rides") or 0) >= MIN_RUNNERS and r.get("entity_id") and r.get("dist"):
                caches.trainer_distance[(r["entity_id"], r["dist"].lower())] = r
        log.info("racing_api shadow: trainer_distance cache %d entries", len(caches.trainer_distance))

        # Trainer × jockey
        rows = _fetch_all(sb_url, sb_key,
                          "racing_api_trainer_analysis_jockeys",
                          "entity_id,jockey_id,runners_or_rides,win_pct,ae_ratio")
        for r in rows:
            if (r.get("runners_or_rides") or 0) >= MIN_RUNNERS and r.get("entity_id") and r.get("jockey_id"):
                caches.trainer_jockey[(r["entity_id"], r["jockey_id"])] = r
        log.info("racing_api shadow: trainer_jockey cache %d entries", len(caches.trainer_jockey))

        # Jockey × course
        rows = _fetch_all(sb_url, sb_key,
                          "racing_api_jockey_analysis_courses",
                          "entity_id,course,runners_or_rides,win_pct,ae_ratio")
        for r in rows:
            if (r.get("runners_or_rides") or 0) >= MIN_RUNNERS and r.get("entity_id") and r.get("course"):
                caches.jockey_course[(r["entity_id"], r["course"].lower())] = r
        log.info("racing_api shadow: jockey_course cache %d entries", len(caches.jockey_course))

        # Jockey × distance
        rows = _fetch_all(sb_url, sb_key,
                          "racing_api_jockey_analysis_distances",
                          "entity_id,dist,runners_or_rides,win_pct,ae_ratio")
        for r in rows:
            if (r.get("runners_or_rides") or 0) >= MIN_RUNNERS and r.get("entity_id") and r.get("dist"):
                caches.jockey_distance[(r["entity_id"], r["dist"].lower())] = r
        log.info("racing_api shadow: jockey_distance cache %d entries", len(caches.jockey_distance))

        # Jockey × trainer
        rows = _fetch_all(sb_url, sb_key,
                          "racing_api_jockey_analysis_trainers",
                          "entity_id,trainer_id,runners_or_rides,win_pct,ae_ratio")
        for r in rows:
            if (r.get("runners_or_rides") or 0) >= MIN_RUNNERS and r.get("entity_id") and r.get("trainer_id"):
                caches.jockey_trainer[(r["entity_id"], r["trainer_id"])] = r
        log.info("racing_api shadow: jockey_trainer cache %d entries", len(caches.jockey_trainer))

        caches.load_ok = True
        log.info("racing_api shadow: all caches loaded OK")

    except Exception as exc:
        log.error("racing_api shadow: cache load failed — %s", exc)
        caches.load_ok = False

    return caches


# ── Score computation ─────────────────────────────────────────────────────────

def _mean(vals: list[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None


def _shadow_score(wp_vals: list[float], ae_vals: list[float]) -> float | None:
    """0.6 × mean(win_pct) + 0.4 × mean(ae_ratio). Returns null if no data."""
    avg_wp = _mean(wp_vals)
    if avg_wp is None:
        return None
    avg_ae = _mean(ae_vals) if ae_vals else 1.0
    return round(0.6 * avg_wp + 0.4 * avg_ae, 4)


def compute_shadow_enrichment(
    trainer_id: str | None,
    jockey_id: str | None,
    course_name: str | None,
    dist_f_raw: Any,
    caches: RacingApiEnrichmentCaches,
) -> dict[str, Any]:
    """
    Compute Racing API shadow enrichment fields for a single verdict.

    Returns a dict of shadow fields only — call top.update(fields).
    NEVER alters velo_prime_prob, tier, assigned_product, or router fields.
    All scores null when data is absent or insufficient.
    """
    if not caches.load_ok:
        return {
            "racing_api_shadow_version": SHADOW_VERSION,
            "racing_api_shadow_leakage_status": LEAKAGE_STATUS,
            "racing_api_shadow_load_status": "caches_not_loaded",
        }

    course = (course_name or "").lower().strip()
    dist_str = dist_f_to_api_string(dist_f_raw)

    # ── Connection signal (trainer↔jockey combos) ─────────────────────────
    conn_wp: list[float] = []
    conn_ae: list[float] = []
    conn_coverage: list[str] = []

    if trainer_id and jockey_id:
        tj = caches.trainer_jockey.get((trainer_id, jockey_id))
        if tj:
            wp = tj.get("win_pct")
            ae = tj.get("ae_ratio")
            if wp is not None:
                conn_wp.append(float(wp))
                conn_coverage.append("trainer_jockey")
            if ae is not None:
                conn_ae.append(float(ae))

    if jockey_id and trainer_id:
        jt = caches.jockey_trainer.get((jockey_id, trainer_id))
        if jt:
            wp = jt.get("win_pct")
            ae = jt.get("ae_ratio")
            if wp is not None:
                conn_wp.append(float(wp))
                if "jockey_trainer" not in conn_coverage:
                    conn_coverage.append("jockey_trainer")
            if ae is not None:
                conn_ae.append(float(ae))

    conn_score = _shadow_score(conn_wp, conn_ae)

    # ── Course signal ─────────────────────────────────────────────────────
    crs_wp: list[float] = []
    crs_ae: list[float] = []
    crs_coverage: list[str] = []

    if trainer_id and course:
        tc = caches.trainer_course.get((trainer_id, course))
        if tc:
            wp = tc.get("win_pct")
            ae = tc.get("ae_ratio")
            if wp is not None:
                crs_wp.append(float(wp))
                crs_coverage.append("trainer_course")
            if ae is not None:
                crs_ae.append(float(ae))

    if jockey_id and course:
        jc = caches.jockey_course.get((jockey_id, course))
        if jc:
            wp = jc.get("win_pct")
            ae = jc.get("ae_ratio")
            if wp is not None:
                crs_wp.append(float(wp))
                if "jockey_course" not in crs_coverage:
                    crs_coverage.append("jockey_course")
            if ae is not None:
                crs_ae.append(float(ae))

    crs_score = _shadow_score(crs_wp, crs_ae)

    # ── Distance signal ───────────────────────────────────────────────────
    dst_wp: list[float] = []
    dst_ae: list[float] = []
    dst_coverage: list[str] = []

    if trainer_id and dist_str:
        td = caches.trainer_distance.get((trainer_id, dist_str))
        if td:
            wp = td.get("win_pct")
            ae = td.get("ae_ratio")
            if wp is not None:
                dst_wp.append(float(wp))
                dst_coverage.append("trainer_distance")
            if ae is not None:
                dst_ae.append(float(ae))

    if jockey_id and dist_str:
        jd = caches.jockey_distance.get((jockey_id, dist_str))
        if jd:
            wp = jd.get("win_pct")
            ae = jd.get("ae_ratio")
            if wp is not None:
                dst_wp.append(float(wp))
                if "jockey_distance" not in dst_coverage:
                    dst_coverage.append("jockey_distance")
            if ae is not None:
                dst_ae.append(float(ae))

    dst_score = _shadow_score(dst_wp, dst_ae)

    # ── Overall enrichment signal (all available) ─────────────────────────
    all_wp = conn_wp + crs_wp + dst_wp
    all_ae = conn_ae + crs_ae + dst_ae
    enr_score = _shadow_score(all_wp, all_ae)
    enr_coverage = conn_coverage + crs_coverage + dst_coverage

    return {
        "racing_api_connection_shadow_score": conn_score,
        "racing_api_course_shadow_score": crs_score,
        "racing_api_distance_shadow_score": dst_score,
        "racing_api_enrichment_shadow_score": enr_score,
        "racing_api_connection_coverage": conn_coverage or None,
        "racing_api_course_coverage": crs_coverage or None,
        "racing_api_distance_coverage": dst_coverage or None,
        "racing_api_enrichment_coverage": enr_coverage or None,
        "racing_api_shadow_version": SHADOW_VERSION,
        "racing_api_shadow_leakage_status": LEAKAGE_STATUS,
    }


# ── Forward ledger ────────────────────────────────────────────────────────────

_LEDGER_COLUMNS = [
    "date", "race_id", "course", "off_time",
    "horse", "horse_id", "trainer_id", "jockey_id",
    "velo_prime_prob", "tier", "candidate_execution_allowed",
    "router_shadow_lane",
    "racing_api_connection_shadow_score",
    "racing_api_course_shadow_score",
    "racing_api_distance_shadow_score",
    "racing_api_enrichment_shadow_score",
    "racing_api_connection_coverage",
    "racing_api_course_coverage",
    "racing_api_distance_coverage",
    "racing_api_enrichment_coverage",
    "result_position", "won", "placed", "sp_decimal", "profit_loss",
    "shadow_version", "leakage_status",
]


_DEDUP_KEY = ("date", "race_id", "horse_id", "shadow_version")


def _ledger_dedup_key(row: dict) -> tuple:
    return tuple(str(row.get(k) or "") for k in _DEDUP_KEY)


def append_to_forward_ledger(ledger_path: str, row: dict[str, Any]) -> None:
    """
    Append one row to the forward-test ledger CSV.
    Idempotent: skips the row if a record with the same
    (date, race_id, horse_id, shadow_version) already exists.
    Creates the file with headers if it does not exist.
    """
    import csv
    from pathlib import Path as _Path

    path = _Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Build dedup set from existing rows
    existing_keys: set[tuple] = set()
    if path.exists() and path.stat().st_size > 0:
        try:
            with path.open(newline="", encoding="utf-8") as f:
                for existing in csv.DictReader(f):
                    existing_keys.add(_ledger_dedup_key(existing))
        except Exception as exc:
            log.warning("shadow ledger dedup scan failed: %s", exc)

    new_key = _ledger_dedup_key(row)
    if new_key in existing_keys:
        log.debug("shadow ledger: duplicate skipped key=%s", new_key)
        return

    write_header = not path.exists() or path.stat().st_size == 0

    def _serialise(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (list, dict)):
            return json.dumps(v, separators=(",", ":"))
        return str(v)

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_LEDGER_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow({col: _serialise(row.get(col)) for col in _LEDGER_COLUMNS})
