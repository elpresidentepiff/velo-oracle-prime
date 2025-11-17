"""
VÉLØ Oracle - Multi-Agent System Demo

Demonstrates the collaborative workflow between specialized agents:
Analyst -> Risk -> Execution -> Learning
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import numpy as np
from agents.base_agent import AgentOrchestrator
from agents.specialized_agents import (
    AnalystAgent,
    RiskAgent,
    ExecutionAgent,
    LearningAgent
)


def create_sample_race_data(race_id: str, num_horses: int = 10) -> pd.DataFrame:
    """Create sample race data."""
    horses = []
    
    for i in range(num_horses):
        horse = {
            'race_id': race_id,
            'horse_name': f'Horse_{i+1}',
            'base_probability': np.random.uniform(0.05, 0.25),
            'speed_rating': np.random.uniform(70, 100),
            'class_rating': np.random.uniform(60, 95)
        }
        horses.append(horse)
    
    return pd.DataFrame(horses)


def create_odds_data(race_data: pd.DataFrame) -> dict:
    """Create sample odds data."""
    odds = {}
    for _, horse in race_data.iterrows():
        odds[horse['horse_name']] = np.random.uniform(2.0, 20.0)
    return odds


def simulate_race_results(race_data: pd.DataFrame) -> dict:
    """Simulate race results."""
    results = {}
    winner_idx = np.random.randint(0, len(race_data))
    
    for idx, horse in race_data.iterrows():
        horse_name = horse['horse_name']
        results[horse_name] = 'win' if idx == winner_idx else 'lose'
    
    return results


def main():
    """Run multi-agent system demonstration."""
    
    print("=" * 80)
    print("VÉLØ ORACLE - MULTI-AGENT SYSTEM DEMO")
    print("=" * 80)
    print()
    
    # Initialize orchestrator
    orchestrator = AgentOrchestrator()
    
    # Create and register agents
    analyst = AnalystAgent()
    risk = RiskAgent(initial_bankroll=1000.0)
    execution = ExecutionAgent()
    learning = LearningAgent()
    
    orchestrator.register_agent(analyst)
    orchestrator.register_agent(risk)
    orchestrator.register_agent(execution)
    orchestrator.register_agent(learning)
    
    print("✓ Multi-agent system initialized")
    print(f"  - {analyst}")
    print(f"  - {risk}")
    print(f"  - {execution}")
    print(f"  - {learning}")
    print()
    
    # Simulate multiple races
    num_races = 10
    print(f"Simulating {num_races} races with full agent workflow...")
    print()
    
    for race_num in range(1, num_races + 1):
        race_id = f"RACE_{race_num:03d}"
        print(f"{'='*60}")
        print(f"Race {race_num}/{num_races}: {race_id}")
        print(f"{'='*60}")
        
        # Create race data
        race_data = create_sample_race_data(race_id)
        odds_data = create_odds_data(race_data)
        
        # Step 1: Analyst analyzes the race
        print("Step 1: Analyst analyzing race...")
        analyst_output = analyst.process({
            'race_data': race_data,
            'race_id': race_id
        })
        print(f"  ✓ Generated {len(analyst_output['predictions'])} predictions")
        
        # Step 2: Risk evaluates and sizes bets
        print("Step 2: Risk calculating bet sizes...")
        risk_output = risk.process({
            'predictions': analyst_output['predictions'],
            'odds_data': odds_data,
            'race_id': race_id
        })
        print(f"  ✓ Approved {len(risk_output['bets'])} bets")
        print(f"  ✓ Current bankroll: £{risk.bankroll:.2f}")
        
        # Step 3: Execution places bets
        print("Step 3: Execution placing bets...")
        execution_output = execution.process({
            'bets': risk_output['bets'],
            'race_id': race_id
        })
        print(f"  ✓ Placed {len(execution_output['placed_bets'])} bets")
        
        # Simulate race results
        results = simulate_race_results(race_data)
        winner = [k for k, v in results.items() if v == 'win'][0]
        print(f"  🏇 Race complete - Winner: {winner}")
        
        # Calculate P&L
        total_pl = 0.0
        for bet in execution_output['placed_bets']:
            if results.get(bet['horse_name']) == 'win':
                profit = bet['stake'] * (bet['odds'] - 1)
                total_pl += profit
                print(f"  💰 WIN: {bet['horse_name']} - Profit: £{profit:.2f}")
            else:
                total_pl -= bet['stake']
        
        # Update bankroll
        risk.update_bankroll(total_pl)
        print(f"  📊 Race P&L: £{total_pl:.2f}")
        print(f"  💼 New bankroll: £{risk.bankroll:.2f}")
        
        # Step 4: Learning evaluates performance
        print("Step 4: Learning evaluating performance...")
        learning_output = learning.process({
            'predictions': analyst_output['predictions'],
            'placed_bets': execution_output['placed_bets'],
            'results': results
        })
        print(f"  ✓ Accuracy: {learning_output['evaluation']['accuracy']:.2%}")
        
        if learning_output['retrain_recommended']:
            print("  ⚠️  Retraining recommended")
        
        print()
    
    # Final summary
    print("=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print()
    
    print(f"Starting bankroll: £1000.00")
    print(f"Final bankroll: £{risk.bankroll:.2f}")
    print(f"Total P&L: £{risk.bankroll - 1000:.2f}")
    print(f"ROI: {((risk.bankroll / 1000) - 1) * 100:.2f}%")
    print()
    
    print(f"Total bets placed: {len(execution.bets_placed)}")
    print(f"Total evaluations: {len(learning.evaluation_history)}")
    print()
    
    # Agent states
    print("Agent States:")
    states = orchestrator.get_all_states()
    for name, state in states.items():
        print(f"  - {name}: {state.status}")
    
    print()
    print("=" * 80)
    print("Multi-agent demo complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()

