"""
VÉLØ Oracle - Data Contracts
Strict typing between chains and model ops
"""
from .race_contract import RaceContract
from .runner_contract import RunnerContract
from .market_contract import MarketContract, OddsMovement
from .narrative_contract import NarrativeContract, PredictionContract

__all__ = [
    "RaceContract",
    "RunnerContract",
    "MarketContract",
    "OddsMovement",
    "NarrativeContract",
    "PredictionContract"
]
