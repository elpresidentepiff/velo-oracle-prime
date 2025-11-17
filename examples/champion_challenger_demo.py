"""
VÉLØ Oracle - Champion/Challenger Framework Demo

This script demonstrates how to use the Champion/Challenger framework
for safe deployment of the intelligence stack.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import numpy as np
from deployment.champion_challenger import ChampionChallengerFramework
from deployment.models import (
    BenterBaselineModel,
    BenterPlusSQPEModel,
    BenterPlusSQPETIEModel,
    FullIntelligenceStackModel
)


def create_sample_race_data(race_id: str, num_horses: int = 10) -> pd.DataFrame:
    """Create sample race data for demonstration."""
    horses = []
    
    for i in range(num_horses):
        horse = {
            'race_id': race_id,
            'horse_name': f'Horse_{i+1}',
            'odds': np.random.uniform(2.0, 20.0),
            'speed_rating': np.random.uniform(70, 100),
            'class_rating': np.random.uniform(60, 95),
            'weight': np.random.uniform(120, 140),
            'jockey_rating': np.random.uniform(70, 95)
        }
        horses.append(horse)
    
    return pd.DataFrame(horses)


def simulate_race_results(race_data: pd.DataFrame) -> dict:
    """Simulate race results (random winner for demo)."""
    results = {}
    
    # Pick a random winner
    winner_idx = np.random.randint(0, len(race_data))
    
    for idx, horse in race_data.iterrows():
        horse_name = horse['horse_name']
        if idx == winner_idx:
            results[horse_name] = 'win'
        else:
            results[horse_name] = 'lose'
    
    return results


def main():
    """Run Champion/Challenger demonstration."""
    
    print("=" * 80)
    print("VÉLØ ORACLE - CHAMPION/CHALLENGER FRAMEWORK DEMO")
    print("=" * 80)
    print()
    
    # Initialize models
    print("Initializing models...")
    champion = BenterBaselineModel()
    challengers = [
        BenterPlusSQPEModel(),
        BenterPlusSQPETIEModel(),
        FullIntelligenceStackModel()
    ]
    
    # Create framework
    framework = ChampionChallengerFramework(
        champion=champion,
        challengers=challengers
    )
    
    print(f"✓ Champion: {champion.name}")
    print(f"✓ Challengers: {[c.name for c in challengers]}")
    print()
    
    # Simulate multiple races
    num_races = 20
    print(f"Simulating {num_races} races...")
    print()
    
    for race_num in range(1, num_races + 1):
        race_id = f"RACE_{race_num:03d}"
        
        # Create race data
        race_data = create_sample_race_data(race_id, num_horses=10)
        
        # Get predictions (only champion predictions are "live")
        champion_predictions = framework.predict(race_data, race_id)
        
        print(f"Race {race_num}/{num_races}: {race_id}")
        print(f"  Champion made {len([p for p in champion_predictions if p.recommended_bet])} bet recommendations")
        
        # Simulate race outcome
        results = simulate_race_results(race_data)
        
        # Record results
        framework.record_result(race_id, results)
    
    print()
    print("=" * 80)
    print("PERFORMANCE COMPARISON")
    print("=" * 80)
    print()
    
    # Generate comparison report
    comparison_df = framework.generate_comparison_report()
    print(comparison_df.to_string(index=False))
    print()
    
    # Check if any challenger should be promoted
    print("=" * 80)
    print("PROMOTION ANALYSIS")
    print("=" * 80)
    print()
    
    recommended_challenger = framework.should_promote_challenger(
        min_predictions=10,
        min_roi_improvement=0.05
    )
    
    if recommended_challenger:
        print(f"✓ RECOMMENDATION: Promote {recommended_challenger} to Champion")
        print()
        print("To execute promotion, run:")
        print(f"  framework.promote_challenger('{recommended_challenger}')")
    else:
        print("✓ Current champion is performing optimally")
        print("  No promotion recommended at this time")
    
    print()
    print("=" * 80)
    print("Demo complete. Results saved to:")
    print(f"  {framework.results_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()

