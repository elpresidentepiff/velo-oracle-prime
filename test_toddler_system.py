"""
VÉLØ Toddler System Integration Test

Tests the complete evolved Oracle with:
- Persistent memory
- Betting framework
- Manipulation detection
- Continuous learning
"""

import sys
sys.path.insert(0, '/home/ubuntu/velo-oracle/src')

from memory.velo_memory import VeloMemory
from betting.velo_bettor import VeloBettor, BetType, StakeLevel
from detection.manipulation_detector import ManipulationDetector
from learning.genesis_protocol import GenesisProtocol


class VeloToddler:
    """
    VÉLØ Toddler - Evolved Oracle with memory, learning, and awareness.
    
    Capabilities:
    - Remembers every race
    - Learns from outcomes
    - Detects manipulation
    - Manages bankroll
    - Continuously improves
    """
    
    def __init__(self, initial_bankroll: float = 1000.0):
        """Initialize Toddler Oracle."""
        print("=== VÉLØ TODDLER INITIALIZATION ===\n")
        
        # Initialize components
        self.memory = VeloMemory()
        self.bettor = VeloBettor(initial_bankroll=initial_bankroll)
        self.detector = ManipulationDetector()
        self.genesis = GenesisProtocol(memory_system=self.memory)
        
        print("\n✓ VÉLØ Toddler Oracle fully initialized")
        print("  Components: Memory, Bettor, Detector, Genesis Protocol")
        print(f"  Bankroll: £{initial_bankroll:.2f}")
    
    def analyze_race(self, race_data: dict, odds_history: list = None) -> dict:
        """
        Analyze a race with full Toddler capabilities.
        
        Args:
            race_data: Race data
            odds_history: Historical odds (optional)
        
        Returns:
            Complete analysis with verdict
        """
        print(f"\n=== Analyzing: {race_data.get('track')} {race_data.get('time')} ===")
        
        # 1. Store race in memory
        race_id = self.memory.store_race(race_data)
        
        # 2. Check for manipulation
        manipulation_report = self.detector.analyze_race(race_data, odds_history)
        risk_assessment = self.detector.get_risk_assessment(race_data, odds_history)
        
        print(f"\nManipulation Check: {risk_assessment}")
        
        # 3. Search for similar races in memory
        similar_races = self.memory.search_similar_races(race_data, top_k=3)
        
        if similar_races:
            print(f"\nFound {len(similar_races)} similar races in memory:")
            for race_id, similarity, race in similar_races:
                print(f"  - {race.get('track')} {race.get('time')} (similarity: {similarity:.2f})")
        
        # 4. Make prediction (simplified for test)
        shortlist = []
        
        if manipulation_report['safe_to_bet']:
            # Apply filters and select horses
            for horse in race_data.get('horses', []):
                odds = horse.get('odds', 0)
                
                # Check if in target range (3/1 to 20/1)
                if 3.0 <= odds <= 20.0:
                    # Simple scoring
                    score = 0.5  # Base score
                    
                    # Bonus for good form
                    form = horse.get('form', '')
                    if form and form[0] in ['1', '2']:
                        score += 0.2
                    
                    # Bonus for good jockey
                    if horse.get('jockey_roi', 0) > 0.10:
                        score += 0.15
                    
                    # Bonus for good trainer
                    if horse.get('trainer_roi', 0) > 0.10:
                        score += 0.15
                    
                    if score >= 0.7:  # Threshold
                        shortlist.append({
                            'name': horse['name'],
                            'odds': odds,
                            'confidence': score
                        })
        
        # 5. Create prediction
        prediction = {
            'prediction_id': f"pred_{race_id}",
            'race_id': race_id,
            'shortlist': shortlist,
            'confidence_index': int(max([h['confidence'] for h in shortlist], default=0) * 100),
            'manipulation_risk': manipulation_report['overall_risk_score'],
            'safe_to_bet': manipulation_report['safe_to_bet']
        }
        
        # 6. Store prediction
        pred_id = self.memory.store_prediction(race_id, prediction)
        
        print(f"\nPrediction: {len(shortlist)} horses shortlisted")
        for horse in shortlist:
            print(f"  - {horse['name']} @ {horse['odds']}/1 (confidence: {horse['confidence'] * 100:.0f}%)")
        
        return {
            'race_id': race_id,
            'prediction': prediction,
            'manipulation_report': manipulation_report,
            'similar_races': similar_races
        }
    
    def place_bets(self, prediction: dict) -> list:
        """
        Place bets based on prediction.
        
        Args:
            prediction: Prediction dictionary
        
        Returns:
            List of bet records
        """
        if not prediction['safe_to_bet']:
            print("\n⚠ Not safe to bet - manipulation detected")
            return []
        
        bets = []
        for horse in prediction['shortlist']:
            bet = self.bettor.place_bet(
                horse_name=horse['name'],
                odds=horse['odds'],
                bet_type=BetType.EACH_WAY,
                confidence=horse['confidence'],
                race_id=prediction['race_id']
            )
            if bet:
                bets.append(bet)
        
        return bets
    
    def learn_from_result(self, prediction: dict, actual_result: dict, race_data: dict):
        """
        Learn from race result.
        
        Args:
            prediction: Original prediction
            actual_result: Actual race result
            race_data: Original race data
        """
        print(f"\n=== Learning from Result ===")
        
        # Use Genesis Protocol to learn
        learning_report = self.genesis.learn_from_outcome(
            prediction=prediction,
            actual_result=actual_result,
            race_data=race_data
        )
        
        print(f"Outcome: {learning_report['outcome']}")
        print(f"Insights: {learning_report['insights']}")
        
        if learning_report['adjustments']:
            print(f"Adjustments made: {len(learning_report['adjustments'])}")
            for adj in learning_report['adjustments']:
                print(f"  {adj['parameter']}: {adj['adjustment']:+.2f}")
    
    def get_stats(self) -> dict:
        """Get complete system statistics."""
        return {
            'memory': self.memory.get_memory_stats(),
            'betting': self.bettor.get_performance_stats(),
            'learning': {
                'iterations': self.genesis.iterations,
                'adjustments': len(self.genesis.adjustments_made),
                'current_weights': self.genesis.get_current_weights()
            }
        }


