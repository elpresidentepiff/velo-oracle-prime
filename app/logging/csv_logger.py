"""
CSV Logging Module
Append-only logging to master_race_log.csv and fade_audit_log.csv
"""

import csv
import os
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# CSV PATHS
# ============================================================================

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

MASTER_RACE_LOG = LOG_DIR / "master_race_log.csv"
FADE_AUDIT_LOG = LOG_DIR / "fade_audit_log.csv"

# ============================================================================
# MASTER RACE LOG
# ============================================================================

MASTER_RACE_LOG_COLUMNS = [
    # Race metadata
    "run_id",
    "race_id",
    "track",
    "date",
    "off_time",
    "race_type",
    "class",
    "distance_yards",
    "going",
    "field_size",
    
    # Market snapshot
    "market_snapshot_ts",
    "input_hash",
    "data_version",
    
    # Signals
    "chaos_score",
    "structure_class",
    "mof_state",
    "mof_confidence",
    "entropy_score",
    "confidence_ceiling",
    
    # Decision
    "top4_chassis",
    "win_candidate",
    "win_overlay",
    "stake_cap",
    "stake_used",
    "status",
    "kill_list_triggers",
    
    # Results (placeholders)
    "result_1st",
    "result_2nd",
    "result_3rd",
    "result_4th",
    "sp_win_candidate",
    "top4_hit_count",
    "win_hit",
    
    # PnL (placeholders)
    "pnl_race",
    "pnl_cumulative",
    "roi_race",
    
    # Audit
    "logged_at"
]

def init_master_race_log():
    """Initialize master race log CSV with headers if not exists."""
    if not MASTER_RACE_LOG.exists():
        with open(MASTER_RACE_LOG, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=MASTER_RACE_LOG_COLUMNS)
            writer.writeheader()
        logger.info(f"Initialized master race log: {MASTER_RACE_LOG}")

def append_master_race_log(result: Dict[str, Any]):
    """
    Append result to master race log.
    
    Args:
        result: OracleExecutionReport JSON from run_engine_full
    """
    init_master_race_log()
    
    race_details = result.get("race_details", {})
    audit = result.get("audit", {})
    signals = result.get("signals", {})
    decision = result.get("decision", {})
    
    # Extract signals
    chaos_score = signals.get("chaos_score", "")
    structure_class = signals.get("structure_class", "")
    mof = signals.get("MOF", {})
    entropy = signals.get("entropy", {})
    
    row = {
        # Race metadata
        "run_id": audit.get("run_id", ""),
        "race_id": race_details.get("race_id", ""),
        "track": race_details.get("track", ""),
        "date": race_details.get("date", ""),
        "off_time": race_details.get("off_time", ""),
        "race_type": race_details.get("race_type", ""),
        "class": race_details.get("class", ""),
        "distance_yards": race_details.get("distance_yards", ""),
        "going": race_details.get("going", ""),
        "field_size": race_details.get("field_size", ""),
        
        # Market snapshot
        "market_snapshot_ts": audit.get("market_snapshot_ts", ""),
        "input_hash": audit.get("input_hash", ""),
        "data_version": audit.get("data_version", ""),
        
        # Signals
        "chaos_score": f"{chaos_score:.3f}" if isinstance(chaos_score, (int, float)) else chaos_score,
        "structure_class": structure_class,
        "mof_state": mof.get("mof_state", ""),
        "mof_confidence": f"{mof.get('mof_confidence', 0):.3f}" if isinstance(mof.get('mof_confidence'), (int, float)) else "",
        "entropy_score": f"{entropy.get('entropy_score', 0):.3f}" if isinstance(entropy.get('entropy_score'), (int, float)) else "",
        "confidence_ceiling": f"{entropy.get('confidence_ceiling', 0):.3f}" if isinstance(entropy.get('confidence_ceiling'), (int, float)) else "",
        
        # Decision
        "top4_chassis": "|".join(decision.get("top4_chassis", [])),
        "win_candidate": decision.get("win_candidate", ""),
        "win_overlay": decision.get("win_overlay", False),
        "stake_cap": f"{decision.get('stake_cap', 0):.2f}",
        "stake_used": f"{decision.get('stake_used', 0):.2f}",
        "status": decision.get("status", ""),
        "kill_list_triggers": "|".join(decision.get("kill_list_triggers", [])),
        
        # Results (placeholders)
        "result_1st": "",
        "result_2nd": "",
        "result_3rd": "",
        "result_4th": "",
        "sp_win_candidate": "",
        "top4_hit_count": "",
        "win_hit": "",
        
        # PnL (placeholders)
        "pnl_race": "",
        "pnl_cumulative": "",
        "roi_race": "",
        
        # Audit
        "logged_at": datetime.utcnow().isoformat()
    }
    
    with open(MASTER_RACE_LOG, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=MASTER_RACE_LOG_COLUMNS)
        writer.writerow(row)
    
    logger.info(f"Logged to master_race_log: {row['run_id']} | {row['race_id']} | {row['status']}")

