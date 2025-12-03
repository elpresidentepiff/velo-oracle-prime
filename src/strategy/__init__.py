"""
VÉLØ Oracle - Strategy Module
Core betting strategy, race selection, and bankroll management
"""
from .race_selection import RaceSelectionProtocol, RaceAttractiveness

__all__ = ["RaceSelectionProtocol", "RaceAttractiveness"]
