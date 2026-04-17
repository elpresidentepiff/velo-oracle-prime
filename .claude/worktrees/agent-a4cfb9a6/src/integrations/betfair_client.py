"""
VÉLØ v10 - Betfair Client (Contract-Based)
Wrapper around legacy betfair_api.py that returns Pydantic contracts
"""

from typing import List, Optional, Dict
from datetime import datetime
import logging

from .betfair_api import BetfairAPIClient as LegacyBetfairClient
from ..modules.contracts import MarketSnapshot, Odds
from .http import HttpClient

logger = logging.getLogger("velo.betfair")


class BetfairClient:
    """
    Modern Betfair client that returns Pydantic contracts
    Uses robust HTTP layer with retry logic
    """
    
    def __init__(self, username: str = None, password: str = None, app_key: str = None):
        """
        Initialize Betfair client
        
        Args:
            username: Betfair username (from settings if not provided)
            password: Betfair password (from settings if not provided)
            app_key: Betfair app key (from settings if not provided)
        """
        from ..core.settings import settings
        
        self.username = username or settings.BETFAIR_USERNAME
        self.password = password or settings.BETFAIR_PASSWORD
        self.app_key = app_key or settings.BETFAIR_APP_KEY
        
        # Use legacy client for now (will refactor incrementally)
        self.legacy_client = LegacyBetfairClient(
            username=self.username,
            password=self.password,
            app_key=self.app_key
        )
        
        self.http = HttpClient()
        logger.info("BetfairClient initialized")
    
    def login(self) -> bool:
        """Authenticate with Betfair"""
        return self.legacy_client.login()
    
    def get_market_snapshot(
        self,
        market_id: str,
        date: str,
        course: str,
        time: str
    ) -> Optional[MarketSnapshot]:
        """
        Get current market odds as a snapshot
        
        Args:
            market_id: Betfair market ID
            date: Race date (YYYY-MM-DD)
            course: Course name
            time: Race time (HH:MM)
        
        Returns:
            MarketSnapshot with current odds, or None if unavailable
        """
        try:
            # Get market data from legacy client
            market_data = self.legacy_client.get_market_prices(market_id)
            
            if not market_data:
                return None
            
            # Convert to contracts
            book = {}
            for runner_data in market_data.get('runners', []):
                runner_name = runner_data.get('runnerName', '')
                
                odds = Odds(
                    bf_win=runner_data.get('lastPriceTraded'),
                    bf_back=runner_data.get('bestBackPrice'),
                    bf_lay=runner_data.get('bestLayPrice'),
                    bf_volume=runner_data.get('totalMatched'),
                    liquidity=runner_data.get('totalMatched')
                )
                
                book[runner_name] = odds
            
            snapshot = MarketSnapshot(
                date=date,
                course=course,
                time=time,
                snapshot_time=datetime.now(),
                market_id=market_id,
                book=book,
                total_matched=market_data.get('totalMatched'),
                market_status=market_data.get('status')
            )
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error getting market snapshot: {e}")
            return None
    
    def get_market_odds(self, market_id: str) -> Dict[str, Odds]:
        """
        Get current odds for all runners in a market
        
        Args:
            market_id: Betfair market ID
        
        Returns:
            Dict mapping runner name to Odds
        """
        try:
            market_data = self.legacy_client.get_market_prices(market_id)
            
            if not market_data:
                return {}
            
            odds_book = {}
            for runner_data in market_data.get('runners', []):
                runner_name = runner_data.get('runnerName', '')
                
                odds = Odds(
                    bf_win=runner_data.get('lastPriceTraded'),
                    bf_back=runner_data.get('bestBackPrice'),
                    bf_lay=runner_data.get('bestLayPrice'),
                    bf_volume=runner_data.get('totalMatched')
                )
                
                odds_book[runner_name] = odds
            
            return odds_book
            
        except Exception as e:
            logger.error(f"Error getting market odds: {e}")
            return {}