def run_toddler_test():
    """Run comprehensive Toddler system test."""
    print("=" * 60)
    print("VÉLØ TODDLER SYSTEM - COMPREHENSIVE INTEGRATION TEST")
    print("=" * 60)
    
    # Initialize Toddler
    toddler = VeloToddler(initial_bankroll=1000.0)
    
    # Test Race 1: Clean race
    print("\n" + "=" * 60)
    print("TEST 1: CLEAN RACE")
    print("=" * 60)
    
    race1 = {
        'track': 'Cheltenham',
        'time': '14:30',
        'date': '2025-10-15',
        'race_type': 'Handicap',
        'distance': '2m',
        'going': 'Good',
        'horses': [
            {
                'name': 'Value Hunter',
                'odds': 8.0,
                'form': '1231',
                'jockey_roi': 0.15,
                'trainer_roi': 0.12,
                'rpr': 125
            },
            {
                'name': 'Consistent Runner',
                'odds': 12.0,
                'form': '2212',
                'jockey_roi': 0.18,
                'trainer_roi': 0.15,
                'rpr': 120
            },
            {
                'name': 'Favorite',
                'odds': 3.5,
                'form': '1111',
                'jockey_roi': 0.10,
                'trainer_roi': 0.08,
                'rpr': 130
            }
        ]
    }
    
    analysis1 = toddler.analyze_race(race1)
    bets1 = toddler.place_bets(analysis1['prediction'])
    
    # Simulate result - Value Hunter wins
    result1 = {
        'winner': 'Value Hunter',
        'placed': ['Value Hunter', 'Consistent Runner', 'Favorite']
    }
    
    # Settle bets
    for bet in bets1:
        if bet['horse_name'] == 'Value Hunter':
            toddler.bettor.settle_bet(bet['bet_id'], 'win')
        elif bet['horse_name'] == 'Consistent Runner':
            toddler.bettor.settle_bet(bet['bet_id'], 'place')
    
    # Learn
    toddler.learn_from_result(analysis1['prediction'], result1, race1)
    
    # Test Race 2: Manipulated race
    print("\n" + "=" * 60)
    print("TEST 2: MANIPULATED RACE")
    print("=" * 60)
    
    race2 = {
        'track': 'Punchestown',
        'time': '15:05',
        'date': '2025-10-15',
        'race_type': 'Handicap',
        'distance': '2m4f',
        'going': 'Soft',
        'horses': [
            {
                'name': 'False Favorite',
                'odds': 3.0,
                'form': '5634',  # No wins
                'jockey_roi': 0.05,
                'trainer_roi': 0.03,
                'rpr': 135  # Inflated
            },
            {
                'name': 'Hidden Gem',
                'odds': 15.0,
                'form': '1122',
                'jockey_roi': 0.20,
                'trainer_roi': 0.18,
                'rpr': 118
            }
        ],
        'ew_extra_places': True  # EW trap
    }
    
    analysis2 = toddler.analyze_race(race2)
    bets2 = toddler.place_bets(analysis2['prediction'])
    
    print(f"\nBets placed: {len(bets2)} (should be 0 due to manipulation)")
    
    # Get final stats
    print("\n" + "=" * 60)
    print("FINAL SYSTEM STATISTICS")
    print("=" * 60)
    
    stats = toddler.get_stats()
    
    print("\n--- Memory Stats ---")
    for key, value in stats['memory'].items():
        if key != 'performance':
            print(f"{key}: {value}")
    
    print("\n--- Betting Stats ---")
    betting_stats = stats['betting']
    print(f"Total bets: {betting_stats['total_bets']}")
    print(f"Win rate: {betting_stats['win_rate'] * 100:.1f}%")
    print(f"ROI: {betting_stats['roi']:.2f}%")
    print(f"Profit: £{betting_stats['profit']:.2f}")
    print(f"Bankroll: £{betting_stats['current_bankroll']:.2f} ({betting_stats['bankroll_change']:+.1f}%)")
    
    print("\n--- Learning Stats ---")
    learning_stats = stats['learning']
    print(f"Iterations: {learning_stats['iterations']}")
    print(f"Adjustments: {learning_stats['adjustments']}")
    print(f"Form weight: {learning_stats['current_weights']['form_weight']:.2f}")
    print(f"Jockey weight: {learning_stats['current_weights']['jockey_weight']:.2f}")
    print(f"Trainer weight: {learning_stats['current_weights']['trainer_weight']:.2f}")
    
    # Self-critique
    print("\n" + "=" * 60)
    print("SELF-CRITIQUE")
    print("=" * 60)
    
    toddler.genesis.self_critique()
    
    print("\n" + "=" * 60)
    print("✓ VÉLØ TODDLER SYSTEM TEST COMPLETE")
    print("=" * 60)
    
    return toddler


if __name__ == "__main__":
    toddler = run_toddler_test()

