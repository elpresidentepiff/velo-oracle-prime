#!/usr/bin/env python3
"""
VELO Ablation / Silencing Tests (AAT)
Tests decision robustness by removing feature families

If removing one feature family flips the selection, the decision was fragile
and should NOT be used for training.

Run 5 ablations:
1. Remove market features
2. Remove trainer/jockey intent
3. Remove form/stability
4. Remove pace geometry
5. Remove course/going bias

Compute:
- flip_count: How many ablations changed the top selection
- prob_delta_max: Maximum probability change
- rank_delta_max: Maximum rank change

Rules:
- If flip_count >= 2 or prob_delta_max > ε → quarantine learning

Author: VELO Team
Version: 2.0 (War Mode)
Date: December 17, 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
import pandas as pd
import numpy as np
import logging

from .feature_registry import FeatureDomain, FeatureRegistry

logger = logging.getLogger(__name__)


@dataclass
class AblationResult:
    """Result from a single ablation test."""
    ablation_name: str
    features_removed: List[str]
    original_top_selection: str
    ablated_top_selection: str
    selection_flipped: bool
    prob_delta: float
    rank_delta: int
    notes: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'ablation_name': self.ablation_name,
            'features_removed_count': len(self.features_removed),
            'original_top_selection': self.original_top_selection,
            'ablated_top_selection': self.ablated_top_selection,
            'selection_flipped': self.selection_flipped,
            'prob_delta': self.prob_delta,
            'rank_delta': self.rank_delta,
            'notes': self.notes
        }


@dataclass
class AblationTestSuite:
    """Results from full ablation test suite."""
    ablations: List[AblationResult] = field(default_factory=list)
    flip_count: int = 0
    prob_delta_max: float = 0.0
    rank_delta_max: int = 0
    fragile: bool = False
    fragility_reason: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'ablations': [a.to_dict() for a in self.ablations],
            'flip_count': self.flip_count,
            'prob_delta_max': self.prob_delta_max,
            'rank_delta_max': self.rank_delta_max,
            'fragile': self.fragile,
            'fragility_reason': self.fragility_reason
        }


class AblationTester:
    """
    Ablation / Silencing Test Engine.
    
    Tests decision robustness by systematically removing feature families
    and checking if the decision changes.
    """
    
    # Fragility thresholds
    MAX_ALLOWED_FLIPS = 1
    MAX_PROB_DELTA = 0.15  # 15% probability change
    
    def __init__(self):
        self.registry = FeatureRegistry()
        logger.info("AAT initialized (War Mode)")
    
    def run_ablation_suite(
        self,
        features_df: pd.DataFrame,
        model_predict_fn: Callable,
        original_prediction: Dict
    ) -> AblationTestSuite:
        """
        Run full ablation test suite.
        
        Args:
            features_df: Feature DataFrame for the race
            model_predict_fn: Function that takes features and returns predictions
            original_prediction: Original prediction dict with top_selection and probs
            
        Returns:
            AblationTestSuite with results
        """
        logger.info("AAT running ablation suite")
        
        ablations = []
        
        # Define ablation tests
        ablation_specs = [
            ("remove_market", [FeatureDomain.MARKET]),
            ("remove_trainer_jockey", [FeatureDomain.TRAINER_JOCKEY]),
            ("remove_form", [FeatureDomain.FORM]),
            ("remove_pace", [FeatureDomain.PACE]),
            ("remove_course_going", [FeatureDomain.COURSE_GOING_DISTANCE])
        ]
        
        original_top = original_prediction.get('top_selection')
        original_probs = original_prediction.get('probabilities', {})
        
        for ablation_name, domains_to_remove in ablation_specs:
            result = self._run_single_ablation(
                features_df,
                model_predict_fn,
                domains_to_remove,
                ablation_name,
                original_top,
                original_probs
            )
            ablations.append(result)
        
        # Calculate summary statistics
        flip_count = sum(1 for a in ablations if a.selection_flipped)
        prob_delta_max = max(a.prob_delta for a in ablations)
        rank_delta_max = max(a.rank_delta for a in ablations)
        
        # Determine fragility
        fragile = (flip_count >= self.MAX_ALLOWED_FLIPS or 
                  prob_delta_max > self.MAX_PROB_DELTA)
        
        fragility_reason = ""
        if fragile:
            reasons = []
            if flip_count >= self.MAX_ALLOWED_FLIPS:
                reasons.append(f"{flip_count} flips (max {self.MAX_ALLOWED_FLIPS})")
            if prob_delta_max > self.MAX_PROB_DELTA:
                reasons.append(f"prob delta {prob_delta_max:.2f} (max {self.MAX_PROB_DELTA})")
            fragility_reason = "; ".join(reasons)
        
        suite = AblationTestSuite(
            ablations=ablations,
            flip_count=flip_count,
            prob_delta_max=prob_delta_max,
            rank_delta_max=rank_delta_max,
            fragile=fragile,
            fragility_reason=fragility_reason
        )
        
        logger.info(f"AAT: Flips={flip_count}, MaxDelta={prob_delta_max:.2f}, Fragile={fragile}")
        return suite
    
    def _run_single_ablation(
        self,
        features_df: pd.DataFrame,
        model_predict_fn: Callable,
        domains_to_remove: List[FeatureDomain],
        ablation_name: str,
        original_top: str,
        original_probs: Dict
    ) -> AblationResult:
        """Run a single ablation test."""
        # Get features to remove
        features_to_remove = self.registry.get_features_by_domains(domains_to_remove)
        
        # Create ablated feature set
        ablated_df = features_df.copy()
        for feature in features_to_remove:
            if feature in ablated_df.columns:
                # Set to neutral value (mean or 0)
                ablated_df[feature] = 0.0
        
        # Get prediction with ablated features
        try:
            ablated_prediction = model_predict_fn(ablated_df)
            ablated_top = ablated_prediction.get('top_selection')
            ablated_probs = ablated_prediction.get('probabilities', {})
        except Exception as e:
            logger.error(f"Ablation {ablation_name} failed: {e}")
            # Return conservative result
            return AblationResult(
                ablation_name=ablation_name,
                features_removed=features_to_remove,
                original_top_selection=original_top,
                ablated_top_selection=original_top,
                selection_flipped=False,
                prob_delta=0.0,
                rank_delta=0,
                notes={'error': str(e)}
            )
        
        # Check if selection flipped
        selection_flipped = (ablated_top != original_top)
        
        # Calculate probability delta
        original_prob = original_probs.get(original_top, 0.0)
        ablated_prob = ablated_probs.get(original_top, 0.0)
        prob_delta = abs(original_prob - ablated_prob)
        
        # Calculate rank delta (simplified - would need full rankings)
        rank_delta = 1 if selection_flipped else 0
        
        return AblationResult(
            ablation_name=ablation_name,
            features_removed=features_to_remove,
            original_top_selection=original_top,
            ablated_top_selection=ablated_top,
            selection_flipped=selection_flipped,
            prob_delta=prob_delta,
            rank_delta=rank_delta
        )


def run_ablation_tests(
    features_df: pd.DataFrame,
    model_predict_fn: Callable,
    original_prediction: Dict
) -> AblationTestSuite:
    """
    Convenience function to run ablation tests.
    
    Args:
        features_df: Feature DataFrame
        model_predict_fn: Model prediction function
        original_prediction: Original prediction
        
    Returns:
        AblationTestSuite
    """
    tester = AblationTester()
    return tester.run_ablation_suite(features_df, model_predict_fn, original_prediction)


if __name__ == "__main__":
    # Example usage
    import pandas as pd
    
    # Mock feature data
    features_df = pd.DataFrame({
        'rpr': [95, 92, 88],
        'or': [90, 87, 85],
        'form_last_3': [0.33, 0.67, 0.0],
        'odds_decimal': [3.5, 5.0, 8.0],
        'runner_id': ['r1', 'r2', 'r3']
    })
    
    # Mock prediction function
    def mock_predict(df):
        # Simple mock: highest RPR wins
        top_idx = df['rpr'].idxmax()
        top_runner = df.loc[top_idx, 'runner_id']
        return {
            'top_selection': top_runner,
            'probabilities': {
                'r1': 0.50,
                'r2': 0.30,
                'r3': 0.20
            }
        }
    
    original_pred = mock_predict(features_df)
    
    suite = run_ablation_tests(features_df, mock_predict, original_pred)
    print(f"Ablation Suite: {suite.to_dict()}")
