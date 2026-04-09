"""
VELO Shadow Lab — Follower Lane
================================
Consumes completed production batches, runs shadow analysis, writes to shadow tables.

Rules:
  - Reads velo_verdicts only (production output)
  - Writes ONLY to shadow tables
  - Never modifies production state
  - Failure is isolated — does not affect scoring

Trigger:
  - Wakes via cron (30 min after production)
  - Uses pipeline_run.status = 'completed' as batch completeness signal
  - Idempotent: re-running same pipeline_run_id is a no-op
"""

import sys
import os
import json
import logging
import traceback
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# ── Supabase ─────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SHADOW_KEY   = os.getenv("SHADOW_SUPABASE_KEY", os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))

# ── Logging ───────────────────────────────────────────────────────────────────
log = logging.getLogger("shadow_lab")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log.setLevel(logging.INFO)

SCRIPT_VERSION = "1.0.0"
SERVICE_NAME   = "velo-shadow-lab"


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Watermark detection
# ══════════════════════════════════════════════════════════════════════════════

def _get_watermark(sb) -> dict:
    """Return most recent processed pipeline_run_id, or empty if none."""
    rows = sb.table("shadow_watermarks") \
        .select("*") \
        .eq("service_name", SERVICE_NAME) \
        .order("last_processed_at", desc=True) \
        .limit(1) \
        .execute()
    if rows.data:
        return rows.data[0]
    return {}


def _is_already_processed(sb, pipeline_run_id: str) -> bool:
    row = sb.table("shadow_watermarks") \
        .select("id") \
        .eq("service_name", SERVICE_NAME) \
        .eq("pipeline_run_id", pipeline_run_id) \
        .execute()
    return len(row.data) > 0


def _advance_watermark(sb, pipeline_run_id: str, rows_processed: int) -> None:
    """Upsert watermark entry for this pipeline_run_id."""
    sb.table("shadow_watermarks").upsert({
        "service_name":     SERVICE_NAME,
        "pipeline_run_id":  pipeline_run_id,
        "last_processed_at": datetime.now(timezone.utc).isoformat(),
        "rows_processed":   rows_processed,
    }, on_conflict="service_name,pipeline_run_id").execute()
    log.info(f"Watermark advanced: pipeline_run_id={pipeline_run_id} rows={rows_processed}")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Batch detection
# ══════════════════════════════════════════════════════════════════════════════

def _get_latest_completed_batch(sb) -> Optional[dict]:
    """Find the most recent completed velo-prime-scoring-prod batch."""
    rows = sb.table("pipeline_runs") \
        .select("*") \
        .eq("service_name", "velo-prime-scoring") \
        .eq("status", "PASS") \
        .eq("run_state", "completed") \
        .order("started_at", desc=True) \
        .limit(1) \
        .execute()
    if not rows.data:
        log.info("No completed production batch found.")
        return None
    batch = rows.data[0]
    log.info(f"Found batch: pipeline_run_id={batch.get('id')} started={batch.get('started_at')}")
    return batch


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Fetch production verdicts for completed batch
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_verdicts(sb, pipeline_run_id: str) -> list[dict]:
    rows = sb.table("velo_verdicts") \
        .select("*") \
        .eq("pipeline_run_id", pipeline_run_id) \
        .execute()
    log.info(f"Fetched {len(rows.data)} verdict rows for pipeline_run_id={pipeline_run_id}")
    return rows.data


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Shadow analysis per verdict
# ══════════════════════════════════════════════════════════════════════════════

def _load_g_state(sb) -> dict:
    """Load G state from Supabase learned_patterns."""
    rows = sb.table("learned_patterns") \
        .select("*") \
        .eq("pattern_type", "playbook_g_state") \
        .order("updated_at", desc=True) \
        .limit(1) \
        .execute()
    if rows.data:
        raw = rows.data[0]
        try:
            return json.loads(raw.get("pattern_data", "{}"))
        except Exception:
            return {}
    return {}


