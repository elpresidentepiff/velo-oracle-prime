"""
audit_hfs_signal_integrity.py
==============================
Improved and extended version of audit_hfs_signal_integrity_block001.py.

Connects to Supabase and runs a full HFS signal integrity audit.
Uses REST API (not supabase-py) for compatibility.

Outputs to:
  data/hfs_signal_integrity_audit_latest.json
  data/hfs_signal_integrity_audit_latest.md

Classification:
  HFS_TRAINING_BLOCKED         — mpi/cb null > 10%, parity off, duplicates, missing vectors
  HFS_SIGNAL_REPAIRED_BUT_LOW_VOLUME — passes null check but total rows < 5000
  HFS_TRAINING_READY           — all checks pass, total rows >= 5000

Changes vs block001:
  - Uses REST API instead of supabase-py (no import dependency)
  - Checks multiple candidate table names (historical_feature_store, hfs_features, velo_features)
  - Adds archive vs live data split
  - Writes JSON output in addition to MD
  - Adds vector completeness check
  - Adds mpi_source / chaos_bloom_source / signal_contract_version audit
  - Fully standalone, no imports from app/

Usage:
    python scripts/audit_hfs_signal_integrity.py
"""

from __future__ import annotations

import json
import logging
import os
import statistics
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
LOG = logging.getLogger("audit_hfs_signal_integrity")

OUTPUT_JSON = ROOT / "data" / "hfs_signal_integrity_audit_latest.json"
OUTPUT_MD = ROOT / "data" / "hfs_signal_integrity_audit_latest.md"

# Minimum thresholds
MIN_ROWS_FOR_READY = 5000
NULL_RATE_THRESHOLD = 0.10    # 10% max null for key fields
WINNER_PARITY_MIN = 0.05      # 5% min winners
WINNER_PARITY_MAX = 0.40      # 40% max winners

# Candidate table names to check (in order of preference)
CANDIDATE_TABLES = [
    "historical_feature_store",
    "hfs_features",
    "velo_features",
    "runner_derived_features",
]

# Core fields to audit when present
SELECT_FIELDS = ",".join([
    "race_id", "horse_id", "race_date",
    "mpi", "chaos_bloom", "mpi_source", "chaos_bloom_source", "signal_contract_version",
    "winner_flag", "placed_flag", "finish_position", "position_int", "is_winner",
    "sp_dec", "field_size",
    "sqpe_v17_prob", "velo_prime_prob", "improvement_score", "market_deception_score",
    "place_prob", "longshot_score",
    "scoring_status", "feature_json",
])


# ── Supabase REST helpers ───────────────────────────────────────────────────────

def _sb_env() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set in environment")
    return url, key


