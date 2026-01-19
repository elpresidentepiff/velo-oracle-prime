"""
VÉLØ V13 - Critics Module

All critics are read-only, episode-bound, and emit proposals only (no auto-apply).

Cognitive Loop:
    Features → Bias → Leakage → Decision rationale

Author: VÉLØ Team
Date: 2026-01-19
Status: LOCKED
"""

from .cognitive_bias import (
    BiasFinding,
    BiasCritique,
    BiasPatchProposal,
    CognitiveBiasCritic,
)
from .decision_critic import (
    DecisionFinding,
    DecisionCritique,
    DecisionPatchProposal,
    DecisionCritic,
)
from .feature_extractor import (
    FeatureFinding,
    FeatureCritique,
    FeaturePatchProposal,
    FeatureExtractorCritic,
)
from .leakage_detector import (
    LeakageFinding,
    LeakageCritique,
    LeakagePatchProposal,
    LeakageDetectorCritic,
)

__all__ = [
    # Cognitive Bias Critic
    "BiasFinding",
    "BiasCritique",
    "BiasPatchProposal",
    "CognitiveBiasCritic",
    # Decision Critic
    "DecisionFinding",
    "DecisionCritique",
    "DecisionPatchProposal",
    "DecisionCritic",
    # Feature Extractor Critic
    "FeatureFinding",
    "FeatureCritique",
    "FeaturePatchProposal",
    "FeatureExtractorCritic",
    # Leakage Detector Critic
    "LeakageFinding",
    "LeakageCritique",
    "LeakagePatchProposal",
    "LeakageDetectorCritic",
]