def _run_g_shadow(verdict: dict, g_state: dict) -> dict:
    """
    G shadow evaluation — pure follower, no production side effects.
    
    Returns dict with:
      g_shadow_multiplier, g_shadow_flags, g_shadow_horse_id,
      g_shadow_mode, doctrines_fired
    """
    runner_list = verdict.get("full_analysis") or []
    if not runner_list:
        return {
            "g_shadow_multiplier": 1.0,
            "g_shadow_flags":      [],
            "g_shadow_horse_id":  None,
            "g_shadow_mode":      "noop",
            "doctrines_fired":    [],
        }

    g_races = g_state.get("races_observed", 0)
    if g_races < 50:
        return {
            "g_shadow_multiplier": 1.0,
            "g_shadow_flags":      ["G_TOO_FEW_RACES"],
            "g_shadow_horse_id":  None,
            "g_shadow_mode":      "underpopulated",
            "doctrines_fired":    [],
        }

    # ── Pain rules ────────────────────────────────────────────────────────────
    sent_tag     = verdict.get("sentient_tag") or verdict.get("rpd_tag") or ""
    hdta_ae      = verdict.get("hdta_ae") or 1.0
    dist_1st     = verdict.get("hdta_dist_1st") or 999
    sentiment    = verdict.get("sentient_modifier_applied") or 0.0
    macro_chaos  = verdict.get("macro_chaos_mode") or False
    regime       = verdict.get("macro_regime_label") or ""
    market_decep = verdict.get("market_deception_score") or 0.0
    or_missing   = verdict.get("or_missing") or False

    pain_flags   = []
    triumph_flags = []
    anger_flags   = []

    # ENGINE_SUPREMACY
    if sent_tag in ("engine_dominance", "engine_supremacy"):
        pain_flags.append("ENGINE_SUPREMACY")
        triumph_flags.append("ENGINE_SUPREMACY")

    # VETP_ECHO
    if sentiment > 0.15 and hdta_ae > 1.3:
        pain_flags.append("VETP_ECHO")
        triumph_flags.append("VETP_ECHO")

    # DUAL_TRAP
    if dist_1st <= 3 and hdta_ae > 1.2:
        pain_flags.append("DUAL_TRAP")

    # ANGER_001
    if regime == "good-to-fast" and sentiment > 0.2:
        anger_flags.append("ANGER_001")

    # ANGER_002
    if macro_chaos and sentiment > 0.1:
        anger_flags.append("ANGER_002")

    # EVIDENCE_WEAKNESS
    if market_decep > 0.6 and sentiment < 0.05:
        pain_flags.append("EVIDENCE_WEAKNESS")

    # ODDS_INTEGRITY
    if or_missing:
        pain_flags.append("ODDS_INTEGRITY")

    # ── Doctrine aggregation ───────────────────────────────────────────────────
    doctrines = list(set(
        [f for f in pain_flags if f.startswith("ENGINE") or f.startswith("VETP")]
        + [f for f in triumph_flags if f.startswith("ENGINE") or f.startswith("VETP")]
    ))

    # ── Top pick G evaluation ──────────────────────────────────────────────────
    top_runner = runner_list[0]
    top_hdta   = top_runner.get("hdta_ae") or 1.0
    top_prob   = top_runner.get("velo_prime_prob") or 0.0
    top_sent   = top_runner.get("sentient_modifier_applied") or 0.0

    pain_score = len(pain_flags) * 0.06
    triumph_score = len(triumph_flags) * 0.05

    if anger_flags:
        anger_mult = 0.80
    elif pain_flags:
        anger_mult = 1.0 - pain_score
    elif triumph_flags:
        anger_mult = 1.0 + triumph_score
    else:
        anger_mult = 1.0

    anger_mult = round(max(0.6, min(1.4, anger_mult)), 4)
    g_shadow_mode = (
        "anger" if anger_flags else
        "pain"  if pain_flags else
        "triumph" if triumph_flags else
        "neutral"
    )

    return {
        "g_shadow_multiplier": anger_mult,
        "g_shadow_flags":      pain_flags + triumph_flags + anger_flags,
        "g_shadow_horse_id":   top_runner.get("horse_id") if pain_flags or triumph_flags else None,
        "g_shadow_mode":       g_shadow_mode,
        "doctrines_fired":     doctrines,
    }


