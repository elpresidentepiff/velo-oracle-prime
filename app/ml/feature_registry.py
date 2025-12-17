#!/usr/bin/env python3
"""
VELO Feature Registry
Groups features by domain for modular ablation studies

Enables experiments like:
- "Remove market features" and measure ROI impact
- "Use only form + pace" for minimal model
- "Ablate trainer/jockey" to test independence

Author: VELO Team
Version: 1.0
Date: December 17, 2025
"""

from typing import List, Dict, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FeatureDomain(Enum):
    """Feature domain categories."""
    CORE = "core"
    FORM = "form"
    PACE = "pace"
    DRAW = "draw"
    TRAINER_JOCKEY = "trainer_jockey"
    COURSE_GOING_DISTANCE = "course_going_distance"
    CLASS = "class"
    RECENCY = "recency"
    WEIGHT_AGE = "weight_age"
    MARKET = "market"


class FeatureRegistry:
    """
    Feature Registry: Groups features by domain.
    
    Enables modular ablation studies to understand feature importance.
    """
    
    # Feature domain mapping
    FEATURE_DOMAINS = {
        FeatureDomain.CORE: [
            'ran', 'num', 'age', 'rpr', 'or', 'ts', 'wgt_num', 'draw'
        ],
        FeatureDomain.FORM: [
            'form_last_3', 'form_last_5', 'form_last_10',
            'wins_last_3', 'wins_last_5', 'wins_last_10',
            'places_last_3', 'places_last_5', 'places_last_10',
            'consistency_score', 'improvement_trend'
        ],
        FeatureDomain.PACE: [
            'early_pace_rating', 'late_pace_rating', 'pace_style', 'sectional_avg'
        ],
        FeatureDomain.DRAW: [
            'draw_bias', 'draw_advantage', 'draw_percentile'
        ],
        FeatureDomain.TRAINER_JOCKEY: [
            'jockey_strike_rate', 'jockey_roi',
            'trainer_strike_rate', 'trainer_roi',
            'sire_roi', 'jockey_trainer_combo_roi'
        ],
        FeatureDomain.COURSE_GOING_DISTANCE: [
            'going_preference', 'going_win_rate', 'going_mismatch',
            'course_form', 'course_wins',
            'distance_form', 'distance_wins',
            'course_distance_form', 'track_type_form'
        ],
        FeatureDomain.CLASS: [
            'class_movement', 'class_drop_wins', 'class_stability'
        ],
        FeatureDomain.RECENCY: [
            'days_since_last_run', 'optimal_layoff', 'too_fresh', 'too_stale'
        ],
        FeatureDomain.WEIGHT_AGE: [
            'weight_carried', 'weight_vs_avg',
            'age_value', 'age_optimal',
            'is_gelding', 'is_mare'
        ],
        FeatureDomain.MARKET: [
            'odds_decimal', 'implied_prob', 'odds_rank', 'is_favorite', 'odds_drift'
        ]
    }
    
    def __init__(self):
        """Initialize feature registry."""
        self._validate_registry()
        logger.info(f"Feature Registry initialized with {len(self.FEATURE_DOMAINS)} domains")
    
    def _validate_registry(self):
        """Validate that all features are assigned to exactly one domain."""
        all_features = set()
        duplicates = set()
        
        for domain, features in self.FEATURE_DOMAINS.items():
            for feature in features:
                if feature in all_features:
                    duplicates.add(feature)
                all_features.add(feature)
        
        if duplicates:
            logger.warning(f"Duplicate features found: {duplicates}")
    
    def get_features_by_domain(self, domain: FeatureDomain) -> List[str]:
        """
        Get all features in a domain.
        
        Args:
            domain: FeatureDomain enum
            
        Returns:
            List of feature names
        """
        return self.FEATURE_DOMAINS.get(domain, [])
    
    def get_features_by_domains(self, domains: List[FeatureDomain]) -> List[str]:
        """
        Get all features across multiple domains.
        
        Args:
            domains: List of FeatureDomain enums
            
        Returns:
            List of feature names
        """
        features = []
        for domain in domains:
            features.extend(self.get_features_by_domain(domain))
        return features
    
    def get_domain_for_feature(self, feature_name: str) -> FeatureDomain:
        """
        Get domain for a specific feature.
        
        Args:
            feature_name: Feature name
            
        Returns:
            FeatureDomain enum or None if not found
        """
        for domain, features in self.FEATURE_DOMAINS.items():
            if feature_name in features:
                return domain
        return None
    
    def get_all_features(self) -> List[str]:
        """Get all features across all domains."""
        all_features = []
        for features in self.FEATURE_DOMAINS.values():
            all_features.extend(features)
        return all_features
    
    def get_feature_count_by_domain(self) -> Dict[str, int]:
        """Get feature count for each domain."""
        return {domain.value: len(features) for domain, features in self.FEATURE_DOMAINS.items()}
    
    def create_feature_subset(
        self,
        include_domains: List[FeatureDomain] = None,
        exclude_domains: List[FeatureDomain] = None
    ) -> List[str]:
        """
        Create a feature subset for ablation studies.
        
        Args:
            include_domains: Domains to include (if None, include all)
            exclude_domains: Domains to exclude
            
        Returns:
            List of feature names
        """
        if include_domains is None:
            include_domains = list(self.FEATURE_DOMAINS.keys())
        
        if exclude_domains is None:
            exclude_domains = []
        
        # Get features from included domains
        features = self.get_features_by_domains(include_domains)
        
        # Remove features from excluded domains
        if exclude_domains:
            excluded_features = set(self.get_features_by_domains(exclude_domains))
            features = [f for f in features if f not in excluded_features]
        
        return features
    
    def describe(self) -> str:
        """Generate human-readable description of registry."""
        lines = ["VELO Feature Registry", "=" * 80]
        
        total_features = len(self.get_all_features())
        lines.append(f"Total Features: {total_features}")
        lines.append("")
        
        for domain, features in self.FEATURE_DOMAINS.items():
            lines.append(f"{domain.value.upper()}: {len(features)} features")
            for feature in features:
                lines.append(f"  - {feature}")
            lines.append("")
        
        return "\n".join(lines)


