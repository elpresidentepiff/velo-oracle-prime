"""
VÉLØ Oracle 2.0 - External Integrations
========================================

This package contains integrations with external racing data APIs:
- Betfair API: Live odds streaming and market analysis
- The Racing API: Historical race data and statistics
"""

from .betfair_api import BetfairAPIClient, BetfairMarketAnalyzer
from .racing_api import RacingAPIClient, RacingDataAnalyzer

__all__ = [
    'BetfairAPIClient',
    'BetfairMarketAnalyzer',
    'RacingAPIClient',
    'RacingDataAnalyzer'
]