def _compute_rank_movement(verdict: dict, g_result: dict) -> dict:
    """Top-3 rank movement analysis."""
    runner_list = verdict.get("full_analysis") or []
    top3 = runner_list[:3]

    top3_scores = []
    for i, runner in enumerate(top3):
        base_prob  = runner.get("velo_prime_prob") or 0.0
        g_mult     = runner.get("g_shadow_multiplier", 1.0) if i == 0 else 1.0
        adjusted   = round(base_prob * g_mult, 4)
        top3_scores.append({
            "rank":           i + 1,
            "horse_id":       runner.get("horse_id", ""),
            "base_prob":      base_prob,
            "g_shadow_mult":  g_mult,
            "adjusted_prob":  adjusted,
            "doctrines_fired": runner.get("doctrines_fired") or [],
        })

    top_prob   = top3_scores[0]["base_prob"]   if len(top3_scores) > 0 else 0.0
    top_shadow = top3_scores[0]["adjusted_prob"] if len(top3_scores) > 0 else 0.0

    return {
        "top3_scores":           top3_scores,
        "rank_1_base_prob":      top_prob,
        "rank_1_shadow_prob":    top_shadow,
        "shortlist_changed":    len(top3_scores) > 1 and (
            top3_scores[1]["base_prob"] != top3_scores[1]["adjusted_prob"]
        ),
        "favourite_overturned":  len(top3_scores) > 1 and (
            top3_scores[1]["adjusted_prob"] > top3_scores[0]["adjusted_prob"]
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Write shadow results
# ══════════════════════════════════════════════════════════════════════════════

def _write_shadow_result(sb, verdict: dict, pipeline_run_id: str, g_result: dict) -> str:
    """Write one shadow result row. Returns status."""
    try:
        sb.table("velo_shadow_results").upsert({
            "race_id":             verdict["race_id"],
            "pipeline_run_id":     pipeline_run_id,
            "generated_at":        verdict["generated_at"],
            "g_shadow_multiplier": g_result["g_shadow_multiplier"],
            "g_shadow_flags":      g_result["g_shadow_flags"],
            "g_shadow_horse_id":  g_result["g_shadow_horse_id"],
            "g_shadow_mode":      g_result["g_shadow_mode"],
            "doctrines_fired":    g_result["doctrines_fired"],
            "processed_at":       datetime.now(timezone.utc).isoformat(),
        }, on_conflict="race_id,pipeline_run_id").execute()
        return "success"
    except Exception as e:
        sb.table("shadow_audit_log").insert({
            "run_id":          f"shadow_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "race_id":         verdict["race_id"],
            "pipeline_run_id": pipeline_run_id,
            "status":          "error",
            "error_message":   str(e)[:500],
        }).execute()
        return "error"


def _write_rank_movement(sb, verdict: dict, pipeline_run_id: str, rm_result: dict) -> None:
    """Write top-3 rank movement analysis."""
    try:
        sb.table("velo_shadow_rank_movement").upsert({
            "race_id":               verdict["race_id"],
            "pipeline_run_id":       pipeline_run_id,
            "generated_at":          verdict["generated_at"],
            "top3_scores":           rm_result["top3_scores"],
            "rank_1_base_prob":      rm_result["rank_1_base_prob"],
            "rank_1_shadow_prob":    rm_result["rank_1_shadow_prob"],
            "shortlist_changed":     rm_result["shortlist_changed"],
            "favourite_overturned": rm_result["favourite_overturned"],
            "processed_at":          datetime.now(timezone.utc).isoformat(),
        }, on_conflict="race_id,pipeline_run_id").execute()
    except Exception as e:
        log.warning(f"Rank movement write failed for {verdict['race_id']}: {e}")


def _log_processed(sb, run_id: str, verdict: dict, pipeline_run_id: str, status: str, rows_evaluated: int = 0) -> None:
    try:
        sb.table("shadow_audit_log").insert({
            "run_id":          run_id,
            "race_id":         verdict["race_id"],
            "pipeline_run_id": pipeline_run_id,
            "status":          status,
            "rows_evaluated":  rows_evaluated,
        }).execute()
    except Exception:
        pass  # Non-critical


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    log.info(f"=== VELO Shadow Lab v{SCRIPT_VERSION} ===")
    log.info(f"Service: {SERVICE_NAME} | Version: {SCRIPT_VERSION}")

    if not SUPABASE_URL or not SHADOW_KEY:
        log.error("SUPABASE_URL or SHADOW_SUPABASE_KEY not set — aborting")
        return

    from supabase import create_client
    sb = create_client(SUPABASE_URL, SHADOW_KEY)
    log.info("Supabase connected")

    # ── Step A: Check if there's a new completed batch ───────────────────────
    batch = _get_latest_completed_batch(sb)
    if not batch:
        log.info("No new completed batch. Exiting cleanly.")
        return

    pipeline_run_id = batch["id"]

    if _is_already_processed(sb, pipeline_run_id):
        log.info(f"Batch {pipeline_run_id} already processed. Exiting.")
        return

    # ── Step B: Fetch verdict rows ───────────────────────────────────────────
    verdicts = _fetch_verdicts(sb, pipeline_run_id)
    if not verdicts:
        log.warning(f"No verdict rows for pipeline_run_id={pipeline_run_id}")
        _advance_watermark(sb, pipeline_run_id, 0)
        return

    # ── Step C: Load G state ─────────────────────────────────────────────────
    g_state = _load_g_state(sb)
    log.info(f"G state: races_observed={g_state.get('races_observed', 0)}")

    # ── Step D: Process each verdict ─────────────────────────────────────────
    run_id       = f"shadow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    success_ct   = 0
    error_ct     = 0

    for verdict in verdicts:
        race_id = verdict.get("race_id", "unknown")

        # G shadow
        g_result = _run_g_shadow(verdict, g_state)

        # Rank movement
        rm_result = _compute_rank_movement(verdict, g_result)

        # Write shadow results
        status = _write_shadow_result(sb, verdict, pipeline_run_id, g_result)
        _write_rank_movement(sb, verdict, pipeline_run_id, rm_result)
        _log_processed(sb, run_id, verdict, pipeline_run_id, status)

        if status == "success":
            success_ct += 1
        else:
            error_ct += 1

        if g_result["g_shadow_flags"]:
            log.info(f"  {race_id}: g_mult={g_result['g_shadow_multiplier']} flags={g_result['g_shadow_flags']}")

    # ── Step E: Advance watermark ─────────────────────────────────────────────
    _advance_watermark(sb, pipeline_run_id, success_ct)

    log.info(f"=== Shadow Lab Complete ===")
    log.info(f"Pipeline run: {pipeline_run_id}")
    log.info(f"Processed:    {success_ct} success | {error_ct} error")
    log.info(f"Exiting cleanly.")


if __name__ == "__main__":
    main()
