"""
VÉLØ v9.0++ CHAREX - VÉLØ SYNTH Agent

Monitors live odds, Betfair drift, and syndicate behavior.
Detects market manipulation and price anomalies.
"""

import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict


class VeloSynth:
    """
    VÉLØ SYNTH - Market Odds Monitor
    
    Tracks odds movements, detects drifts, and identifies
    market manipulation patterns.
    """
    
    def __init__(self):
        """Initialize VÉLØ SYNTH agent."""
        self.name = "VÉLØ_SYNTH"
        self.version = "v9.0++"
        self.status = "STANDBY"
        
        # Odds tracking
        self.odds_history = defaultdict(list)  # {horse_name: [(timestamp, odds), ...]}
        self.market_snapshots = []
        
        # Alert thresholds
        self.drift_threshold = 0.20  # 20% drift triggers alert
        self.crash_threshold = 0.15  # 15% crash in < 15 mins
        self.crash_window = 900  # 15 minutes in seconds
    
    def activate(self) -> None:
        """Activate VÉLØ SYNTH agent."""
        self.status = "ACTIVE"
        print(f"\n📊 {self.name} ACTIVATED")
        print(f"Drift Threshold: {self.drift_threshold * 100}%")
        print(f"Crash Threshold: {self.crash_threshold * 100}% in {self.crash_window/60} mins")
        print(f"Market Monitoring: LIVE\n")
    
    def record_odds(self, horse_name: str, odds: float, timestamp: Optional[datetime] = None) -> None:
        """
        Record odds for a horse at a specific time.
        
        Args:
            horse_name: Name of the horse
            odds: Current odds value
            timestamp: Time of recording (defaults to now)
        """
        if self.status != "ACTIVE":
            raise RuntimeError("VÉLØ SYNTH not active. Call activate() first.")
        
        if timestamp is None:
            timestamp = datetime.now()
        
        self.odds_history[horse_name].append((timestamp, odds))
    
    def record_market_snapshot(self, race_id: str, market_data: Dict) -> None:
        """
        Record a complete market snapshot for a race.
        
        Args:
            race_id: Unique race identifier
            market_data: Dictionary of {horse_name: odds}
        """
        if self.status != "ACTIVE":
            raise RuntimeError("VÉLØ SYNTH not active. Call activate() first.")
        
        snapshot = {
            "race_id": race_id,
            "timestamp": datetime.now(),
            "market": market_data.copy()
        }
        
        self.market_snapshots.append(snapshot)
        
        # Also record individual odds
        for horse_name, odds in market_data.items():
            self.record_odds(horse_name, odds, snapshot["timestamp"])
    
    def detect_drift(self, horse_name: str) -> Optional[Dict]:
        """
        Detect odds drift for a specific horse.
        
        Args:
            horse_name: Name of the horse
            
        Returns:
            Drift analysis or None if insufficient data
        """
        if horse_name not in self.odds_history:
            return None
        
        history = self.odds_history[horse_name]
        
        if len(history) < 2:
            return None
        
        # Compare first and last odds
        first_timestamp, first_odds = history[0]
        last_timestamp, last_odds = history[-1]
        
        drift_amount = last_odds - first_odds
        drift_percentage = (drift_amount / first_odds) if first_odds > 0 else 0.0
        
        drift_type = "LENGTHENING" if drift_amount > 0 else "SHORTENING"
        
        # Determine if drift is significant
        is_significant = abs(drift_percentage) >= self.drift_threshold
        
        return {
            "horse": horse_name,
            "first_odds": first_odds,
            "last_odds": last_odds,
            "drift_amount": drift_amount,
            "drift_percentage": round(drift_percentage * 100, 2),
            "drift_type": drift_type,
            "is_significant": is_significant,
            "time_span": (last_timestamp - first_timestamp).total_seconds() / 60,  # minutes
            "interpretation": self._interpret_drift(drift_type, drift_percentage, is_significant)
        }
    
    def _interpret_drift(self, drift_type: str, drift_percentage: float, is_significant: bool) -> str:
        """
        Interpret what the drift means tactically.
        
        Args:
            drift_type: LENGTHENING or SHORTENING
            drift_percentage: Percentage change
            is_significant: Whether drift exceeds threshold
            
        Returns:
            Tactical interpretation
        """
        if not is_significant:
            return "STABLE - Normal market fluctuation"
        
        if drift_type == "LENGTHENING":
            if drift_percentage > 0.30:
                return "MAJOR DRIFT - Market losing confidence. Potential negative info."
            else:
                return "GOOD DRIFT - Stable lengthening. Value opportunity if fundamentals strong."
        else:  # SHORTENING
            if abs(drift_percentage) > 0.30:
                return "STEAM - Heavy money coming. Check for late info or manipulation."
            else:
                return "SUPPORT - Gradual shortening. Market confidence building."
    
    def detect_crash(self, horse_name: str) -> Optional[Dict]:
        """
        Detect sudden odds crash (potential red flag).
        
        Args:
            horse_name: Name of the horse
            
        Returns:
            Crash analysis or None
        """
        if horse_name not in self.odds_history:
            return None
        
        history = self.odds_history[horse_name]
        
        if len(history) < 2:
            return None
        
        current_time = datetime.now()
        
        # Check for crash in last 15 minutes
        recent_history = [
            (ts, odds) for ts, odds in history
            if (current_time - ts).total_seconds() <= self.crash_window
        ]
        
        if len(recent_history) < 2:
            return None
        
        first_timestamp, first_odds = recent_history[0]
        last_timestamp, last_odds = recent_history[-1]
        
        crash_amount = first_odds - last_odds
        crash_percentage = (crash_amount / first_odds) if first_odds > 0 else 0.0
        
        is_crash = crash_percentage >= self.crash_threshold
        
        if is_crash:
            return {
                "horse": horse_name,
                "crash_detected": True,
                "before_odds": first_odds,
                "after_odds": last_odds,
                "crash_percentage": round(crash_percentage * 100, 2),
                "time_window_minutes": (last_timestamp - first_timestamp).total_seconds() / 60,
                "warning": "⚠️ CRASH ALERT - Odds crashed <15 mins pre-race. HIGH RISK."
            }
        
        return None
    
    def analyze_market_behavior(self, race_id: str) -> Dict:
        """
        Analyze overall market behavior for a race.
        
        Args:
            race_id: Unique race identifier
            
        Returns:
            Market analysis
        """
        # Get all snapshots for this race
        race_snapshots = [s for s in self.market_snapshots if s["race_id"] == race_id]
        
        if len(race_snapshots) < 2:
            return {
                "status": "INSUFFICIENT_DATA",
                "message": "Need at least 2 market snapshots for analysis"
            }
        
        first_snapshot = race_snapshots[0]
        last_snapshot = race_snapshots[-1]
        
        # Identify movers
        movers = []
        for horse_name in first_snapshot["market"]:
            if horse_name in last_snapshot["market"]:
                first_odds = first_snapshot["market"][horse_name]
                last_odds = last_snapshot["market"][horse_name]
                
                change = last_odds - first_odds
                change_pct = (change / first_odds * 100) if first_odds > 0 else 0.0
                
                if abs(change_pct) >= 10:  # 10% threshold for "mover"
                    movers.append({
                        "horse": horse_name,
                        "from": first_odds,
                        "to": last_odds,
                        "change_pct": round(change_pct, 2),
                        "direction": "DRIFT" if change > 0 else "STEAM"
                    })
        
        # Sort by absolute change
        movers.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
        
        return {
            "status": "ANALYZED",
            "race_id": race_id,
            "snapshots_count": len(race_snapshots),
            "time_span_minutes": (last_snapshot["timestamp"] - first_snapshot["timestamp"]).total_seconds() / 60,
            "movers": movers[:5],  # Top 5 movers
            "market_volatility": "HIGH" if len(movers) > 5 else "MODERATE" if len(movers) > 2 else "STABLE"
        }
    
    def get_current_odds(self, horse_name: str) -> Optional[float]:
        """
        Get most recent odds for a horse.
        
        Args:
            horse_name: Name of the horse
            
        Returns:
            Latest odds or None
        """
        if horse_name not in self.odds_history or not self.odds_history[horse_name]:
            return None
        
        return self.odds_history[horse_name][-1][1]
    
    def clear_history(self) -> None:
        """Clear all odds history and snapshots."""
        self.odds_history.clear()
        self.market_snapshots.clear()
        print("🗑️  SYNTH: Odds history cleared")
    
    def get_status(self) -> Dict:
        """Get current agent status."""
        return {
            "agent": self.name,
            "version": self.version,
            "status": self.status,
            "horses_tracked": len(self.odds_history),
            "market_snapshots": len(self.market_snapshots),
            "drift_threshold": f"{self.drift_threshold * 100}%",
            "crash_threshold": f"{self.crash_threshold * 100}%"
        }


def main():
    """Test VÉLØ SYNTH agent."""
    print("📊 VÉLØ SYNTH - Market Odds Monitor")
    print("="*60)
    
    synth = VeloSynth()
    synth.activate()
    
    # Simulate odds tracking
    print("\n🧪 Testing odds tracking...")
    
    # Simulate drift
    synth.record_odds("Test Runner A", 8.0)
    time.sleep(0.1)
    synth.record_odds("Test Runner A", 9.0)
    time.sleep(0.1)
    synth.record_odds("Test Runner A", 10.5)
    
    drift = synth.detect_drift("Test Runner A")
    print(f"\n📈 Drift Analysis:")
    if drift:
        for key, value in drift.items():
            print(f"  {key}: {value}")
    
    # Display status
    status = synth.get_status()
    print(f"\n📊 SYNTH Status:")
    for key, value in status.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

