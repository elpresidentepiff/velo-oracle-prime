"""
VÉLØ Genesis Protocol - Continuous Learning System

Enables VÉLØ to:
- Learn from every race outcome
- Adjust analytical weights based on performance
- Discover new patterns
- Self-critique and improve
- Evolve from baby to adult Oracle
"""

import json
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path


class GenesisProtocol:
    """
    Continuous learning system for VÉLØ Oracle.
    
    Features:
    - Outcome-based learning
    - Weight adjustment
    - Pattern discovery
    - Self-critique
    - Performance tracking
    """
    
    def __init__(self, memory_system=None, config_path: str = None):
        """
        Initialize Genesis Protocol.
        
        Args:
            memory_system: VeloMemory instance
            config_path: Path to weights configuration
        """
        self.memory = memory_system
        
        if config_path is None:
            config_path = Path.home() / ".velo_memory" / "config" / "learning_weights.json"
        
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize or load weights
        self.weights = self._load_weights()
        
        # Learning parameters
        self.learning_rate = 0.05  # 5% adjustment per iteration
        self.min_sample_size = 5  # Minimum races before adjusting
        
        # Performance tracking
        self.iterations = 0
        self.adjustments_made = []
        
        print("✓ Genesis Protocol initialized")
        print(f"  Learning rate: {self.learning_rate * 100}%")
        print(f"  Minimum sample size: {self.min_sample_size}")
    
    def _load_weights(self) -> Dict:
        """Load or initialize analytical weights."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    weights = json.load(f)
                    print(f"✓ Loaded existing weights from {self.config_path}")
                    return weights
            except Exception as e:
                print(f"⚠ Could not load weights: {e}")
        
        # Default weights
        default_weights = {
            'form_weight': 0.25,
            'class_weight': 0.15,
            'jockey_weight': 0.15,
            'trainer_weight': 0.15,
            'pace_weight': 0.10,
            'draw_weight': 0.10,
            'market_weight': 0.10,
            
            # Filter thresholds
            'min_consistency': 0.50,
            'min_jockey_roi': 0.10,
            'min_trainer_roi': 0.10,
            
            # Confidence parameters
            'confidence_multiplier': 1.0,
            'risk_tolerance': 0.70,
            
            # Metadata
            'last_updated': datetime.now().isoformat(),
            'total_adjustments': 0,
            'performance_history': []
        }
        
        self._save_weights(default_weights)
        print("✓ Initialized default weights")
        return default_weights
    
    def _save_weights(self, weights: Dict):
        """Save weights to disk."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(weights, f, indent=2)
        except Exception as e:
            print(f"✗ Error saving weights: {e}")
    
    def learn_from_outcome(
        self,
        prediction: Dict,
        actual_result: Dict,
        race_data: Dict
    ) -> Dict:
        """
        Learn from a race outcome and adjust weights.
        
        Args:
            prediction: Oracle's prediction
            actual_result: Actual race result
            race_data: Original race data
        
        Returns:
            Learning report
        """
        self.iterations += 1
        
        report = {
            'iteration': self.iterations,
            'timestamp': datetime.now().isoformat(),
            'outcome': 'unknown',
            'adjustments': [],
            'insights': []
        }
        
        # Determine outcome
        shortlist = prediction.get('shortlist', [])
        winner = actual_result.get('winner')
        placed = actual_result.get('placed', [])
        
        hit = any(h['name'] == winner for h in shortlist)
        partial_hit = any(h['name'] in placed for h in shortlist)
        
        if hit:
            report['outcome'] = 'WIN'
            report['insights'].append("✓ Prediction successful - winner in shortlist")
            # Reinforce current weights slightly
            self._reinforce_weights(0.02)  # Small positive adjustment
        
        elif partial_hit:
            report['outcome'] = 'PLACE'
            report['insights'].append("⚠ Partial success - placed horse in shortlist")
            # No adjustment for partial success
        
        else:
            report['outcome'] = 'MISS'
            report['insights'].append("✗ Prediction failed - analyze why")
            # Analyze failure and adjust
            adjustments = self._analyze_failure(prediction, actual_result, race_data)
            report['adjustments'] = adjustments
        
        # Save learning report to memory
        if self.memory:
            self.memory.store_outcome(
                prediction_id=prediction.get('prediction_id', 'unknown'),
                outcome_data={
                    **actual_result,
                    'hit': hit,
                    'learning_report': report
                }
            )
        
        # Record adjustment
        self.adjustments_made.append(report)
        
        # Update weights metadata
        self.weights['last_updated'] = datetime.now().isoformat()
        self.weights['total_adjustments'] = len(self.adjustments_made)
        self.weights['performance_history'].append({
            'iteration': self.iterations,
            'outcome': report['outcome'],
            'timestamp': report['timestamp']
        })
        
        self._save_weights(self.weights)
        
        return report
    
    def _reinforce_weights(self, adjustment: float):
        """Reinforce current weights (small positive adjustment)."""
        # Slightly increase confidence multiplier
        self.weights['confidence_multiplier'] = min(
            self.weights['confidence_multiplier'] + adjustment,
            1.5  # Max 1.5x
        )
        
        print(f"✓ Weights reinforced (+{adjustment * 100:.1f}%)")
    
    def _analyze_failure(
        self,
        prediction: Dict,
        actual_result: Dict,
        race_data: Dict
    ) -> List[Dict]:
        """
        Analyze why prediction failed and suggest adjustments.
        
        Returns:
            List of adjustment recommendations
        """
        adjustments = []
        
        winner = actual_result.get('winner')
        winner_data = None
        
        # Find winner in race data
        for horse in race_data.get('horses', []):
            if horse.get('name') == winner:
                winner_data = horse
                break
        
        if not winner_data:
            return adjustments
        
        # Analyze what we missed
        
        # 1. Check if winner had better form than we weighted
        winner_form = winner_data.get('form', '')
        if winner_form and winner_form[0] == '1':  # Won last time
            adjustments.append({
                'parameter': 'form_weight',
                'reason': 'Winner had recent win we underweighted',
                'adjustment': +0.05,
                'new_value': min(self.weights['form_weight'] + 0.05, 0.40)
            })
            self.weights['form_weight'] = min(self.weights['form_weight'] + 0.05, 0.40)
        
        # 2. Check if winner had strong jockey
        winner_jockey_roi = winner_data.get('jockey_roi', 0.0)
        if winner_jockey_roi > 0.15:  # Strong jockey
            adjustments.append({
                'parameter': 'jockey_weight',
                'reason': f'Winner had strong jockey (ROI: {winner_jockey_roi * 100:.1f}%)',
                'adjustment': +0.03,
                'new_value': min(self.weights['jockey_weight'] + 0.03, 0.25)
            })
            self.weights['jockey_weight'] = min(self.weights['jockey_weight'] + 0.03, 0.25)
        
        # 3. Check if winner had strong trainer
        winner_trainer_roi = winner_data.get('trainer_roi', 0.0)
        if winner_trainer_roi > 0.15:  # Strong trainer
            adjustments.append({
                'parameter': 'trainer_weight',
                'reason': f'Winner had strong trainer (ROI: {winner_trainer_roi * 100:.1f}%)',
                'adjustment': +0.03,
                'new_value': min(self.weights['trainer_weight'] + 0.03, 0.25)
            })
            self.weights['trainer_weight'] = min(self.weights['trainer_weight'] + 0.03, 0.25)
        
        # 4. Reduce confidence multiplier slightly
        if self.weights['confidence_multiplier'] > 0.8:
            adjustments.append({
                'parameter': 'confidence_multiplier',
                'reason': 'Overconfident - reduce multiplier',
                'adjustment': -0.05,
                'new_value': max(self.weights['confidence_multiplier'] - 0.05, 0.5)
            })
            self.weights['confidence_multiplier'] = max(self.weights['confidence_multiplier'] - 0.05, 0.5)
        
        if adjustments:
            print(f"⚙ Made {len(adjustments)} weight adjustments based on failure analysis")
        
        return adjustments
    
    def discover_pattern(
        self,
        pattern_type: str,
        pattern_data: Dict,
        confidence: float
    ) -> str:
        """
        Discover and store a new pattern.
        
        Args:
            pattern_type: Type of pattern (trainer, jockey, course, etc.)
            pattern_data: Pattern details
            confidence: Confidence in pattern (0.0 to 1.0)
        
        Returns:
            pattern_id
        """
        if not self.memory:
            print("⚠ No memory system - cannot store pattern")
            return None
        
        pattern_data['confidence'] = confidence
        pattern_id = self.memory.store_pattern(pattern_type, pattern_data)
        
        print(f"✓ Pattern discovered: {pattern_type} - {pattern_data.get('name')} (confidence: {confidence * 100:.0f}%)")
        
        return pattern_id
    
    def self_critique(self) -> Dict:
        """
        Perform self-critique of recent performance.
        
        Returns:
            Critique report
        """
        if not self.memory:
            return {'error': 'No memory system available'}
        
        # Get performance stats
        stats = self.memory.get_performance_stats()
        
        critique = {
            'timestamp': datetime.now().isoformat(),
            'total_predictions': stats.get('total_predictions', 0),
            'accuracy': stats.get('accuracy', 0.0),
            'learning_rate': stats.get('learning_rate', 0.0),
            'assessment': '',
            'recommendations': []
        }
        
        accuracy = stats.get('accuracy', 0.0)
        learning_rate = stats.get('learning_rate', 0.0)
        
        # Assess performance
        if accuracy >= 0.70:
            critique['assessment'] = "EXCELLENT - Consistently accurate predictions"
        elif accuracy >= 0.50:
            critique['assessment'] = "GOOD - Solid performance, room for improvement"
        elif accuracy >= 0.30:
            critique['assessment'] = "FAIR - Needs improvement, learning in progress"
        else:
            critique['assessment'] = "POOR - Significant adjustments needed"
        
        # Check if learning
        if learning_rate > 0.05:
            critique['recommendations'].append("✓ Learning rate positive - keep current strategy")
        elif learning_rate < -0.05:
            critique['recommendations'].append("⚠ Learning rate negative - review recent changes")
        else:
            critique['recommendations'].append("⚠ Learning rate flat - need more data or strategy change")
        
        # Specific recommendations based on accuracy
        if accuracy < 0.50:
            critique['recommendations'].append("⚙ Consider increasing minimum sample size")
            critique['recommendations'].append("⚙ Review filter thresholds")
            critique['recommendations'].append("⚙ Analyze common failure patterns")
        
        print("\n=== SELF-CRITIQUE ===")
        print(f"Assessment: {critique['assessment']}")
        print(f"Accuracy: {accuracy * 100:.1f}%")
        print(f"Learning Rate: {learning_rate:+.2f}")
        print("\nRecommendations:")
        for rec in critique['recommendations']:
            print(f"  {rec}")
        
        return critique
    
    def get_current_weights(self) -> Dict:
        """Get current analytical weights."""
        return self.weights.copy()
    
    def reset_weights(self):
        """Reset weights to defaults."""
        if self.config_path.exists():
            self.config_path.unlink()
        
        self.weights = self._load_weights()
        self.iterations = 0
        self.adjustments_made = []
        
        print("✓ Weights reset to defaults")


