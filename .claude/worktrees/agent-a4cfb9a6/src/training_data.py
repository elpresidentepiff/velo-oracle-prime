"""
VÉLØ Training Data Management
Handles historical race results and training dataset creation.
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta


class TrainingDataManager:
    """
    Manages historical race results and creates training datasets for LightGBM.
    
    Training data schema:
    - Features: 61 engineered features per runner
    - Labels: Binary (won=1, lost=0) and top4 (top4=1, else=0)
    - Metadata: Race ID, runner name, actual finish position
    """
    
    def __init__(self, data_dir: str = "/home/ubuntu/velo-oracle-prime/training_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def create_training_example(
        self,
        features: np.ndarray,
        finish_position: int,
        race_id: str,
        runner_name: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create single training example.
        
        Args:
            features: np.ndarray of shape (61,) with engineered features
            finish_position: Actual finish position (1-based)
            race_id: Unique race identifier
            runner_name: Horse name
            metadata: Optional additional metadata
        
        Returns:
            Training example dict
        """
        return {
            'race_id': race_id,
            'runner_name': runner_name,
            'features': features.tolist(),
            'finish_position': finish_position,
            'won': int(finish_position == 1),
            'top4': int(finish_position <= 4),
            'metadata': metadata or {},
            'created_at': datetime.now().isoformat()
        }
    
    def save_training_examples(self, examples: List[Dict[str, Any]], filename: str):
        """Save training examples to JSON file."""
        filepath = self.data_dir / filename
        with open(filepath, 'w') as f:
            json.dump(examples, f, indent=2)
        print(f"✅ Saved {len(examples)} training examples to {filepath}")
    
    def load_training_examples(self, filename: str) -> List[Dict[str, Any]]:
        """Load training examples from JSON file."""
        filepath = self.data_dir / filename
        with open(filepath, 'r') as f:
            examples = json.load(f)
        print(f"✅ Loaded {len(examples)} training examples from {filepath}")
        return examples
    
    def examples_to_arrays(
        self,
        examples: List[Dict[str, Any]],
        target: str = 'won'
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert training examples to feature matrix and label vector.
        
        Args:
            examples: List of training example dicts
            target: Target variable ('won' or 'top4')
        
        Returns:
            X: Feature matrix of shape (n_examples, 61)
            y: Label vector of shape (n_examples,)
        """
        X = np.array([ex['features'] for ex in examples], dtype=np.float32)
        y = np.array([ex[target] for ex in examples], dtype=np.int32)
        return X, y
    
    def create_sample_dataset(self, n_races: int = 100, n_runners_per_race: int = 10) -> List[Dict[str, Any]]:
        """
        Create synthetic training dataset for testing.
        
        Args:
            n_races: Number of races to generate
            n_runners_per_race: Runners per race
        
        Returns:
            List of training examples
        """
        from feature_engineering import FeatureEngineer, create_sample_runner
        
        engineer = FeatureEngineer()
        examples = []
        
        print(f"Generating {n_races} races × {n_runners_per_race} runners = {n_races * n_runners_per_race} examples...")
        
        for race_idx in range(n_races):
            race_id = f"synthetic_race_{race_idx:04d}"
            race_context = {
                'going': np.random.choice(['GOOD', 'SOFT', 'HEAVY']),
                'distance': '2m',
                'runners': n_runners_per_race,
                'pace_pressure_index': np.random.uniform(0.3, 0.8),
                'draw_bias_score': np.random.uniform(-0.2, 0.2),
            }
            
            # Generate runners with varying quality
            race_examples = []
            for runner_idx in range(n_runners_per_race):
                # Create runner with random variations
                runner = create_sample_runner()
                
                # Add noise to features
                runner['rpr_last_3_avg'] += np.random.normal(0, 10)
                runner['ts_last_3_avg'] += np.random.normal(0, 8)
                runner['or_current'] += np.random.normal(0, 12)
                runner['career_win_rate'] = np.clip(np.random.beta(2, 5), 0, 1)
                runner['odds'] = np.random.uniform(2.0, 20.0)
                
                # Extract features
                features = engineer.extract_features(runner, race_context)
                
                # Simulate finish position (biased by form quality)
                form_score = (
                    runner['rpr_last_3_avg'] * 0.3 +
                    runner['ts_last_3_avg'] * 0.3 +
                    runner['or_current'] * 0.2 +
                    runner['career_win_rate'] * 50 +
                    (1 / runner['odds']) * 20
                )
                
                race_examples.append({
                    'runner_name': f"Horse_{runner_idx+1}",
                    'features': features,
                    'form_score': form_score,
                })
            
            # Sort by form score and assign finish positions
            race_examples.sort(key=lambda x: x['form_score'], reverse=True)
            
            # Add some randomness to finish positions
            for rank, ex in enumerate(race_examples):
                # Occasionally swap positions (simulate upsets)
                if np.random.random() < 0.15 and rank < len(race_examples) - 1:
                    finish_position = rank + 2  # Finish one place lower
                else:
                    finish_position = rank + 1
                
                finish_position = min(finish_position, n_runners_per_race)
                
                training_ex = self.create_training_example(
                    features=ex['features'],
                    finish_position=finish_position,
                    race_id=race_id,
                    runner_name=ex['runner_name'],
                    metadata={'going': race_context['going']}
                )
                examples.append(training_ex)
        
        print(f"✅ Generated {len(examples)} training examples")
        return examples
    
    def get_dataset_statistics(self, examples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate dataset statistics."""
        n_examples = len(examples)
        n_wins = sum(ex['won'] for ex in examples)
        n_top4 = sum(ex['top4'] for ex in examples)
        
        races = set(ex['race_id'] for ex in examples)
        n_races = len(races)
        
        return {
            'n_examples': n_examples,
            'n_races': n_races,
            'n_wins': n_wins,
            'n_top4': n_top4,
            'win_rate': n_wins / n_examples,
            'top4_rate': n_top4 / n_examples,
            'avg_runners_per_race': n_examples / n_races,
        }


def main():
    """Generate sample training dataset."""
    manager = TrainingDataManager()
    
    print("=" * 80)
    print("VÉLØ Training Data Generator")
    print("=" * 80)
    print()
    
    # Generate sample dataset
    examples = manager.create_sample_dataset(n_races=100, n_runners_per_race=10)
    
    # Save to file
    manager.save_training_examples(examples, 'synthetic_dataset_v1.json')
    
    # Calculate statistics
    stats = manager.get_dataset_statistics(examples)
    
    print()
    print("Dataset Statistics:")
    print(f"  Total examples: {stats['n_examples']}")
    print(f"  Total races: {stats['n_races']}")
    print(f"  Wins: {stats['n_wins']} ({stats['win_rate']:.1%})")
    print(f"  Top-4 finishes: {stats['n_top4']} ({stats['top4_rate']:.1%})")
    print(f"  Avg runners per race: {stats['avg_runners_per_race']:.1f}")
    print()
    
    # Convert to arrays
    X, y_win = manager.examples_to_arrays(examples, target='won')
    X, y_top4 = manager.examples_to_arrays(examples, target='top4')
    
    print("Feature Matrix:")
    print(f"  Shape: {X.shape}")
    print(f"  Win labels: {y_win.sum()} positives, {(~y_win.astype(bool)).sum()} negatives")
    print(f"  Top4 labels: {y_top4.sum()} positives, {(~y_top4.astype(bool)).sum()} negatives")
    print()
    print("✅ Training data pipeline working")


if __name__ == "__main__":
    main()
