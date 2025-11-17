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

from .sqpe import SQPEEngine, SQPE, SQPESignal, SignalStrength, SQPEConfig
from .tie import TrainerIntentEngine, TIE, TIEConfig
from .nds import NDS, NDSSignal, DisruptionStrength, NarrativeType
from .orchestrator import (
    IntelligenceOrchestrator,
    IntelligenceSignal,
    BetRecommendation
)

__all__ = [
    # SQPE
    'SQPEEngine',
    'SQPE',
    'SQPESignal',
    'SignalStrength',
    'SQPEConfig',
    
    # TIE
    'TrainerIntentEngine',
    'TIE',
    'TIEConfig',
    
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