def _sb_get(table: str, select: str, params: dict | None = None, limit: int = 10000) -> list[dict]:
    url, key = _sb_env()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Prefer": "count=none",
    }
    all_rows: list[dict] = []
    offset = 0
    page = min(limit, 1000)
    while True:
        query: dict[str, str] = {"select": select, "limit": str(page), "offset": str(offset)}
        if params:
            query.update(params)
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in query.items())
        req_url = f"{url}/rest/v1/{table}?{qs}"
        req = urllib.request.Request(req_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (404, 400):
                return []  # table doesn't exist or bad request
            LOG.warning("HTTP %d from %s: %s", e.code, table, e)
            return all_rows
        except Exception as exc:
            LOG.warning("Supabase error (%s): %s", table, exc)
            return all_rows
        if not isinstance(data, list):
            return all_rows
        all_rows.extend(data)
        if len(data) < page:
            break
        offset += page
        if offset >= limit:
            break
    return all_rows


def _table_exists(table: str) -> bool:
    url, key = _sb_env()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    req_url = f"{url}/rest/v1/{table}?select=*&limit=1"
    req = urllib.request.Request(req_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return isinstance(data, list)
    except Exception:
        return False


# ── Analysis helpers ────────────────────────────────────────────────────────────

def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None or str(v).strip() in ("", "–", "-"):
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


def _describe(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "min": None, "max": None, "mean": None, "std": None}
    n = len(values)
    return {
        "n": n,
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "mean": round(statistics.mean(values), 4),
        "std": round(statistics.stdev(values), 4) if n >= 2 else 0.0,
    }


def _null_rate(rows: list[dict], key: str) -> float:
    if not rows:
        return 1.0
    return sum(1 for r in rows if r.get(key) is None) / len(rows)


def _has_ordered_vec(r: dict) -> bool:
    fj = r.get("feature_json")
    if isinstance(fj, dict):
        return bool(fj.get("strictly_ordered_vector"))
    if isinstance(fj, str):
        try:
            return bool(json.loads(fj).get("strictly_ordered_vector"))
        except Exception:
            return False
    return fj is not None  # If feature_json exists but not a dict/str, count as present


def _sp_bracket(sp: Any) -> str:
    v = _safe_float(sp)
    if v is None:
        return "unknown"
    if v <= 2.0:
        return "evens_or_under"
    if v <= 4.0:
        return "2.0-4.0"
    if v <= 8.0:
        return "4.0-8.0"
    if v <= 16.0:
        return "8.0-16.0"
    if v <= 33.0:
        return "16.0-33.0"
    return "33.0+"


# ── Main audit logic ────────────────────────────────────────────────────────────

def _audit_table(table: str, rows: list[dict]) -> dict[str, Any]:
    total = len(rows)
    _empty_stats = {"n": 0, "min": None, "max": None, "mean": None, "std": None}
    if total == 0:
        return {
            "table": table, "total": 0,
            "rows_2026": 0, "rows_pre2026": 0,
            "mpi_null_count": 0, "mpi_null_pct": 0.0, "mpi_stats": _empty_stats, "mpi_source_counts": {},
            "chaos_bloom_null_count": 0, "chaos_bloom_null_pct": 0.0, "chaos_bloom_stats": _empty_stats,
            "winner_parity": None, "winner_pct": None, "winner_count": 0, "duplicate_count": 0,
            "vector_completeness": None, "missing_vec": None, "missing_vec_pct": None,
            "key_features_checked": [], "key_field_null_rates": {}, "scoring_status_counts": {},
            "signal_contract_version_counts": {},
            "live_mpi_null": None, "live_cb_null": None,
            "archive_mpi_null_rate": None, "live_mpi_null_rate": None,
            "archive_cb_null_rate": None, "live_cb_null_rate": None,
            "classification": "HFS_TRAINING_BLOCKED",
            "blocked_reasons": ["TABLE_EMPTY_OR_NOT_FOUND"],
        }

    sample_keys = set(rows[0].keys()) if rows else set()

    # ── Partition: 2026+ vs pre-2026 ─────────────────────────────────────────
    rows_2026 = [r for r in rows if (r.get("race_date") or "") >= "2026-01-01"]
    rows_pre2026 = [r for r in rows if (r.get("race_date") or "") < "2026-01-01"]

    # ── MPI ──────────────────────────────────────────────────────────────────
    mpi_vals = [_safe_float(r["mpi"]) for r in rows if r.get("mpi") is not None]
    mpi_null = total - len(mpi_vals)
    mpi_null_pct = mpi_null / max(total, 1)
    mpi_stats = _describe(mpi_vals)

    # MPI source breakdown
    mpi_source_counts = Counter(r.get("mpi_source") for r in rows if "mpi_source" in sample_keys)

    # ── Chaos bloom ─────────────────────────────────────────────────────────
    cb_vals = [_safe_float(r["chaos_bloom"]) for r in rows if r.get("chaos_bloom") is not None]
    cb_null = total - len(cb_vals)
    cb_null_pct = cb_null / max(total, 1)
    cb_stats = _describe(cb_vals)

    # ── Signal contract version ──────────────────────────────────────────────
    sig_version_counts = Counter(
        r.get("signal_contract_version") for r in rows
        if "signal_contract_version" in sample_keys
    )

    # ── Winner / placed parity ────────────────────────────────────────────────
    winner_count = 0
    placed_count = 0
    if "winner_flag" in sample_keys:
        winner_count = sum(1 for r in rows if r.get("winner_flag") is True)
        placed_count = sum(1 for r in rows if r.get("placed_flag") is True)
    elif "is_winner" in sample_keys:
        winner_count = sum(1 for r in rows if r.get("is_winner") in (True, 1, "1", "true"))
    elif "position_int" in sample_keys:
        winner_count = sum(1 for r in rows if r.get("position_int") == 1)
        placed_count = sum(1 for r in rows if r.get("position_int") is not None and r.get("position_int") <= 3)
    elif "finish_position" in sample_keys:
        winner_count = sum(1 for r in rows if str(r.get("finish_position") or "") == "1")

    winner_pct = winner_count / max(total, 1)
    placed_pct = placed_count / max(total, 1)

    # ── Duplicates ───────────────────────────────────────────────────────────
    key_counts = Counter((r.get("race_id"), r.get("horse_id")) for r in rows)
    duplicates = sum(v - 1 for v in key_counts.values() if v > 1)

    # ── Missing vectors ──────────────────────────────────────────────────────
    if "feature_json" in sample_keys:
        missing_vec = sum(1 for r in rows if not _has_ordered_vec(r))
        missing_vec_pct = missing_vec / max(total, 1)
    else:
        missing_vec = None
        missing_vec_pct = None

    # ── Key feature null rates ────────────────────────────────────────────────
    key_field_null_rates: dict[str, float] = {}
    for field in ["sqpe_v17_prob", "velo_prime_prob", "mpi", "chaos_bloom",
                  "market_deception_score", "place_prob"]:
        if field in sample_keys:
            key_field_null_rates[field] = round(_null_rate(rows, field), 4)

    # ── SP and field size distributions ──────────────────────────────────────
    sp_bracket_counter = Counter(_sp_bracket(r.get("sp_dec")) for r in rows)
    fs_vals = [r.get("field_size") for r in rows if r.get("field_size") is not None]
    fs_ranges = {"2-5": (2, 5), "6-8": (6, 8), "9-12": (9, 12), "13-16": (13, 16), "17+": (17, 9999)}
    fs_deciles: dict[str, int] = {}
    for bucket, (lo, hi) in fs_ranges.items():
        fs_deciles[bucket] = sum(1 for v in fs_vals if v is not None and lo <= int(v) <= hi)

    # ── Archive vs live ─────────────────────────────────────────────────────
    scoring_status_counts: dict[str, int] = {}
    if "scoring_status" in sample_keys:
        scoring_status_counts = dict(Counter(r.get("scoring_status") for r in rows))

    archive_mpi_null: Optional[float] = None
    live_mpi_null: Optional[float] = None
    if rows_2026 or rows_pre2026:
        archive_mpi_null = round(_null_rate(rows_pre2026, "mpi"), 4) if rows_pre2026 else None
        live_mpi_null = round(_null_rate(rows_2026, "mpi"), 4) if rows_2026 else None

    # ── Classification logic ─────────────────────────────────────────────────
    blocked_reasons: list[str] = []
    if mpi_null_pct > NULL_RATE_THRESHOLD:
        blocked_reasons.append(f"mpi null% = {mpi_null_pct:.1%} (> {NULL_RATE_THRESHOLD:.0%} threshold)")
    if cb_null_pct > NULL_RATE_THRESHOLD:
        blocked_reasons.append(f"chaos_bloom null% = {cb_null_pct:.1%} (> {NULL_RATE_THRESHOLD:.0%} threshold)")
    if winner_pct < WINNER_PARITY_MIN:
        blocked_reasons.append(f"winner parity = {winner_pct:.1%} (< {WINNER_PARITY_MIN:.0%} threshold)")
    elif winner_pct > WINNER_PARITY_MAX:
        blocked_reasons.append(f"winner parity = {winner_pct:.1%} (> {WINNER_PARITY_MAX:.0%} — label imbalance?)")
    if duplicates > 100:
        blocked_reasons.append(f"duplicate rows = {duplicates} (> 100 threshold)")
    if missing_vec_pct is not None and missing_vec_pct > 0.05:
        blocked_reasons.append(f"missing vectors = {missing_vec_pct:.1%} (> 5%)")
    # Check for critical field absence
    if "mpi" not in sample_keys:
        blocked_reasons.append("mpi field not present in table")
    if "chaos_bloom" not in sample_keys:
        blocked_reasons.append("chaos_bloom field not present in table")
    if "sqpe_v17_prob" not in sample_keys and "velo_prime_prob" not in sample_keys:
        blocked_reasons.append("no sqpe_v17_prob or velo_prime_prob field")

    if blocked_reasons:
        classification = "HFS_TRAINING_BLOCKED"
    elif total < MIN_ROWS_FOR_READY:
        classification = "HFS_SIGNAL_REPAIRED_BUT_LOW_VOLUME"
    else:
        classification = "HFS_TRAINING_READY"

    return {
        "table": table,
        "total": total,
        "rows_2026": len(rows_2026),
        "rows_pre2026": len(rows_pre2026),
        "mpi_null_count": mpi_null,
        "mpi_null_pct": round(mpi_null_pct, 4),
        "mpi_stats": mpi_stats,
        "mpi_source_counts": dict(mpi_source_counts),
        "chaos_bloom_null_count": cb_null,
        "chaos_bloom_null_pct": round(cb_null_pct, 4),
        "chaos_bloom_stats": cb_stats,
        "signal_contract_version_counts": dict(sig_version_counts),
        "winner_count": winner_count,
        "placed_count": placed_count,
        "winner_pct": round(winner_pct, 4),
        "placed_pct": round(placed_pct, 4),
        "duplicates": duplicates,
        "missing_vec": missing_vec,
        "missing_vec_pct": round(missing_vec_pct, 4) if missing_vec_pct is not None else None,
        "key_field_null_rates": key_field_null_rates,
        "sp_bracket_counts": dict(sp_bracket_counter),
        "fs_deciles": fs_deciles,
        "scoring_status_counts": scoring_status_counts,
        "archive_mpi_null_rate": archive_mpi_null,
        "live_mpi_null_rate": live_mpi_null,
        "sample_fields": sorted(sample_keys)[:30],
        "blocked_reasons": blocked_reasons,
        "classification": classification,
    }


def main() -> int:
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    LOG.info("HFS Signal Integrity Audit — started at %s", generated_at)

    # Find which tables exist
    existing_tables: list[str] = []
    LOG.info("Checking candidate HFS tables ...")
    for table in CANDIDATE_TABLES:
        exists = _table_exists(table)
        LOG.info("  %s: %s", table, "EXISTS" if exists else "NOT FOUND")
        if exists:
            existing_tables.append(table)

    table_analyses: list[dict] = []
    for table in existing_tables:
        LOG.info("Loading %s (up to 10000 rows) ...", table)
        rows = _sb_get(table, SELECT_FIELDS, limit=10000)
        LOG.info("  %s: %d rows loaded", table, len(rows))
        analysis = _audit_table(table, rows)
        table_analyses.append(analysis)
        LOG.info("  %s classification: %s", table, analysis["classification"])
        if analysis["blocked_reasons"]:
            for br in analysis["blocked_reasons"]:
                LOG.warning("  BLOCKER (%s): %s", table, br)

    # Overall classification
    if not table_analyses:
        overall_status = "HFS_TRAINING_BLOCKED"
        blocker_summary = ["NO_HFS_TABLE_EXISTS — none of the candidate tables were found"]
    else:
        classifications = [a["classification"] for a in table_analyses]
        if "HFS_TRAINING_READY" in classifications:
            overall_status = "HFS_TRAINING_READY"
        elif "HFS_SIGNAL_REPAIRED_BUT_LOW_VOLUME" in classifications:
            overall_status = "HFS_SIGNAL_REPAIRED_BUT_LOW_VOLUME"
        else:
            overall_status = "HFS_TRAINING_BLOCKED"
        blocker_summary = [
            f"{a['table']}: {br}"
            for a in table_analyses
            for br in a["blocked_reasons"]
        ]

    if overall_status == "HFS_TRAINING_READY":
        recommendation = "HFS signal intact and volume sufficient. Proceed to training gate review with operator sign-off."
    elif overall_status == "HFS_SIGNAL_REPAIRED_BUT_LOW_VOLUME":
        total_rows = sum(a["total"] for a in table_analyses)
        recommendation = (
            f"Signal partially repaired (n={total_rows}). Need >= {MIN_ROWS_FOR_READY} rows. "
            "Run backfill to increase volume."
        )
    else:
        recommendation = (
            "HFS training blocked. Steps to fix: "
            "(1) Run backfill_hfs_mpi_chaos_bloom.py --apply (requires DB password). "
            "(2) Re-run backfill_historical_feature_store.py --year 2026 --only-null-signals. "
            "(3) Re-run this audit to confirm HFS_TRAINING_READY."
        )

    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "existing_tables": existing_tables,
        "table_analyses": table_analyses,
        "overall_status": overall_status,
        "blocker_summary": blocker_summary,
        "recommendation": recommendation,
    }

    # ── Write JSON ────────────────────────────────────────────────────────────
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # ── Write MD ──────────────────────────────────────────────────────────────
    lines = []

    def out(line: str = "") -> None:
        lines.append(line)
        print(line)

    out()
    out("=" * 70)
    out("HFS SIGNAL INTEGRITY AUDIT")
    out(f"Generated: {generated_at}")
    out(f"OVERALL STATUS: {overall_status}")
    out("=" * 70)
    out()

    if not table_analyses:
        out("No HFS tables found. HFS training is blocked.")
        out()
        out(f"Recommendation: {recommendation}")
    else:
        for a in table_analyses:
            out(f"## Table: {a['table']}  |  Classification: {a['classification']}")
            out()
            out(f"  Total rows:                        {a['total']}")
            out(f"  2026+ rows (live era):             {a.get('rows_2026', 'n/a')}")
            out(f"  Pre-2026 archive:                  {a.get('rows_pre2026', 'n/a')}")
            out()
            out("  MPI Signal:")
            out(f"    Null count:                      {a['mpi_null_count']}  ({a['mpi_null_pct']:.1%})")
            ms = a["mpi_stats"]
            if ms["n"] > 0:
                out(f"    min={ms['min']}  max={ms['max']}  mean={ms['mean']}  std={ms['std']}")
            if a["mpi_source_counts"]:
                out(f"    MPI sources: {a['mpi_source_counts']}")
            out()
            out("  Chaos Bloom Signal:")
            out(f"    Null count:                      {a['chaos_bloom_null_count']}  ({a['chaos_bloom_null_pct']:.1%})")
            cs = a["chaos_bloom_stats"]
            if cs["n"] > 0:
                out(f"    min={cs['min']}  max={cs['max']}  mean={cs['mean']}  std={cs['std']}")
            out()
            out("  Signal contract versions:")
            for ver, cnt in a.get("signal_contract_version_counts", {}).items():
                out(f"    {ver}: {cnt}")
            out()
            wp = a.get("winner_pct"); out(f"  Winner parity:   {wp:.1%}  ({a['winner_count']} of {a['total']})" if wp is not None else "  Winner parity:   n/a")
            pp = a.get("placed_pct"); out(f"  Placed parity:   {pp:.1%}  ({a.get('placed_count',0)} of {a['total']})" if pp is not None else "  Placed parity:   n/a")
            out(f"  Duplicates:      {a.get('duplicates', 0)}")
            if a["missing_vec"] is not None:
                out(f"  Missing vectors: {a['missing_vec']}  ({a['missing_vec_pct']:.1%})")
            out()
            out("  Key field null rates:")
            for f, nr in a["key_field_null_rates"].items():
                flag = "  *** BLOCKER" if nr > NULL_RATE_THRESHOLD else ""
                out(f"    {f}: {nr:.1%}{flag}")
            out()
            if a["scoring_status_counts"]:
                out("  Scoring status breakdown:")
                for k, v in a["scoring_status_counts"].items():
                    out(f"    {k}: {v}")
                out()
            if a["archive_mpi_null_rate"] is not None or a["live_mpi_null_rate"] is not None:
                out(f"  Archive MPI null: {a['archive_mpi_null_rate']}")
                out(f"  Live MPI null:    {a['live_mpi_null_rate']}")
                out()
            out()

    out("=" * 70)
    out(f"FINAL CLASSIFICATION: {overall_status}")
    out("=" * 70)
    if blocker_summary:
        out("BLOCKED REASONS:")
        for br in blocker_summary:
            out(f"  - {br}")
    else:
        out("No blocking conditions detected.")
    out()
    if overall_status == "HFS_TRAINING_BLOCKED":
        out("Playbook G training: BLOCKED — resolve issues above before training.")
    elif overall_status == "HFS_SIGNAL_REPAIRED_BUT_LOW_VOLUME":
        total_rows = sum(a["total"] for a in table_analyses)
        out("Playbook G training: BLOCKED — signal repaired but row count insufficient.")
        out(f"  Current rows: {total_rows}. Need >= {MIN_ROWS_FOR_READY} before training.")
    else:
        out("Playbook G training: READY — all integrity checks pass.")
    out()
    out(f"Recommendation: {recommendation}")
    out()

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOG.info("Audit written to %s", OUTPUT_MD)
    LOG.info("JSON written to %s", OUTPUT_JSON)
    print(f"\nAudit saved to: {OUTPUT_MD}")
    print(f"JSON saved to:  {OUTPUT_JSON}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
