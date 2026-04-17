"""
Betfair Client - Abstraction Layer
Supports SIM / DELAYED / LIVE modes for safe testing and deployment
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class BetfairMode(str, Enum):
    """Operating modes for Betfair integration"""
    SIM = "SIM"           # Simulated mode - no real API calls
    DELAYED = "DELAYED"   # Delayed data feed (free tier)
    LIVE = "LIVE"         # Live data feed (£300 activation)


class BetfairClient:
    """
    Unified Betfair API client with mode switching
    
    Modes:
    - SIM: Returns mocked data, logs "would place" orders
    - DELAYED: Uses delayed app key (10-60s delay)
    - LIVE: Uses live app key (real-time data)
    
    Usage:
        client = BetfairClient(
            app_key="your_key",
            username="your_username",
            password="your_password",
            mode=BetfairMode.SIM
        )
        client.login()
        markets = client.list_markets_for_day(date.today())
    """
    
    def __init__(
        self,
        app_key: str,
        username: str,
        password: str,
        mode: BetfairMode = BetfairMode.SIM,
        cert_path: Optional[str] = None,
        key_path: Optional[str] = None
    ):
        self.app_key = app_key
        self.username = username
        self.password = password
        self.mode = mode
        self.cert_path = cert_path
        self.key_path = key_path
        
        self.session_token: Optional[str] = None
        self.logged_in = False
        
        # SIM mode state
        self.sim_orders: List[Dict] = []
        self.sim_market_books: Dict[str, Dict] = {}
        
        logger.info(f"BetfairClient initialized in {mode} mode")
    
    def login(self) -> bool:
        """
        Authenticate with Betfair and obtain session token
        
        Returns:
            bool: True if login successful
        """
        if self.mode == BetfairMode.SIM:
            logger.info("[SIM] Simulated login successful")
            self.session_token = "SIM_TOKEN_12345"
            self.logged_in = True
            return True
        
        try:
            # Real Betfair login logic
            # Using betfairlightweight or direct API calls
            import betfairlightweight
            
            trading = betfairlightweight.APIClient(
                username=self.username,
                password=self.password,
                app_key=self.app_key,
                certs=self.cert_path if self.cert_path else None
            )
            
            trading.login()
            self.session_token = trading.session_token
            self.logged_in = True
            
            logger.info(f"[{self.mode}] Betfair login successful")
            return True
            
        except Exception as e:
            logger.error(f"[{self.mode}] Login failed: {e}")
            return False
    
    def list_markets_for_day(
        self,
        date: datetime,
        country_codes: List[str] = ["GB", "IE"],
        market_types: List[str] = ["WIN"]
    ) -> List[Dict]:
        """
        List all horse racing markets for a given day
        
        Args:
            date: Target date
            country_codes: List of country codes
            market_types: List of market types (WIN, PLACE, etc.)
        
        Returns:
            List of market dictionaries with:
                - market_id
                - event_id
                - market_name
                - market_start_time
                - runners (list of selection_id, runner_name)
        """
        if self.mode == BetfairMode.SIM:
            return self._sim_list_markets(date, country_codes)
        
        try:
            # Real Betfair API call
            import betfairlightweight
            
            # Market filter
            market_filter = betfairlightweight.filters.market_filter(
                event_type_ids=['7'],  # Horse Racing
                market_countries=country_codes,
                market_type_codes=market_types,
                market_start_time={
                    'from': date.isoformat(),
                    'to': (date + timedelta(days=1)).isoformat()
                }
            )
            
            # Get market catalogue
            markets = self.trading.betting.list_market_catalogue(
                filter=market_filter,
                max_results=200,
                market_projection=['RUNNER_METADATA', 'EVENT', 'MARKET_START_TIME']
            )
            
            result = []
            for market in markets:
                result.append({
                    'market_id': market.market_id,
                    'event_id': market.event.id,
                    'market_name': market.market_name,
                    'market_start_time': market.market_start_time,
                    'venue': market.event.venue,
                    'runners': [
                        {
                            'selection_id': runner.selection_id,
                            'runner_name': runner.runner_name,
                            'sort_priority': runner.sort_priority
                        }
                        for runner in market.runners
                    ]
                })
            
            logger.info(f"[{self.mode}] Found {len(result)} markets for {date}")
            return result
            
        except Exception as e:
            logger.error(f"[{self.mode}] Failed to list markets: {e}")
            return []
    
    def get_market_book(self, market_ids: List[str]) -> Dict[str, Dict]:
        """
        Get current market book (prices, volumes, status)
        
        Args:
            market_ids: List of market IDs
        
        Returns:
            Dict mapping market_id to market book:
                - status (OPEN, SUSPENDED, CLOSED)
                - inplay (bool)
                - total_matched (float)
                - runners: list of
                    - selection_id
                    - status
                    - last_price_traded
                    - ex (exchange prices)
                        - available_to_back: [{price, size}, ...]
                        - available_to_lay: [{price, size}, ...]
        """
        if self.mode == BetfairMode.SIM:
            return self._sim_get_market_book(market_ids)
        
        try:
            # Real Betfair API call
            import betfairlightweight
            
            market_books = self.trading.betting.list_market_book(
                market_ids=market_ids,
                price_projection=betfairlightweight.filters.price_projection(
                    price_data=['EX_BEST_OFFERS']
                )
            )
            
            result = {}
            for book in market_books:
                result[book.market_id] = {
                    'status': book.status,
                    'inplay': book.inplay,
                    'total_matched': book.total_matched,
                    'runners': [
                        {
                            'selection_id': runner.selection_id,
                            'status': runner.status,
                            'last_price_traded': runner.last_price_traded,
                            'ex': {
                                'available_to_back': [
                                    {'price': p.price, 'size': p.size}
                                    for p in (runner.ex.available_to_back or [])
                                ],
                                'available_to_lay': [
                                    {'price': p.price, 'size': p.size}
                                    for p in (runner.ex.available_to_lay or [])
                                ]
                            }
                        }
                        for runner in book.runners
                    ]
                }
            
            logger.info(f"[{self.mode}] Retrieved market book for {len(market_ids)} markets")
            return result
            
        except Exception as e:
            logger.error(f"[{self.mode}] Failed to get market book: {e}")
            return {}
    
    def place_order(
        self,
        market_id: str,
        selection_id: int,
        side: str,  # "BACK" or "LAY"
        size: float,
        price: float,
        persistence: str = "PERSIST"
    ) -> Dict:
        """
        Place a bet on Betfair
        
        Args:
            market_id: Market ID
            selection_id: Selection ID (horse)
            side: "BACK" or "LAY"
            size: Stake amount
            price: Odds (decimal)
            persistence: Order persistence type
        
        Returns:
            Order result dict with:
                - status: "SUCCESS" or "FAILURE"
                - bet_id: Unique bet identifier
                - placed_date: Timestamp
                - average_price_matched: Actual matched price
                - size_matched: Actual matched size
        """
        order = {
            'market_id': market_id,
            'selection_id': selection_id,
            'side': side,
            'size': size,
            'price': price,
            'persistence': persistence,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if self.mode == BetfairMode.SIM:
            return self._sim_place_order(order)
        
        if self.mode == BetfairMode.DELAYED:
            logger.warning("[DELAYED] Cannot place orders in DELAYED mode - use LIVE mode")
            return {
                'status': 'BLOCKED',
                'error': 'Orders not allowed in DELAYED mode'
            }
        
        try:
            # Real Betfair order placement
            import betfairlightweight
            
            instruction = betfairlightweight.filters.limit_order(
                size=size,
                price=price,
                persistence_type=persistence
            )
            
            place_instruction = betfairlightweight.filters.place_instruction(
                selection_id=selection_id,
                side=side,
                order_type="LIMIT",
                limit_order=instruction
            )
            
            result = self.trading.betting.place_orders(
                market_id=market_id,
                instructions=[place_instruction]
            )
            
            if result.status == "SUCCESS":
                bet_result = result.instruction_reports[0]
                logger.info(f"[LIVE] Order placed: {side} {selection_id} @ {price} for £{size}")
                return {
                    'status': 'SUCCESS',
                    'bet_id': bet_result.bet_id,
                    'placed_date': bet_result.placed_date,
                    'average_price_matched': bet_result.average_price_matched,
                    'size_matched': bet_result.size_matched
                }
            else:
                logger.error(f"[LIVE] Order failed: {result.error_code}")
                return {
                    'status': 'FAILURE',
                    'error': result.error_code
                }
                
        except Exception as e:
            logger.error(f"[LIVE] Failed to place order: {e}")
            return {
                'status': 'ERROR',
                'error': str(e)
            }
    
    def list_current_orders(
        self,
        market_ids: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        List all current orders (matched, unmatched, cancelled)
        
        Args:
            market_ids: Optional filter by market IDs
        
        Returns:
            List of order dicts
        """
        if self.mode == BetfairMode.SIM:
            return self.sim_orders
        
        try:
            # Real Betfair API call
            orders = self.trading.betting.list_current_orders(
                market_ids=market_ids
            )
            
            result = []
            for order in orders.current_orders:
                result.append({
                    'bet_id': order.bet_id,
                    'market_id': order.market_id,
                    'selection_id': order.selection_id,
                    'side': order.side,
                    'status': order.status,
                    'price': order.price_size.price,
                    'size': order.price_size.size,
                    'size_matched': order.size_matched,
                    'placed_date': order.placed_date
                })
            
            return result
            
        except Exception as e:
            logger.error(f"[{self.mode}] Failed to list orders: {e}")
            return []
    
    # ========== SIM MODE HELPERS ==========
    
    def _sim_list_markets(self, date: datetime, country_codes: List[str]) -> List[Dict]:
        """Generate simulated markets for testing"""
        logger.info(f"[SIM] Generating simulated markets for {date}")
        
        # Mock 5 races
        venues = ["Kempton", "Chelmsford", "Newcastle", "Wolverhampton", "Southwell"]
        markets = []
        
        for i, venue in enumerate(venues):
            market_time = date.replace(hour=14 + i, minute=30, second=0)
            market_id = f"1.{200000000 + i}"
            
            markets.append({
                'market_id': market_id,
                'event_id': f"30000{i}",
                'market_name': f"{venue} 14:30",
                'market_start_time': market_time.isoformat(),
                'venue': venue,
                'runners': [
                    {'selection_id': j * 1000 + i, 'runner_name': f"Horse {j}", 'sort_priority': j}
                    for j in range(1, 9)  # 8 runners
                ]
            })
        
        return markets
    
    def _sim_get_market_book(self, market_ids: List[str]) -> Dict[str, Dict]:
        """Generate simulated market book"""
        logger.info(f"[SIM] Generating simulated market book for {len(market_ids)} markets")
        
        result = {}
        for market_id in market_ids:
            # Generate random but realistic prices
            import random
            
            runners = []
            for i in range(1, 9):
                selection_id = i * 1000
                last_price = round(2.0 + (i - 1) * 1.5, 2)
                
                runners.append({
                    'selection_id': selection_id,
                    'status': 'ACTIVE',
                    'last_price_traded': last_price,
                    'ex': {
                        'available_to_back': [
                            {'price': last_price, 'size': round(random.uniform(100, 500), 2)}
                        ],
                        'available_to_lay': [
                            {'price': round(last_price + 0.1, 2), 'size': round(random.uniform(100, 500), 2)}
                        ]
                    }
                })
            
            result[market_id] = {
                'status': 'OPEN',
                'inplay': False,
                'total_matched': round(random.uniform(50000, 200000), 2),
                'runners': runners
            }
        
        return result
    
    def _sim_place_order(self, order: Dict) -> Dict:
        """Simulate order placement"""
        logger.info(
            f"[SIM] WOULD PLACE: {order['side']} selection {order['selection_id']} "
            f"@ {order['price']} for £{order['size']} in market {order['market_id']}"
        )
        
        # Generate fake bet ID
        bet_id = f"SIM_{len(self.sim_orders) + 1}"
        
        # Store order
        order['bet_id'] = bet_id
        order['status'] = 'MATCHED'
        order['size_matched'] = order['size']
        order['average_price_matched'] = order['price']
        
        self.sim_orders.append(order)
        
        return {
            'status': 'SUCCESS',
            'bet_id': bet_id,
            'placed_date': order['timestamp'],
            'average_price_matched': order['price'],
            'size_matched': order['size']
        }


def create_betfair_client(mode: Optional[BetfairMode] = None) -> BetfairClient:
    """
    Factory function to create BetfairClient from environment variables
    
    Environment variables:
        BETFAIR_MODE: SIM, DELAYED, or LIVE
        BETFAIR_APP_KEY_DELAYED: Delayed app key
        BETFAIR_APP_KEY_LIVE: Live app key
        BETFAIR_USERNAME: Username
        BETFAIR_PASSWORD: Password
    
    Returns:
        Configured BetfairClient instance
    """
    mode = mode or BetfairMode(os.getenv("BETFAIR_MODE", "SIM"))
    
    # Select appropriate app key
    if mode == BetfairMode.LIVE:
        app_key = os.getenv("BETFAIR_APP_KEY_LIVE", "")
    elif mode == BetfairMode.DELAYED:
        app_key = os.getenv("BETFAIR_APP_KEY_DELAYED", "")
    else:  # SIM
        app_key = "SIM_APP_KEY"
    
    username = os.getenv("BETFAIR_USERNAME", "sim_user")
    password = os.getenv("BETFAIR_PASSWORD", "sim_pass")
    
    client = BetfairClient(
        app_key=app_key,
        username=username,
        password=password,
        mode=mode
    )
    
    return client