# ============================================================================
# FADE AUDIT LOG
# ============================================================================

FADE_AUDIT_LOG_COLUMNS = [
    "run_id",
    "race_id",
    "faded_runner",
    "fade_type",
    "reason_codes",
    "finish_pos",
    "sp",
    "success",
    "logged_at"
]

def init_fade_audit_log():
    """Initialize fade audit log CSV with headers if not exists."""
    if not FADE_AUDIT_LOG.exists():
        with open(FADE_AUDIT_LOG, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=FADE_AUDIT_LOG_COLUMNS)
            writer.writeheader()
        logger.info(f"Initialized fade audit log: {FADE_AUDIT_LOG}")

def append_fade_audit_log(
    run_id: str,
    race_id: str,
    faded_runner: str,
    fade_type: str,
    reason_codes: List[str],
    finish_pos: str = "",
    sp: str = "",
    success: str = ""
):
    """
    Append fade event to fade audit log.
    
    Args:
        run_id: Engine run ID
        race_id: Race ID
        faded_runner: Runner ID that was faded
        fade_type: Type of fade (ANCHOR_FRAME, ICM_BANNED, etc.)
        reason_codes: List of reason codes
        finish_pos: Finish position (placeholder)
        sp: Starting price (placeholder)
        success: Success flag (placeholder)
    """
    init_fade_audit_log()
    
    row = {
        "run_id": run_id,
        "race_id": race_id,
        "faded_runner": faded_runner,
        "fade_type": fade_type,
        "reason_codes": "|".join(reason_codes),
        "finish_pos": finish_pos,
        "sp": sp,
        "success": success,
        "logged_at": datetime.utcnow().isoformat()
    }
    
    with open(FADE_AUDIT_LOG, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FADE_AUDIT_LOG_COLUMNS)
        writer.writerow(row)
    
    logger.info(f"Logged to fade_audit_log: {run_id} | {faded_runner} | {fade_type}")

# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def log_engine_result(result: Dict[str, Any]):
    """
    Log engine result to master race log and fade audit log.
    
    Args:
        result: OracleExecutionReport JSON
    """
    # Log to master race log
    append_master_race_log(result)
    
    # Extract fade events from ICM win_banned
    audit = result.get("audit", {})
    race_details = result.get("race_details", {})
    signals = result.get("signals", {})
    icm = signals.get("ICM", {})
    win_banned = icm.get("win_banned", {})
    
    run_id = audit.get("run_id", "")
    race_id = race_details.get("race_id", "")
    
    # Log faded runners
    for runner_id, banned in win_banned.items():
        if banned:
            # Get ICM components for this runner
            icm_components = icm.get("icm_components", {}).get(runner_id, {})
            hard_count = icm.get("hard_constraint_count", {}).get(runner_id, 0)
            
            reason_codes = []
            for comp_name, comp_value in icm_components.items():
                if comp_value >= 0.65:
                    reason_codes.append(f"{comp_name}={comp_value:.2f}")
            
            append_fade_audit_log(
                run_id=run_id,
                race_id=race_id,
                faded_runner=runner_id,
                fade_type="ICM_BANNED",
                reason_codes=reason_codes
            )
