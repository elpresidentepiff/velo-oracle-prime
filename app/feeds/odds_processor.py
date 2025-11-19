"""
VÉLØ Oracle - Odds Processor
Process and normalize odds data
"""
from typing import Dict, Any, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OddsProcessor:
    """
    Process and normalize odds data
    
    Functions:
    - Normalize to internal format
    - Calculate implied probabilities
    - Detect arbitrage opportunities
    - Compute overround
    """
    
    @staticmethod
    def normalize_odds(
        odds_data: Dict[str, Any],
        source_format: str = "decimal"
    ) -> Dict[str, Any]:
        """
        Normalize odds to internal format
        
        Args:
            odds_data: Raw odds data
            source_format: decimal, fractional, american
            
        Returns:
            Normalized odds
        """
        if source_format == "decimal":
            decimal_odds = odds_data.get('odds', 1.0)
        elif source_format == "fractional":
            # Convert fractional to decimal (e.g., "5/1" -> 6.0)
            frac = odds_data.get('odds', '1/1')
            num, den = map(float, frac.split('/'))
            decimal_odds = (num / den) + 1.0
        elif source_format == "american":
            # Convert American to decimal
            american = odds_data.get('odds', 100)
            if american > 0:
                decimal_odds = (american / 100) + 1.0
            else:
                decimal_odds = (100 / abs(american)) + 1.0
        else:
            decimal_odds = 1.0
        
        # Calculate implied probability
        implied_prob = 1.0 / decimal_odds if decimal_odds > 0 else 0.0
        
        return {
            'runner_id': odds_data.get('runner_id'),
            'runner_name': odds_data.get('runner_name'),
            'odds_decimal': decimal_odds,
            'implied_probability': implied_prob,
            'source': odds_data.get('source', 'unknown'),
            'timestamp': odds_data.get('timestamp')
        }
    
    @staticmethod
    def calculate_overround(runners: List[Dict[str, Any]]) -> float:
        """
        Calculate market overround (bookmaker margin)
        
        Args:
            runners: List of runner odds
            
        Returns:
            Overround percentage
        """
        total_implied_prob = sum(
            1.0 / r['odds_decimal'] for r in runners if r.get('odds_decimal', 0) > 0
        )
        
        overround = (total_implied_prob - 1.0) * 100
        
        return overround
    
    @staticmethod
    def detect_arbitrage(
        runners: List[Dict[str, Any]],
        threshold: float = 0.0
    ) -> Dict[str, Any]:
        """
        Detect arbitrage opportunities
        
        Args:
            runners: List of runner odds from different bookmakers
            threshold: Profit threshold (0 = any arbitrage)
            
        Returns:
            Arbitrage details
        """
        # Group by runner
        runner_odds = {}
        for r in runners:
            runner_id = r['runner_id']
            if runner_id not in runner_odds:
                runner_odds[runner_id] = []
            runner_odds[runner_id].append(r)
        
        # Find best odds for each runner
        best_odds = {}
        for runner_id, odds_list in runner_odds.items():
            best = max(odds_list, key=lambda x: x['odds_decimal'])
            best_odds[runner_id] = best
        
        # Calculate total implied probability with best odds
        total_implied = sum(
            1.0 / odds['odds_decimal'] for odds in best_odds.values()
        )
        
        # Arbitrage exists if total < 1.0
        is_arbitrage = total_implied < 1.0
        profit_percent = (1.0 - total_implied) * 100 if is_arbitrage else 0.0
        
        return {
            'is_arbitrage': is_arbitrage,
            'profit_percent': profit_percent,
            'total_implied_probability': total_implied,
            'best_odds': best_odds
        }
    
    @staticmethod
    def compute_value_bets(
        model_probabilities: Dict[str, float],
        market_odds: Dict[str, float],
        edge_threshold: float = 0.05
    ) -> List[Dict[str, Any]]:
        """
        Find value bets (model prob > implied prob)
        
        Args:
            model_probabilities: Model predictions {runner_id: prob}
            market_odds: Market odds {runner_id: decimal_odds}
            edge_threshold: Minimum edge to qualify
            
        Returns:
            List of value bets
        """
        value_bets = []
        
        for runner_id, model_prob in model_probabilities.items():
            if runner_id not in market_odds:
                continue
            
            odds = market_odds[runner_id]
            implied_prob = 1.0 / odds if odds > 0 else 0.0
            
            edge = model_prob - implied_prob
            
            if edge > edge_threshold:
                value_bets.append({
                    'runner_id': runner_id,
                    'model_probability': model_prob,
                    'implied_probability': implied_prob,
                    'odds_decimal': odds,
                    'edge': edge,
                    'edge_percent': edge * 100,
                    'expected_value': model_prob * odds - 1.0
                })
        
        # Sort by edge
        value_bets.sort(key=lambda x: x['edge'], reverse=True)
        
        return value_bets


if __name__ == "__main__":
    # Test odds processor
    print("="*60)
    print("Odds Processor Test")
    print("="*60)
    
    processor = OddsProcessor()
    
    # Test normalization
    print("\n1. Odds Normalization:")
    
    decimal_odds = {'runner_id': 'R1', 'runner_name': 'Horse A', 'odds': 3.5}
    normalized = processor.normalize_odds(decimal_odds, 'decimal')
    print(f"  Decimal 3.5 → Implied prob: {normalized['implied_probability']:.4f}")
    
    # Test overround
    print("\n2. Overround Calculation:")
    
    runners = [
        {'runner_id': 'R1', 'odds_decimal': 3.5},
        {'runner_id': 'R2', 'odds_decimal': 4.0},
        {'runner_id': 'R3', 'odds_decimal': 8.0},
        {'runner_id': 'R4', 'odds_decimal': 12.0}
    ]
    
    overround = processor.calculate_overround(runners)
    print(f"  Market overround: {overround:.2f}%")
    
    # Test value bets
    print("\n3. Value Bet Detection:")
    
    model_probs = {
        'R1': 0.35,  # Model thinks 35% chance
        'R2': 0.20,
        'R3': 0.15,
        'R4': 0.05
    }
    
    market_odds = {
        'R1': 3.5,   # Implied 28.6% - VALUE!
        'R2': 4.0,   # Implied 25% - no value
        'R3': 8.0,   # Implied 12.5% - VALUE!
        'R4': 12.0   # Implied 8.3% - no value
    }
    
    value_bets = processor.compute_value_bets(model_probs, market_odds, edge_threshold=0.02)
    
    print(f"  Found {len(value_bets)} value bets:")
    for vb in value_bets:
        print(f"    {vb['runner_id']}: Edge {vb['edge_percent']:+.1f}% (EV: {vb['expected_value']:+.2f})")
    
    print("\n✅ Odds processor test complete")
