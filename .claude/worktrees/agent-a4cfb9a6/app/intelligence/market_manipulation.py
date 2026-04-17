"""
VÉLØ Oracle - Market Manipulation Detection
Detect suspicious betting patterns and market manipulation
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class MarketManipulationDetector:
    """Detect suspicious market movements and manipulation patterns"""
    
    def __init__(self):
        self.manipulation_patterns = [
            "late_plunge",
            "coordinated_drift",
            "artificial_support",
            "wash_trading",
            "layoff_scheme",
            "steam_move"
        ]
        
        # Thresholds for detection
        self.thresholds = {
            "late_plunge_minutes": 10,  # Minutes before race
            "plunge_percentage": 0.30,   # 30% odds drop
            "drift_percentage": 0.40,    # 40% odds increase
            "volume_spike": 3.0,         # 3x normal volume
            "coordinated_threshold": 0.75 # Correlation threshold
        }
    
    def detect_suspicious_moves(self, odds_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect suspicious betting patterns
        
        Args:
            odds_history: List of odds snapshots with timestamps
            
        Returns:
            Manipulation analysis dictionary
        """
        logger.debug(f"Analyzing {len(odds_history)} odds snapshots for manipulation")
        
        if not odds_history or len(odds_history) < 2:
            return {
                "flag": False,
                "confidence": 0.0,
                "pattern": None,
                "analysis": "Insufficient data for analysis"
            }
        
        # Check for various manipulation patterns
        late_plunge = self._detect_late_plunge(odds_history)
        coordinated_drift = self._detect_coordinated_drift(odds_history)
        artificial_support = self._detect_artificial_support(odds_history)
        steam_move = self._detect_steam_move(odds_history)
        
        # Determine most likely pattern
        patterns = [
            late_plunge,
            coordinated_drift,
            artificial_support,
            steam_move
        ]
        
        # Find highest confidence pattern
        detected_pattern = max(patterns, key=lambda p: p.get("confidence", 0.0))
        
        # Flag if confidence exceeds threshold
        is_suspicious = detected_pattern.get("confidence", 0.0) > 0.65
        
        result = {
            "flag": is_suspicious,
            "confidence": detected_pattern.get("confidence", 0.0),
            "pattern": detected_pattern.get("type") if is_suspicious else None,
            "description": detected_pattern.get("description", ""),
            "analysis": detected_pattern.get("analysis", ""),
            "risk_level": self._calculate_risk_level(detected_pattern),
            "recommended_action": self._recommend_action(detected_pattern),
            "all_patterns": patterns
        }
        
        if is_suspicious:
            logger.warning(f"Suspicious pattern detected: {result['pattern']} (confidence: {result['confidence']:.2f})")
        
        return result
    
    def _detect_late_plunge(self, odds_history: List[Dict]) -> Dict[str, Any]:
        """Detect late plunge pattern (sharp odds drop near race time)"""
        
        if len(odds_history) < 3:
            return {"type": "late_plunge", "confidence": 0.0}
        
        # Get recent odds movement
        recent_odds = odds_history[-3:]
        
        initial_odds = recent_odds[0].get("odds", 5.0)
        final_odds = recent_odds[-1].get("odds", 5.0)
        
        # Calculate percentage drop
        odds_drop = (initial_odds - final_odds) / initial_odds if initial_odds > 0 else 0.0
        
        # Check if drop exceeds threshold
        if odds_drop > self.thresholds["plunge_percentage"]:
            # Check timing (should be close to race time)
            time_to_race = recent_odds[-1].get("minutes_to_race", 60)
            
            if time_to_race <= self.thresholds["late_plunge_minutes"]:
                confidence = min(odds_drop * 1.5, 1.0)
                
                return {
                    "type": "late_plunge",
                    "confidence": confidence,
                    "description": f"Sharp {odds_drop*100:.1f}% odds drop in final minutes",
                    "analysis": "Late plunge may indicate insider information or coordinated betting",
                    "odds_change": odds_drop,
                    "timing": time_to_race
                }
        
        return {"type": "late_plunge", "confidence": 0.0}
    
    def _detect_coordinated_drift(self, odds_history: List[Dict]) -> Dict[str, Any]:
        """Detect coordinated drift (artificial odds inflation)"""
        
        if len(odds_history) < 5:
            return {"type": "coordinated_drift", "confidence": 0.0}
        
        # Calculate steady drift
        odds_values = [snapshot.get("odds", 5.0) for snapshot in odds_history]
        
        # Check for consistent upward movement
        increases = sum(
            1 for i in range(1, len(odds_values))
            if odds_values[i] > odds_values[i-1]
        )
        
        consistency = increases / (len(odds_values) - 1) if len(odds_values) > 1 else 0.0
        
        # Calculate total drift
        total_drift = (odds_values[-1] - odds_values[0]) / odds_values[0] if odds_values[0] > 0 else 0.0
        
        if total_drift > self.thresholds["drift_percentage"] and consistency > 0.7:
            confidence = min(consistency * total_drift, 1.0)
            
            return {
                "type": "coordinated_drift",
                "confidence": confidence,
                "description": f"Sustained {total_drift*100:.1f}% odds drift",
                "analysis": "Coordinated drift may indicate market manipulation to inflate odds",
                "drift_amount": total_drift,
                "consistency": consistency
            }
        
        return {"type": "coordinated_drift", "confidence": 0.0}
    
    def _detect_artificial_support(self, odds_history: List[Dict]) -> Dict[str, Any]:
        """Detect artificial price support (odds held artificially low)"""
        
        if len(odds_history) < 4:
            return {"type": "artificial_support", "confidence": 0.0}
        
        # Check for unusual stability in volatile market
        odds_values = [snapshot.get("odds", 5.0) for snapshot in odds_history]
        volumes = [snapshot.get("volume", 100) for snapshot in odds_history]
        
        # Calculate odds variance
        mean_odds = sum(odds_values) / len(odds_values)
        variance = sum((o - mean_odds) ** 2 for o in odds_values) / len(odds_values)
        
        # Calculate volume variance
        mean_volume = sum(volumes) / len(volumes)
        volume_variance = sum((v - mean_volume) ** 2 for v in volumes) / len(volumes)
        
        # Low odds variance + high volume variance = artificial support
        if variance < 0.1 and volume_variance > mean_volume:
            confidence = min((volume_variance / mean_volume) * 0.5, 1.0)
            
            return {
                "type": "artificial_support",
                "confidence": confidence,
                "description": "Odds artificially stable despite volume fluctuations",
                "analysis": "Artificial support may indicate coordinated betting to maintain odds",
                "variance": variance,
                "volume_variance": volume_variance
            }
        
        return {"type": "artificial_support", "confidence": 0.0}
    
    def _detect_steam_move(self, odds_history: List[Dict]) -> Dict[str, Any]:
        """Detect steam move (sudden sharp odds movement)"""
        
        if len(odds_history) < 3:
            return {"type": "steam_move", "confidence": 0.0}
        
        # Look for sudden sharp movement
        for i in range(1, len(odds_history)):
            prev_odds = odds_history[i-1].get("odds", 5.0)
            curr_odds = odds_history[i].get("odds", 5.0)
            
            # Calculate change
            change = abs(curr_odds - prev_odds) / prev_odds if prev_odds > 0 else 0.0
            
            # Check for spike
            if change > 0.20:  # 20% sudden change
                volume = odds_history[i].get("volume", 100)
                avg_volume = sum(s.get("volume", 100) for s in odds_history) / len(odds_history)
                
                volume_spike = volume / avg_volume if avg_volume > 0 else 1.0
                
                if volume_spike > self.thresholds["volume_spike"]:
                    confidence = min(change * volume_spike * 0.3, 1.0)
                    
                    return {
                        "type": "steam_move",
                        "confidence": confidence,
                        "description": f"Sudden {change*100:.1f}% odds move with {volume_spike:.1f}x volume",
                        "analysis": "Steam move indicates large informed money entering market",
                        "odds_change": change,
                        "volume_spike": volume_spike
                    }
        
        return {"type": "steam_move", "confidence": 0.0}
    
    def _calculate_risk_level(self, pattern: Dict) -> str:
        """Calculate risk level based on pattern confidence"""
        confidence = pattern.get("confidence", 0.0)
        
        if confidence >= 0.85:
            return "CRITICAL"
        elif confidence >= 0.70:
            return "HIGH"
        elif confidence >= 0.50:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _recommend_action(self, pattern: Dict) -> str:
        """Recommend action based on detected pattern"""
        pattern_type = pattern.get("type")
        confidence = pattern.get("confidence", 0.0)
        
        if confidence < 0.65:
            return "MONITOR - Continue normal operations"
        
        if pattern_type == "late_plunge":
            return "CAUTION - Consider following late money or avoiding race"
        
        elif pattern_type == "coordinated_drift":
            return "OPPORTUNITY - Potential value if drift is artificial"
        
        elif pattern_type == "artificial_support":
            return "AVOID - Odds may not reflect true probability"
        
        elif pattern_type == "steam_move":
            return "FOLLOW - Sharp money may have information edge"
        
        return "MONITOR - Assess situation carefully"


def detect_suspicious_moves(odds_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convenience function to detect market manipulation
    
    Args:
        odds_history: List of odds snapshots
        
    Returns:
        Manipulation analysis
    """
    detector = MarketManipulationDetector()
    return detector.detect_suspicious_moves(odds_history)
