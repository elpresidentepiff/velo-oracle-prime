"""
VÉLØ Oracle - Experiment Tracking Demo

Demonstrates how to use the lightweight experiment tracking system
for logging parameters, metrics, and models.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

import numpy as np
import pandas as pd
from monitoring import experiment_tracker as mlflow


def simulate_training_run(model_name: str, kelly_fraction: float, min_edge: float) -> dict:
    """Simulate a training run with random results."""
    # Simulate metrics
    roi = np.random.uniform(0.8, 1.3)
    sharpe = np.random.uniform(0.5, 3.0)
    max_drawdown = np.random.uniform(0.05, 0.30)
    win_rate = np.random.uniform(0.25, 0.55)
    total_bets = np.random.randint(100, 500)
    
    return {
        'roi': roi,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'total_bets': total_bets
    }


def main():
    """Run experiment tracking demonstration."""
    
    print("=" * 80)
    print("VÉLØ ORACLE - EXPERIMENT TRACKING DEMO")
    print("=" * 80)
    print()
    
    # Set experiment
    experiment_name = "velo_v12_backtest"
    mlflow.set_experiment(experiment_name)
    print(f"✓ Experiment set: {experiment_name}")
    print()
    
    # Simulate multiple training runs with different configurations
    configurations = [
        {'model': 'Benter_Baseline', 'kelly_fraction': 0.1, 'min_edge': 0.05},
        {'model': 'Benter_Plus_SQPE', 'kelly_fraction': 0.1, 'min_edge': 0.05},
        {'model': 'Benter_Plus_SQPE_TIE', 'kelly_fraction': 0.15, 'min_edge': 0.03},
        {'model': 'Full_Intelligence_Stack', 'kelly_fraction': 0.1, 'min_edge': 0.05},
        {'model': 'Full_Intelligence_Stack', 'kelly_fraction': 0.2, 'min_edge': 0.03},
    ]
    
    print(f"Running {len(configurations)} experiments...")
    print()
    
    for i, config in enumerate(configurations, 1):
        print(f"Run {i}/{len(configurations)}: {config['model']}")
        
        # Start run
        with mlflow.run(mlflow._global_tracker, run_name=f"{config['model']}_run{i}"):
            # Log parameters
            mlflow.log_params({
                'model_name': config['model'],
                'kelly_fraction': config['kelly_fraction'],
                'min_edge': config['min_edge'],
                'backtest_years': '2023-2024',
                'bankroll': 1000
            })
            
            # Simulate training
            results = simulate_training_run(
                config['model'],
                config['kelly_fraction'],
                config['min_edge']
            )
            
            # Log metrics
            mlflow.log_metrics({
                'roi': results['roi'],
                'sharpe_ratio': results['sharpe_ratio'],
                'max_drawdown': results['max_drawdown'],
                'win_rate': results['win_rate'],
                'total_bets': results['total_bets']
            })
            
            # Log tags
            mlflow._global_tracker.set_tag('version', 'v12')
            mlflow._global_tracker.set_tag('status', 'completed')
            
            print(f"  ✓ ROI: {results['roi']:.3f}")
            print(f"  ✓ Sharpe: {results['sharpe_ratio']:.2f}")
            print(f"  ✓ Win Rate: {results['win_rate']:.2%}")
        
        print()
    
    # Search and compare runs
    print("=" * 80)
    print("EXPERIMENT RESULTS")
    print("=" * 80)
    print()
    
    runs_df = mlflow.search_runs(experiment_name)
    
    if not runs_df.empty:
        # Select key columns
        display_cols = [
            'run_name',
            'params.model_name',
            'params.kelly_fraction',
            'metrics.roi',
            'metrics.sharpe_ratio',
            'metrics.win_rate',
            'status'
        ]
        
        available_cols = [col for col in display_cols if col in runs_df.columns]
        display_df = runs_df[available_cols].copy()
        
        # Sort by ROI
        if 'metrics.roi' in display_df.columns:
            display_df = display_df.sort_values('metrics.roi', ascending=False)
        
        print(display_df.to_string(index=False))
        print()
        
        # Find best run
        if 'metrics.roi' in display_df.columns:
            best_run = display_df.iloc[0]
            print("=" * 80)
            print("BEST PERFORMING RUN")
            print("=" * 80)
            print()
            print(f"Model: {best_run.get('params.model_name', 'N/A')}")
            print(f"ROI: {best_run.get('metrics.roi', 0):.3f}")
            print(f"Sharpe Ratio: {best_run.get('metrics.sharpe_ratio', 0):.2f}")
            print(f"Win Rate: {best_run.get('metrics.win_rate', 0):.2%}")
            print()
    
    print("=" * 80)
    print(f"All results saved to: /home/ubuntu/velo-oracle/mlruns/{experiment_name}/")
    print("=" * 80)


if __name__ == "__main__":
    main()