# Predefined feature subsets for common experiments
class FeatureSubsets:
    """Predefined feature subsets for common ablation experiments."""
    
    @staticmethod
    def minimal() -> List[str]:
        """Minimal feature set: core only."""
        registry = FeatureRegistry()
        return registry.get_features_by_domain(FeatureDomain.CORE)
    
    @staticmethod
    def no_market() -> List[str]:
        """All features except market."""
        registry = FeatureRegistry()
        return registry.create_feature_subset(exclude_domains=[FeatureDomain.MARKET])
    
    @staticmethod
    def form_and_pace() -> List[str]:
        """Form and pace features only."""
        registry = FeatureRegistry()
        return registry.get_features_by_domains([
            FeatureDomain.CORE,
            FeatureDomain.FORM,
            FeatureDomain.PACE
        ])
    
    @staticmethod
    def no_trainer_jockey() -> List[str]:
        """All features except trainer/jockey."""
        registry = FeatureRegistry()
        return registry.create_feature_subset(exclude_domains=[FeatureDomain.TRAINER_JOCKEY])
    
    @staticmethod
    def ability_only() -> List[str]:
        """Ability-focused features (no market, no trainer/jockey)."""
        registry = FeatureRegistry()
        return registry.create_feature_subset(exclude_domains=[
            FeatureDomain.MARKET,
            FeatureDomain.TRAINER_JOCKEY
        ])


def get_feature_subset(subset_name: str) -> List[str]:
    """
    Get a predefined feature subset by name.
    
    Args:
        subset_name: Name of subset (minimal, no_market, form_and_pace, etc.)
        
    Returns:
        List of feature names
    """
    subsets = {
        'minimal': FeatureSubsets.minimal,
        'no_market': FeatureSubsets.no_market,
        'form_and_pace': FeatureSubsets.form_and_pace,
        'no_trainer_jockey': FeatureSubsets.no_trainer_jockey,
        'ability_only': FeatureSubsets.ability_only
    }
    
    if subset_name not in subsets:
        raise ValueError(f"Unknown subset: {subset_name}. Available: {list(subsets.keys())}")
    
    return subsets[subset_name]()


if __name__ == "__main__":
    # Example usage
    registry = FeatureRegistry()
    
    print(registry.describe())
    print("\n" + "="*80)
    print("PREDEFINED SUBSETS")
    print("="*80)
    
    for subset_name in ['minimal', 'no_market', 'form_and_pace', 'ability_only']:
        features = get_feature_subset(subset_name)
        print(f"\n{subset_name.upper()}: {len(features)} features")
        print(f"  {', '.join(features[:10])}...")
