"""
VÉLØ Intelligence Stack

Transforms the Oracle from calculator to strategist through
multi-signal convergence analysis.

Modules:
- SQPE: Sub-Quadratic Prediction Engine (signal convergence)
- TIE: Trainer Intention Engine (placement analysis)
- NDS: Narrative Disruption Scan (market misread detection)
- Orchestrator: Dual-signal logic coordinator

Author: VÉLØ Oracle Team
Version: 1.0
"""

from .sqpe import SQPE, SQPESignal, SignalStrength
from .tie import TIE, TIESignal, TrainerIntent
from .nds import NDS, NDSSignal, DisruptionStrength, NarrativeType
from .orchestrator import (
    IntelligenceOrchestrator,
    IntelligenceSignal,
    BetRecommendation
)

__all__ = [
    # SQPE
    'SQPE',
    'SQPESignal',
    'SignalStrength',
    
    # TIE
    'TIE',
    'TIESignal',
    'TrainerIntent',
    
    # NDS
    'NDS',
    'NDSSignal',
    'DisruptionStrength',
    'NarrativeType',
    
    # Orchestrator
    'IntelligenceOrchestrator',
    'IntelligenceSignal',
    'BetRecommendation',
]