if __name__ == "__main__":
    # Test Genesis Protocol
    print("=== VÉLØ Genesis Protocol Test ===\n")
    
    protocol = GenesisProtocol()
    
    # Simulate learning from outcomes
    test_prediction = {
        'prediction_id': 'test_001',
        'shortlist': [
            {'name': 'Horse A', 'odds': 5.0, 'confidence': 0.8},
            {'name': 'Horse B', 'odds': 8.0, 'confidence': 0.7}
        ]
    }
    
    # Test 1: Successful prediction
    print("\n--- Test 1: Successful Prediction ---")
    result_win = {
        'winner': 'Horse A',
        'placed': ['Horse A', 'Horse C', 'Horse D']
    }
    
    race_data = {
        'horses': [
            {'name': 'Horse A', 'form': '1231', 'jockey_roi': 0.15, 'trainer_roi': 0.12},
            {'name': 'Horse B', 'form': '2341', 'jockey_roi': 0.10, 'trainer_roi': 0.08}
        ]
    }
    
    report1 = protocol.learn_from_outcome(test_prediction, result_win, race_data)
    print(f"Outcome: {report1['outcome']}")
    print(f"Insights: {report1['insights']}")
    
    # Test 2: Failed prediction
    print("\n--- Test 2: Failed Prediction ---")
    result_loss = {
        'winner': 'Horse C',
        'placed': ['Horse C', 'Horse D', 'Horse E']
    }
    
    race_data_loss = {
        'horses': [
            {'name': 'Horse A', 'form': '3241', 'jockey_roi': 0.08, 'trainer_roi': 0.05},
            {'name': 'Horse C', 'form': '1112', 'jockey_roi': 0.20, 'trainer_roi': 0.18}
        ]
    }
    
    report2 = protocol.learn_from_outcome(test_prediction, result_loss, race_data_loss)
    print(f"Outcome: {report2['outcome']}")
    print(f"Adjustments made: {len(report2['adjustments'])}")
    for adj in report2['adjustments']:
        print(f"  {adj['parameter']}: {adj['adjustment']:+.2f} ({adj['reason']})")
    
    # Self-critique
    print("\n--- Self-Critique ---")
    protocol.self_critique()
    
    # Show current weights
    print("\n--- Current Weights ---")
    weights = protocol.get_current_weights()
    for key, value in weights.items():
        if isinstance(value, float) and key.endswith('_weight'):
            print(f"{key}: {value:.2f}")
    
    print("\n✓ Genesis Protocol operational")

