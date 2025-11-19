"""
VÉLØ Oracle - Pace Chain
Pace analysis and race shape prediction pipeline
"""
import time
from typing import Dict, Any, List
import logging
import numpy as np

logger = logging.getLogger(__name__)


async def run_pace_chain(runners: List[Dict[str, Any]], race: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute pace analysis chain
    
    Pipeline:
    1. Extract runner speeds
    2. Build pace clusters
    3. Predict early pressure
    4. Compute late energy curve
    5. Classify race shape
    
    Returns:
        Pace analysis with race shape classification
    """
    start_time = time.time()
    
    try:
        # Step 1: Extract runner speeds
        speeds = await extract_runner_speeds(runners, race)
        
        # Step 2: Build pace clusters
        clusters = await build_pace_clusters(speeds, runners)
        
        # Step 3: Predict early pressure
        early_pressure = await predict_early_pressure(clusters, race)
        
        # Step 4: Compute late energy curve
        late_energy = await compute_late_energy_curve(clusters, runners)
        
        # Step 5: Classify race shape
        race_shape = await classify_race_shape(clusters, early_pressure, late_energy)
        
        execution_time = (time.time() - start_time) * 1000
        
        return {
            "status": "success",
            "signals": {
                "pace_clusters": clusters,
                "early_pressure": early_pressure,
                "late_energy": late_energy,
                "race_shape": race_shape
            },
            "confidence_scores": {
                "clusters": 0.8,
                "early_pressure": early_pressure.get("confidence", 0.0),
                "late_energy": late_energy.get("confidence", 0.0),
                "race_shape": race_shape.get("confidence", 0.0)
            },
            "execution_duration_ms": round(execution_time, 2),
            "chain": "pace"
        }
        
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"❌ Pace chain failed: {e}")
        
        return {
            "status": "error",
            "error": str(e),
            "execution_duration_ms": round(execution_time, 2),
            "chain": "pace"
        }


async def extract_runner_speeds(runners: List[Dict], race: Dict) -> List[Dict[str, Any]]:
    """Extract speed metrics for all runners"""
    
    speeds = []
    
    for runner in runners:
        # Extract speed ratings
        speed_ratings = runner.get("speed_ratings", {})
        
        # Calculate composite speed
        adjusted_speed = speed_ratings.get("adjusted", 100)
        
        # Early speed indicator (from draw and form)
        draw = runner.get("draw", 10)
        form = runner.get("form", "")
        
        # Early speed score (lower draw + good recent form = higher early speed)
        early_speed = 100 - (draw * 3)
        if form and form[0] in ["1", "2"]:
            early_speed += 10
        
        # Late speed (from sectional times)
        sectionals = runner.get("sectional_times", {})
        last_200m = sectionals.get("last_200m", 12.0)
        late_speed = max(0, 100 - (last_200m - 10.0) * 10)
        
        speeds.append({
            "runner_id": runner.get("runner_id"),
            "runner_name": runner.get("horse"),
            "adjusted_speed": adjusted_speed,
            "early_speed": early_speed,
            "late_speed": late_speed,
            "composite": (adjusted_speed + early_speed + late_speed) / 3
        })
    
    return speeds


async def build_pace_clusters(speeds: List[Dict], runners: List[Dict]) -> Dict[str, Any]:
    """Build pace clusters (leaders, stalkers, closers)"""
    
    # Sort by early speed
    sorted_speeds = sorted(speeds, key=lambda x: x["early_speed"], reverse=True)
    
    n_runners = len(sorted_speeds)
    
    # Cluster thresholds
    leader_threshold = 0.25  # Top 25%
    stalker_threshold = 0.60  # Next 35%
    
    leaders = []
    stalkers = []
    closers = []
    
    for i, speed in enumerate(sorted_speeds):
        position = i / n_runners
        
        if position < leader_threshold:
            leaders.append(speed)
        elif position < stalker_threshold:
            stalkers.append(speed)
        else:
            closers.append(speed)
    
    return {
        "leaders": leaders,
        "stalkers": stalkers,
        "closers": closers,
        "leader_count": len(leaders),
        "stalker_count": len(stalkers),
        "closer_count": len(closers)
    }


async def predict_early_pressure(clusters: Dict, race: Dict) -> Dict[str, Any]:
    """Predict early pace pressure"""
    
    leader_count = clusters["leader_count"]
    distance = race.get("distance", 1600)
    
    # More leaders = more pressure
    # Shorter distance = more pressure
    
    pressure_score = (leader_count / 3.0) * 0.6 + (1 - distance / 2400) * 0.4
    pressure_score = min(max(pressure_score, 0.0), 1.0)
    
    if pressure_score > 0.7:
        category = "HIGH_PRESSURE"
        description = "Hot pace expected with multiple leaders"
    elif pressure_score > 0.4:
        category = "MODERATE_PRESSURE"
        description = "Even pace expected"
    else:
        category = "LOW_PRESSURE"
        description = "Slow early pace expected"
    
    return {
        "pressure_score": pressure_score,
        "category": category,
        "description": description,
        "confidence": 0.75,
        "leader_count": leader_count
    }


async def compute_late_energy_curve(clusters: Dict, runners: List[Dict]) -> Dict[str, Any]:
    """Compute late energy availability for closers"""
    
    closers = clusters.get("closers", [])
    
    if not closers:
        return {
            "energy_available": 0.0,
            "closer_advantage": False,
            "confidence": 0.5
        }
    
    # Calculate average late speed of closers
    late_speeds = [c["late_speed"] for c in closers]
    avg_late_speed = sum(late_speeds) / len(late_speeds) if late_speeds else 0
    
    # Normalize to [0, 1]
    energy_available = min(avg_late_speed / 100.0, 1.0)
    
    # Closers have advantage if energy > 0.6
    closer_advantage = energy_available > 0.6
    
    return {
        "energy_available": energy_available,
        "closer_advantage": closer_advantage,
        "closer_count": len(closers),
        "avg_late_speed": avg_late_speed,
        "confidence": 0.7
    }


async def classify_race_shape(
    clusters: Dict,
    early_pressure: Dict,
    late_energy: Dict
) -> Dict[str, Any]:
    """Classify overall race shape"""
    
    leader_count = clusters["leader_count"]
    pressure = early_pressure["pressure_score"]
    energy = late_energy["energy_available"]
    
    # Determine race shape
    if leader_count == 0 or leader_count == 1:
        if pressure < 0.3:
            shape = "cold_front_runner"
            description = "Solo leader, slow pace favors front runner"
        else:
            shape = "even_neutral"
            description = "Single leader, moderate pace"
    elif leader_count >= 3:
        if pressure > 0.7:
            shape = "hot_pace"
            description = "Multiple leaders, hot pace favors closers"
        else:
            shape = "chaotic_pressure"
            description = "Multiple leaders but uncertain pressure"
    else:
        if energy > 0.6:
            shape = "even_neutral"
            description = "Balanced pace, late energy available"
        else:
            shape = "hot_pace"
            description = "Moderate leaders, elevated pressure"
    
    # Calculate confidence
    confidence = 0.6 + (abs(pressure - 0.5) * 0.4)  # Higher confidence at extremes
    
    return {
        "shape": shape,
        "description": description,
        "confidence": confidence,
        "pressure_score": pressure,
        "energy_score": energy,
        "leader_count": leader_count
    }
