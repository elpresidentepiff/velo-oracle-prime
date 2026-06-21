"""
VÉLØ Run Observability Writer
==============================
Implements VELO_OBSERVABILITY_CONTRACT_V1.

Writes data/velo_run_observability_{date}_{run_id}.json after each pipeline
execution. This is the authoritative audit artifact for every run.

Hard constraints:
  - Writes ONLY to data/ directory (LOCAL_ARTIFACT_ONLY permission)
  - No Supabase writes
  - No scoring changes
  - No model changes
  - No live-state mutation

Field naming — semantic accuracy:
  race_scoring_coverage_pct  : percentage of normalised races that were scored
                               (NOT RPDC coverage — renamed from rpdc_coverage)
  persistence_status         : local write attempt status — "OK", "FAIL", "BLOCKED"
                               (NOT ratings source status — renamed from ratings_source_status)
  supabase_write_attempt_success : True if the local persist call reported success.
                               This is NOT independent Supabase readback verification.
                               Future readback proof must use a separate field:
                               supabase_readback_verified (not yet implemented)
                               (renamed from supabase_write_proof)

Usage:
    # Called programmatically from run_prime_today.py:
    from write_velo_run_observability import write_observability_packet

    # Or standalone for manual inspection:
    python scripts/ops/write_velo_run_observability.py --date 2026-05-27 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

# ── Source truth labels ───────────────────────────────────────────────────────
SOURCE_LABELS = frozenset({
    "RP_MERGED_CLEAN",
    "RP_MERGED_DEGRADED",
    "LOCAL_JSON_FALLBACK",
    "RACING_API_BLOCKED",
    "SOURCE_UNKNOWN_BLOCK",
})

# ── Schema version ────────────────────────────────────────────────────────────
SCHEMA_VERSION = "1.1.0"  # bumped: field renames for semantic accuracy


def _get_commit_sha() -> str:
    """Return the current git commit SHA, preferring env vars (Railway)."""
    for key in ("RAILWAY_GIT_COMMIT_SHA", "GIT_COMMIT_SHA", "COMMIT_SHA"):
        val = (os.getenv(key) or "").strip()
        if val:
            return val[:40]
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def _get_branch() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def build_observability_packet(
    *,
    date_str: str,
    run_id: str | None = None,
    source_truth: str,
    feature_health: str,
    active_formula: str,
    excluded_live_components: list[str],
    # ── Renamed fields (semantic accuracy patch) ──────────────────────────────
    race_scoring_coverage_pct: float,          # was: rpdc_coverage
    persistence_status: str,                   # was: ratings_source_status
    supabase_write_attempt_success: bool,      # was: supabase_write_proof
    # ── Unchanged fields ──────────────────────────────────────────────────────
    decision_tier_status: str,
    learning_gate: str,
    next_safe_command: str,
    races_processed: int = 0,
    runners_processed: int = 0,
    warnings: list[str] | None = None,
    gate_fires: dict[str, bool] | None = None,
    extra: dict[str, Any] | None = None,
    # ── Deprecated aliases (accepted but not stored — raise on use) ───────────
    rpdc_coverage: float | None = None,
    ratings_source_status: str | None = None,
    supabase_write_proof: bool | None = None,
) -> dict[str, Any]:
    """
    Build the canonical observability packet dict.

    All 11 mandatory fields from VELO_OBSERVABILITY_CONTRACT_V1 are required.
    Returns a dict ready for JSON serialisation.

    Field semantics (v1.1.0):
      race_scoring_coverage_pct
          Percentage of normalised races that were scored by SQPE.
          This is NOT RPDC (Racing Post Data Coverage). Renamed to prevent
          overclaiming about external data source coverage.

      persistence_status
          Status of the Supabase persist attempt: "OK", "FAIL", or "BLOCKED".
          This is NOT the ratings source status. Renamed to reflect what it
          actually measures.

      supabase_write_attempt_success
          True if the local persist call reported success.
          This is NOT independent Supabase readback verification.
          Future independent readback proof must use:
            supabase_readback_verified  (not yet implemented)
    """
    # ── Deprecated alias guard ────────────────────────────────────────────────
    if rpdc_coverage is not None:
        raise TypeError(
            "rpdc_coverage is deprecated. Use race_scoring_coverage_pct instead."
        )
    if ratings_source_status is not None:
        raise TypeError(
            "ratings_source_status is deprecated. Use persistence_status instead."
        )
    if supabase_write_proof is not None:
        raise TypeError(
            "supabase_write_proof is deprecated. Use supabase_write_attempt_success instead."
        )

    if source_truth not in SOURCE_LABELS:
        raise ValueError(
            f"source_truth '{source_truth}' is not a valid source label. "
            f"Must be one of: {sorted(SOURCE_LABELS)}"
        )

    run_id = run_id or str(uuid.uuid4())
    sha = _get_commit_sha()
    branch = _get_branch()
    ts = datetime.now(UTC).isoformat()

    packet: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "date": date_str,
        "timestamp": ts,
        "git_commit_sha": sha,
        "git_branch": branch,
        # ── 11 mandatory observability fields ──────────────────────────────
        "source_truth": source_truth,
        "feature_health": feature_health,
        "active_formula": active_formula,
        "excluded_live_components": excluded_live_components,
        # Renamed fields (v1.1.0 semantic accuracy patch):
        "race_scoring_coverage_pct": race_scoring_coverage_pct,
        "persistence_status": persistence_status,
        "supabase_write_attempt_success": supabase_write_attempt_success,
        # NOTE: supabase_write_attempt_success is the local write attempt result.
        # It is NOT independent Supabase readback verification.
        # Future readback proof must be a separate field: supabase_readback_verified
        "supabase_readback_verified": None,  # placeholder — not yet implemented
        "decision_tier_status": decision_tier_status,
        "learning_gate": learning_gate,
        "next_safe_command": next_safe_command,
        # ── Run metrics ────────────────────────────────────────────────────
        "metrics": {
            "races_processed": races_processed,
            "runners_processed": runners_processed,
        },
        # ── Gate fires ─────────────────────────────────────────────────────
        "gates": gate_fires or {
            "gate_2_flatline_fires": False,
            "gate_5_rpdc_warn_fires": False,
            "gate_6_learning_blocked": False,
        },
        # ── Warnings ───────────────────────────────────────────────────────
        "warnings": warnings or [],
    }
    if extra:
        packet["extra"] = extra
    return packet


def write_observability_packet(
    packet: dict[str, Any],
    *,
    dry_run: bool = False,
) -> Path:
    """
    Persist the observability packet to data/velo_run_observability_{date}_{run_id}.json.

    Returns the path written (or the path that would have been written on dry-run).
    """
    date_tag = packet["date"].replace("-", "_")
    run_id_short = packet["run_id"][:8]
    filename = f"velo_run_observability_{date_tag}_{run_id_short}.json"
    out_path = DATA / filename

    if dry_run:
        print(f"[DRY-RUN] Would write: {out_path}")
        print(json.dumps(packet, indent=2))
        return out_path

    DATA.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    print(f"[OK] Observability packet written: {out_path}")
    return out_path


def load_observability_packet(date_str: str) -> dict[str, Any] | None:
    """
    Load the most recent observability packet for a given date.
    Returns None if no packet exists.
    """
    date_tag = date_str.replace("-", "_")
    candidates = sorted(DATA.glob(f"velo_run_observability_{date_tag}_*.json"))
    if not candidates:
        return None
    return json.loads(candidates[-1].read_text(encoding="utf-8"))


def validate_packet_schema(packet: dict[str, Any]) -> list[str]:
    """
    Validate that a packet contains all 11 mandatory observability fields.
    Returns a list of missing/invalid field names (empty = valid).

    Uses v1.1.0 field names. Old field names (rpdc_coverage, ratings_source_status,
    supabase_write_proof) are treated as schema errors.
    """
    required_fields = [
        "source_truth",
        "feature_health",
        "active_formula",
        "excluded_live_components",
        "race_scoring_coverage_pct",       # was: rpdc_coverage
        "persistence_status",              # was: ratings_source_status
        "supabase_write_attempt_success",  # was: supabase_write_proof
        "decision_tier_status",
        "git_commit_sha",
        "learning_gate",
        "next_safe_command",
    ]
    missing = [f for f in required_fields if f not in packet]
    errors = list(missing)

    # Detect old field names — treat as schema errors
    old_fields = {
        "rpdc_coverage": "race_scoring_coverage_pct",
        "ratings_source_status": "persistence_status",
        "supabase_write_proof": "supabase_write_attempt_success",
    }
    for old, new in old_fields.items():
        if old in packet:
            errors.append(f"deprecated field '{old}' found — rename to '{new}'")

    # Type checks
    if "source_truth" in packet and packet["source_truth"] not in SOURCE_LABELS:
        errors.append(f"source_truth '{packet['source_truth']}' not in SOURCE_LABELS")
    if "race_scoring_coverage_pct" in packet and not isinstance(
        packet["race_scoring_coverage_pct"], (int, float)
    ):
        errors.append("race_scoring_coverage_pct must be numeric")
    if "supabase_write_attempt_success" in packet and not isinstance(
        packet["supabase_write_attempt_success"], bool
    ):
        errors.append("supabase_write_attempt_success must be boolean")
    if "excluded_live_components" in packet and not isinstance(
        packet["excluded_live_components"], list
    ):
        errors.append("excluded_live_components must be a list")

    return errors


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="VÉLØ Run Observability Writer")
    parser.add_argument("--date", default=None, help="Date YYYY-MM-DD (default: today)")
    parser.add_argument("--dry-run", action="store_true", help="Print packet without writing")
    parser.add_argument("--validate", metavar="FILE", help="Validate an existing observability JSON file")
    args = parser.parse_args()

    if args.validate:
        path = Path(args.validate)
        if not path.exists():
            print(f"[ERROR] File not found: {path}")
            return 1
        packet = json.loads(path.read_text(encoding="utf-8"))
        errors = validate_packet_schema(packet)
        if errors:
            print(f"[FAIL] Schema validation failed ({len(errors)} error(s)):")
            for e in errors:
                print(f"  - {e}")
            return 1
        print(f"[OK] Schema valid: {path}")
        return 0

    from datetime import date as _date
    date_str = args.date or _date.today().isoformat()

    # Build a representative packet for manual/standalone use
    packet = build_observability_packet(
        date_str=date_str,
        source_truth="SOURCE_UNKNOWN_BLOCK",
        feature_health="UNKNOWN",
        active_formula="UNKNOWN — run via run_prime_today.py",
        excluded_live_components=[],
        race_scoring_coverage_pct=0.0,
        persistence_status="UNKNOWN",
        supabase_write_attempt_success=False,
        decision_tier_status="UNKNOWN",
        learning_gate="BLOCKED_NO_RUN",
        next_safe_command="python scripts/ops/velo_session_start_check.py",
        warnings=["Standalone invocation — no live run data available"],
    )
    write_observability_packet(packet, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
