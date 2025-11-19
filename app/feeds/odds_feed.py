"""
VÉLØ Oracle - Odds Feed Integration
Capture and process real-time odds data
"""
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OddsFeed:
    """
    Real-time odds feed integration
    
    Capabilities:
    - Capture odds snapshots
    - Normalize to internal format
    - Compute steam/drift volatility
    - Save 2K+ snapshots/day
    """
    
    def __init__(self, storage_path: str = "data/odds_snapshots"):
        self.storage_path = storage_path
        self.snapshots = []
        self.current_odds = {}
    
    def capture_snapshot(
        self,
        race_id: str,
        runners: List[Dict[str, Any]],
        source: str = "betfair"
    ) -> Dict[str, Any]:
        """
        Capture odds snapshot
        
        Args:
            race_id: Unique race identifier
            runners: List of runner odds data
            source: Odds source (betfair, sportsbet, etc.)
            
        Returns:
            Snapshot metadata
        """
        snapshot = {
            'timestamp': datetime.utcnow().isoformat(),
            'race_id': race_id,
            'source': source,
            'runners': runners,
            'snapshot_id': f"{race_id}_{datetime.utcnow().timestamp()}"
        }
        
        self.snapshots.append(snapshot)
        self.current_odds[race_id] = runners
        
        logger.info(f"✅ Captured snapshot for {race_id} ({len(runners)} runners)")
        
        return snapshot
    
    def get_current_odds(self, race_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get current odds for a race"""
        return self.current_odds.get(race_id)
    
    def get_odds_history(
        self,
        race_id: str,
        runner_id: str = None
    ) -> List[Dict[str, Any]]:
        """Get odds history for a race/runner"""
        
        history = [s for s in self.snapshots if s['race_id'] == race_id]
        
        if runner_id:
            # Filter for specific runner
            filtered = []
            for snapshot in history:
                runner_data = next(
                    (r for r in snapshot['runners'] if r.get('runner_id') == runner_id),
                    None
                )
                if runner_data:
                    filtered.append({
                        'timestamp': snapshot['timestamp'],
                        'odds': runner_data.get('odds_decimal'),
                        'volume': runner_data.get('volume', 0)
                    })
            return filtered
        
        return history
    
    def compute_odds_movement(
        self,
        race_id: str,
        runner_id: str,
        window_minutes: int = 60
    ) -> Dict[str, float]:
        """
        Compute odds movement over time window
        
        Returns:
            Movement statistics
        """
        history = self.get_odds_history(race_id, runner_id)
        
        if len(history) < 2:
            return {
                'movement_percent': 0.0,
                'volatility': 0.0,
                'trend': 'stable'
            }
        
        # Get first and last odds
        first_odds = history[0]['odds']
        last_odds = history[-1]['odds']
        
        # Calculate movement
        movement_percent = ((last_odds - first_odds) / first_odds * 100) if first_odds > 0 else 0.0
        
        # Calculate volatility (std dev of odds)
        odds_values = [h['odds'] for h in history]
        import numpy as np
        volatility = float(np.std(odds_values))
        
        # Determine trend
        if movement_percent < -5:
            trend = 'steaming'  # Odds shortening (backing)
        elif movement_percent > 5:
            trend = 'drifting'  # Odds lengthening (laying)
        else:
            trend = 'stable'
        
        return {
            'movement_percent': movement_percent,
            'volatility': volatility,
            'trend': trend,
            'first_odds': first_odds,
            'last_odds': last_odds,
            'snapshots_count': len(history)
        }
    
    def detect_steam_move(
        self,
        race_id: str,
        runner_id: str,
        threshold: float = 10.0
    ) -> bool:
        """
        Detect steam move (rapid odds shortening)
        
        Args:
            threshold: Percentage drop to qualify as steam
            
        Returns:
            True if steam detected
        """
        movement = self.compute_odds_movement(race_id, runner_id, window_minutes=15)
        
        is_steam = movement['movement_percent'] < -threshold
        
        if is_steam:
            logger.warning(f"🔥 STEAM DETECTED: {runner_id} ({movement['movement_percent']:.1f}%)")
        
        return is_steam
    
    def save_snapshots(self, filepath: str = None):
        """Save snapshots to file"""
        if filepath is None:
            filepath = f"{self.storage_path}/snapshots_{datetime.utcnow().date()}.json"
        
        with open(filepath, 'w') as f:
            json.dump(self.snapshots, f, indent=2)
        
        logger.info(f"✅ Saved {len(self.snapshots)} snapshots to {filepath}")
    
    def load_snapshots(self, filepath: str):
        """Load snapshots from file"""
        try:
            with open(filepath, 'r') as f:
                self.snapshots = json.load(f)
            logger.info(f"✅ Loaded {len(self.snapshots)} snapshots from {filepath}")
        except Exception as e:
            logger.error(f"❌ Failed to load snapshots: {e}")


if __name__ == "__main__":
    # Test odds feed
    print("="*60)
    print("Odds Feed Test")
    print("="*60)
    
    feed = OddsFeed()
    
    # Simulate odds snapshots
    import numpy as np
    
    race_id = "TEST_RACE_001"
    
    # Capture 10 snapshots with changing odds
    base_odds = [3.5, 5.0, 8.0, 12.0]
    
    for i in range(10):
        runners = []
        for j, base in enumerate(base_odds):
            # Simulate odds movement (runner 0 steaming, others stable)
            if j == 0:
                odds = base * (1.0 - i * 0.05)  # Steaming (shortening)
            else:
                odds = base + np.random.normal(0, 0.2)
            
            runners.append({
                'runner_id': f"RUNNER_{j}",
                'runner_name': f"Horse {j+1}",
                'odds_decimal': max(1.01, odds),
                'volume': np.random.randint(1000, 10000)
            })
        
        feed.capture_snapshot(race_id, runners)
    
    # Analyze movement
    print("\nOdds Movement Analysis:")
    for i in range(4):
        runner_id = f"RUNNER_{i}"
        movement = feed.compute_odds_movement(race_id, runner_id)
        
        print(f"\n{runner_id}:")
        print(f"  Movement: {movement['movement_percent']:+.1f}%")
        print(f"  Volatility: {movement['volatility']:.2f}")
        print(f"  Trend: {movement['trend']}")
        print(f"  Odds: {movement['first_odds']:.2f} → {movement['last_odds']:.2f}")
    
    # Check for steam
    print("\nSteam Detection:")
    for i in range(4):
        runner_id = f"RUNNER_{i}"
        is_steam = feed.detect_steam_move(race_id, runner_id, threshold=10.0)
        print(f"  {runner_id}: {'🔥 STEAM' if is_steam else '✓ Normal'}")
    
    print("\n✅ Odds feed test complete")
