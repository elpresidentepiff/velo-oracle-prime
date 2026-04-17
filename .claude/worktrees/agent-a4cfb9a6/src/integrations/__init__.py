"""
VÉLØ v10 - Integrations Module
External API clients with Pydantic contracts
"""

# Modern contract-based clients (v10)
from .betfair_client import BetfairClient
from .racing_client import RacingClient
from .http import HttpClient, HttpError, get, post

# Legacy clients (for backward compatibility)
from .betfair_api import BetfairAPIClient as LegacyBetfairClient
from .racing_api import RacingAPIClient as LegacyRacingClient

__all__ = [
    # Modern clients
    'BetfairClient',
    'RacingClient',
    'HttpClient',
    'HttpError',
    'get',
    'post',
    # Legacy clients
    'LegacyBetfairClient',
    'LegacyRacingClient',
]
