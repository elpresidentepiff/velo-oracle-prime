"""
V10 Entrypoint with ENGINE_FULL mode
Wires V12 Market-Intent Stack into production
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import json

from app.velo_v12_intent_stack import (
    Race, Runner, OddsPoint,
    run_engine_full
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# MODE ENUM
# ============================================================================

class EngineMode:
    """Engine execution modes."""
    ENGINE_FULL = "ENGINE_FULL"
    LEGACY_V10 = "LEGACY_V10"

# ============================================================================
# V10 ENTRYPOINT
# ============================================================================

def run_velo_v10(
    race_data: Dict[str, Any],
    mode: str = EngineMode.ENGINE_FULL,
    bankroll: float = 10000.0
) -> Dict[str, Any]:
    """
    V10 entrypoint with mode switching.
    
    Args:
        race_data: Race data dict matching Race schema
        mode: ENGINE_FULL or LEGACY_V10
        bankroll: Current bankroll for stake calculation
        
    Returns:
        OracleExecutionReport JSON
    """
    logger.info(f"V10 Entrypoint | Mode: {mode} | Race: {race_data.get('race_id', 'UNKNOWN')}")
    
    if mode == EngineMode.ENGINE_FULL:
        return run_engine_full_mode(race_data, bankroll)
    elif mode == EngineMode.LEGACY_V10:
        return run_legacy_v10_mode(race_data, bankroll)
    else:
        raise ValueError(f"Unknown mode: {mode}")

# ============================================================================
# ENGINE_FULL MODE
# ============================================================================

def run_engine_full_mode(race_data: Dict[str, Any], bankroll: float) -> Dict[str, Any]:
    """
    Run ENGINE_FULL mode using V12 Market-Intent Stack.
    
    Args:
        race_data: Race data dict
        bankroll: Current bankroll
        
    Returns:
        OracleExecutionReport JSON
    """
    try:
        # Parse race data into Race object
        race = parse_race_data(race_data)
        
        # Run V12 engine
        result = run_engine_full(race, bankroll, data_version="v12-alpha")
        
        logger.info(f"ENGINE_FULL | Race: {race.race_id} | Status: {result['decision']['status']}")
        
        return result
        
    except Exception as e:
        logger.error(f"ENGINE_FULL error: {e}", exc_info=True)
        return {
            "race_details": {
                "race_id": race_data.get("race_id", "UNKNOWN"),
                "track": race_data.get("track", "UNKNOWN"),
                "date": race_data.get("date", "UNKNOWN"),
                "off_time": race_data.get("off_time", "UNKNOWN")
            },
            "audit": {
                "run_id": "ERROR",
                "mode": "ENGINE_FULL",
                "input_hash": "ERROR",
                "data_version": "v12-alpha",
                "market_snapshot_ts": race_data.get("market_snapshot_ts", "")
            },
            "signals": {},
            "decision": {
                "top4_chassis": [],
                "win_candidate": None,
                "win_overlay": False,
                "stake_cap": 0.0,
                "stake_used": 0.0,
                "kill_list_triggers": [f"ENGINE_ERROR:{str(e)}"],
                "status": "ERROR"
            }
        }

# ============================================================================
# LEGACY V10 MODE (Placeholder)
# ============================================================================

def run_legacy_v10_mode(race_data: Dict[str, Any], bankroll: float) -> Dict[str, Any]:
    """
    Run LEGACY_V10 mode (placeholder for existing V10 logic).
    
    Args:
        race_data: Race data dict
        bankroll: Current bankroll
        
    Returns:
        OracleExecutionReport JSON
    """
    logger.warning("LEGACY_V10 mode not implemented - use ENGINE_FULL")
    return {
        "race_details": {
            "race_id": race_data.get("race_id", "UNKNOWN"),
            "track": race_data.get("track", "UNKNOWN"),
            "date": race_data.get("date", "UNKNOWN"),
            "off_time": race_data.get("off_time", "UNKNOWN")
        },
        "audit": {
            "run_id": "LEGACY",
            "mode": "LEGACY_V10",
            "input_hash": "",
            "data_version": "v10",
            "market_snapshot_ts": race_data.get("market_snapshot_ts", "")
        },
        "signals": {},
        "decision": {
            "top4_chassis": [],
            "win_candidate": None,
            "win_overlay": False,
            "stake_cap": 0.0,
            "stake_used": 0.0,
            "kill_list_triggers": ["LEGACY_MODE_NOT_IMPLEMENTED"],
            "status": "NOT_IMPLEMENTED"
        }
    }

# ============================================================================
# DATA PARSING
# ============================================================================

def parse_race_data(data: Dict[str, Any]) -> Race:
    """
    Parse race data dict into Race object.
    
    Args:
        data: Race data dict
        
    Returns:
        Race object
    """
    # Parse runners
    runners = []
    for r_data in data.get("runners", []):
        # Parse odds timeline
        odds_timeline = None
        if r_data.get("odds_timeline"):
            odds_timeline = [
                OddsPoint(ts=pt["ts"], odds=pt["odds"])
                for pt in r_data["odds_timeline"]
            ]
        
        # Parse place odds timeline
        place_odds_timeline = None
        if r_data.get("place_odds_timeline"):
            place_odds_timeline = [
                OddsPoint(ts=pt["ts"], odds=pt["odds"])
                for pt in r_data["place_odds_timeline"]
            ]
        
        runner = Runner(
            runner_id=r_data.get("runner_id", r_data.get("horse", "UNKNOWN")),
            horse=r_data["horse"],
            weight_lbs=r_data["weight_lbs"],
            jockey=r_data["jockey"],
            trainer=r_data["trainer"],
            odds_live=r_data["odds_live"],
            claims_lbs=r_data.get("claims_lbs", 0),
            stall=r_data.get("stall"),
            OR=r_data.get("OR"),
            TS=r_data.get("TS"),
            RPR=r_data.get("RPR"),
            owner=r_data.get("owner"),
            headgear=r_data.get("headgear"),
            run_style=r_data.get("run_style"),
            odds_timeline=odds_timeline,
            place_odds_live=r_data.get("place_odds_live"),
            place_odds_timeline=place_odds_timeline,
            comments=r_data.get("comments"),
            last_runs=r_data.get("last_runs")
        )
        runners.append(runner)
    
    # Create race object
    race = Race(
        race_id=data["race_id"],
        track=data["track"],
        date=data["date"],
        off_time=data["off_time"],
        race_type=data["race_type"],
        klass=data.get("class", data.get("klass", "UNKNOWN")),
        distance_yards=data["distance_yards"],
        going=data["going"],
        rail_moves=data.get("rail_moves"),
        field_size=data["field_size"],
        market_snapshot_ts=data["market_snapshot_ts"],
        nr_list=data.get("nr_list", []),
        runners=runners
    )
    
    return race

# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    """CLI interface for testing."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m app.v10_entrypoint <race_data.json>")
        sys.exit(1)
    
    # Load race data
    with open(sys.argv[1], 'r') as f:
        race_data = json.load(f)
    
    # Run engine
    result = run_velo_v10(race_data, mode=EngineMode.ENGINE_FULL)
    
    # Print result
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
