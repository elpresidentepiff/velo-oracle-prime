"""
VÉLØ Oracle 2.0 - Betfair API Integration
==========================================

This module provides live odds streaming, market movement detection,
and real money flow analysis from Betfair Exchange.

The Betfair API allows us to:
1. Stream live odds in real-time
2. Detect market manipulation through money flow
3. Identify when "smart money" moves vs "public money"
4. Track odds movements to spot value opportunities
5. Access matched bet volumes to gauge confidence

Author: VÉLØ Oracle Team
Version: 2.0.0
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests

logger = logging.getLogger(__name__)


class BetfairAPIClient:
    """
    Betfair API client for live odds streaming and market analysis.
    
    This client connects to Betfair's API-NG (Next Generation API) to:
    - Authenticate and maintain session tokens
    - Stream live odds data
    - Fetch market catalogs
    - Analyze market movements
    - Detect manipulation patterns
    """
    
    # Betfair API endpoints
    API_ENDPOINT = "https://api.betfair.com/exchange/betting/json-rpc/v1"
    IDENTITY_ENDPOINT = "https://identitysso.betfair.com/api"
    STREAM_ENDPOINT = "stream-api.betfair.com"
    
    def __init__(self, username: str = None, password: str = None, app_key: str = None):
        """
        Initialize Betfair API client.
        
        Args:
            username: Betfair account username (or from BETFAIR_USERNAME env var)
            password: Betfair account password (or from BETFAIR_PASSWORD env var)
            app_key: Betfair application key (or from BETFAIR_APP_KEY env var)
        """
        self.username = username or os.getenv('BETFAIR_USERNAME')
        self.password = password or os.getenv('BETFAIR_PASSWORD')
        self.app_key = app_key or os.getenv('BETFAIR_APP_KEY')
        
        self.session_token = None
        self.token_expiry = None
        
        # Cache for market data
        self.market_cache = {}
        self.odds_history = {}
        
        logger.info("BetfairAPIClient initialized")
    
    def login(self) -> bool:
        """
        Authenticate with Betfair and obtain session token.
        
        Returns:
            bool: True if login successful, False otherwise
        """
        if not all([self.username, self.password, self.app_key]):
            logger.error("Missing Betfair credentials. Set BETFAIR_USERNAME, BETFAIR_PASSWORD, BETFAIR_APP_KEY")
            return False
        
        try:
            headers = {
                'X-Application': self.app_key,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {
                'username': self.username,
                'password': self.password
            }
            
            response = requests.post(
                f"{self.IDENTITY_ENDPOINT}/login",
                headers=headers,
                data=data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'SUCCESS':
                    self.session_token = result.get('token')
                    # Tokens typically last 8 hours
                    self.token_expiry = datetime.now() + timedelta(hours=8)
                    logger.info("Successfully logged in to Betfair")
                    return True
                else:
                    logger.error(f"Login failed: {result.get('error')}")
                    return False
            else:
                logger.error(f"Login request failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Login exception: {e}")
            return False
    
    def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid session token."""
        if not self.session_token or datetime.now() >= self.token_expiry:
            return self.login()
        return True
    
    def _call_api(self, method: str, params: Dict) -> Optional[Dict]:
        """
        Make an API call to Betfair.
        
        Args:
            method: API method name (e.g., 'listMarketCatalogue')
            params: Method parameters
            
        Returns:
            API response dict or None on error
        """
        if not self._ensure_authenticated():
            logger.error("Not authenticated")
            return None
        
        try:
            headers = {
                'X-Application': self.app_key,
                'X-Authentication': self.session_token,
                'Content-Type': 'application/json'
            }
            
            payload = {
                "jsonrpc": "2.0",
                "method": f"SportsAPING/v1.0/{method}",
                "params": params,
                "id": 1
            }
            
            response = requests.post(
                self.API_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'result' in result:
                    return result['result']
                elif 'error' in result:
                    logger.error(f"API error: {result['error']}")
                    return None
            else:
                logger.error(f"API request failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"API call exception: {e}")
            return None
    
    def get_horse_racing_markets(self, hours_ahead: int = 24) -> List[Dict]:
        """
        Get upcoming horse racing markets.
        
        Args:
            hours_ahead: How many hours ahead to fetch markets
            
        Returns:
            List of market dictionaries
        """
        from_time = datetime.now().isoformat()
        to_time = (datetime.now() + timedelta(hours=hours_ahead)).isoformat()
        
        params = {
            "filter": {
                "eventTypeIds": ["7"],  # 7 = Horse Racing
                "marketCountries": ["GB", "IE"],  # UK and Ireland
                "marketTypeCodes": ["WIN"],  # Win markets
                "marketStartTime": {
                    "from": from_time,
                    "to": to_time
                }
            },
            "maxResults": 200,
            "marketProjection": [
                "COMPETITION",
                "EVENT",
                "EVENT_TYPE",
                "MARKET_START_TIME",
                "MARKET_DESCRIPTION",
                "RUNNER_DESCRIPTION"
            ]
        }
        
        result = self._call_api("listMarketCatalogue", params)
        return result if result else []
    
    def get_market_odds(self, market_id: str) -> Optional[Dict]:
        """
        Get current odds for a specific market.
        
        Args:
            market_id: Betfair market ID
            
        Returns:
            Market odds data including back/lay prices and volumes
        """
        params = {
            "marketIds": [market_id],
            "priceProjection": {
                "priceData": ["EX_BEST_OFFERS", "EX_TRADED"],
                "virtualise": False
            }
        }
        
        result = self._call_api("listMarketBook", params)
        
        if result and len(result) > 0:
            market_data = result[0]
            
            # Store in odds history for movement detection
            if market_id not in self.odds_history:
                self.odds_history[market_id] = []
            
            self.odds_history[market_id].append({
                'timestamp': datetime.now().isoformat(),
                'data': market_data
            })
            
            # Keep only last 100 snapshots per market
            if len(self.odds_history[market_id]) > 100:
                self.odds_history[market_id] = self.odds_history[market_id][-100:]
            
            return market_data
        
        return None
    
    def detect_market_movement(self, market_id: str, runner_id: int) -> Dict:
        """
        Detect market movement patterns for a specific runner.
        
        This is where we detect "the show" - manipulation patterns that
        indicate when favorites are being set up to lose.
        
        Args:
            market_id: Betfair market ID
            runner_id: Runner (horse) selection ID
            
        Returns:
            Dict containing movement analysis:
            - odds_drift: % change in odds
            - volume_surge: Unusual betting volume
            - smart_money: Indication of professional money
            - manipulation_score: 0-100 likelihood of manipulation
        """
        if market_id not in self.odds_history or len(self.odds_history[market_id]) < 2:
            return {
                'odds_drift': 0,
                'volume_surge': False,
                'smart_money': False,
                'manipulation_score': 0,
                'confidence': 'low',
                'message': 'Insufficient data'
            }
        
        history = self.odds_history[market_id]
        
        # Get first and last snapshots
        first_snapshot = history[0]['data']
        last_snapshot = history[-1]['data']
        
        # Find runner in both snapshots
        first_runner = None
        last_runner = None
        
        for runner in first_snapshot.get('runners', []):
            if runner.get('selectionId') == runner_id:
                first_runner = runner
                break
        
        for runner in last_snapshot.get('runners', []):
            if runner.get('selectionId') == runner_id:
                last_runner = runner
                break
        
        if not first_runner or not last_runner:
            return {
                'odds_drift': 0,
                'volume_surge': False,
                'smart_money': False,
                'manipulation_score': 0,
                'confidence': 'low',
                'message': 'Runner not found'
            }
        
        # Calculate odds drift
        first_odds = first_runner.get('ex', {}).get('availableToBack', [{}])[0].get('price', 0)
        last_odds = last_runner.get('ex', {}).get('availableToBack', [{}])[0].get('price', 0)
        
        if first_odds > 0:
            odds_drift = ((last_odds - first_odds) / first_odds) * 100
        else:
            odds_drift = 0
        
        # Calculate volume changes
        first_volume = sum([item.get('size', 0) for item in first_runner.get('ex', {}).get('tradedVolume', [])])
        last_volume = sum([item.get('size', 0) for item in last_runner.get('ex', {}).get('tradedVolume', [])])
        
        volume_increase = last_volume - first_volume
        volume_surge = volume_increase > 10000  # £10k+ is significant
        
        # Detect smart money patterns
        # Smart money typically:
        # 1. Comes in late (last 15 mins before race)
        # 2. Moves odds significantly with large single bets
        # 3. Goes against public sentiment
        
        smart_money = False
        if abs(odds_drift) > 10 and volume_surge:
            smart_money = True
        
        # Calculate manipulation score
        manipulation_score = 0
        
        # Favorite drifting significantly = potential manipulation
        if first_odds < 5.0 and odds_drift > 20:
            manipulation_score += 40
        
        # Large volume with odds movement = coordinated action
        if volume_surge and abs(odds_drift) > 15:
            manipulation_score += 30
        
        # Smart money against public = classic manipulation
        if smart_money:
            manipulation_score += 30
        
        manipulation_score = min(manipulation_score, 100)
        
        # Determine confidence
        if len(history) < 5:
            confidence = 'low'
        elif len(history) < 20:
            confidence = 'medium'
        else:
            confidence = 'high'
        
        return {
            'odds_drift': round(odds_drift, 2),
            'volume_surge': volume_surge,
            'smart_money': smart_money,
            'manipulation_score': manipulation_score,
            'confidence': confidence,
            'first_odds': first_odds,
            'last_odds': last_odds,
            'volume_increase': volume_increase,
            'message': self._interpret_movement(odds_drift, manipulation_score)
        }
    
    def _interpret_movement(self, drift: float, manipulation_score: int) -> str:
        """Interpret market movement in VÉLØ's voice."""
        if manipulation_score > 70:
            return "⚠️ HIGH MANIPULATION RISK - The house is setting a trap"
        elif manipulation_score > 40:
            return "⚡ Suspicious movement - Smart money disagrees with public"
        elif abs(drift) > 20:
            return "📊 Significant drift - Market reassessing this runner"
        elif abs(drift) < 5:
            return "✓ Stable odds - Market confidence holding"
        else:
            return "→ Normal movement - No red flags"
    
    def get_runner_odds_history(self, market_id: str, runner_id: int) -> List[Dict]:
        """
        Get historical odds for a specific runner.
        
        Args:
            market_id: Betfair market ID
            runner_id: Runner selection ID
            
        Returns:
            List of odds snapshots over time
        """
        if market_id not in self.odds_history:
            return []
        
        runner_history = []
        
        for snapshot in self.odds_history[market_id]:
            for runner in snapshot['data'].get('runners', []):
                if runner.get('selectionId') == runner_id:
                    back_prices = runner.get('ex', {}).get('availableToBack', [])
                    lay_prices = runner.get('ex', {}).get('availableToLay', [])
                    
                    runner_history.append({
                        'timestamp': snapshot['timestamp'],
                        'back_price': back_prices[0].get('price') if back_prices else None,
                        'back_size': back_prices[0].get('size') if back_prices else None,
                        'lay_price': lay_prices[0].get('price') if lay_prices else None,
                        'lay_size': lay_prices[0].get('size') if lay_prices else None,
                        'total_matched': runner.get('totalMatched', 0)
                    })
                    break
        
        return runner_history
    
    def logout(self):
        """Logout and invalidate session token."""
        if self.session_token:
            try:
                headers = {
                    'X-Application': self.app_key,
                    'X-Authentication': self.session_token
                }
                
                requests.post(
                    f"{self.IDENTITY_ENDPOINT}/logout",
                    headers=headers,
                    timeout=10
                )
                
                logger.info("Logged out from Betfair")
            except Exception as e:
                logger.error(f"Logout exception: {e}")
            
            self.session_token = None
            self.token_expiry = None


class BetfairMarketAnalyzer:
    """
    Analyzes Betfair market data to detect value and manipulation.
    
    This is the "eyes" of VÉLØ - watching the money flow to spot
    when the house is running "the show".
    """
    
    def __init__(self, client: BetfairAPIClient):
        self.client = client
        logger.info("BetfairMarketAnalyzer initialized")
    
    def analyze_race_market(self, market_id: str) -> Dict:
        """
        Comprehensive analysis of a race market.
        
        Returns:
            Dict containing:
            - market_efficiency: How efficient the market is
            - favorite_trap_risk: Likelihood favorite is a trap
            - value_runners: Horses offering value
            - manipulation_detected: Overall manipulation assessment
        """
        market_odds = self.client.get_market_odds(market_id)
        
        if not market_odds:
            return {
                'error': 'Could not fetch market data',
                'market_efficiency': 0,
                'favorite_trap_risk': 0,
                'value_runners': [],
                'manipulation_detected': False
            }
        
        runners = market_odds.get('runners', [])
        
        # Analyze each runner
        runner_analysis = []
        for runner in runners:
            runner_id = runner.get('selectionId')
            movement = self.client.detect_market_movement(market_id, runner_id)
            
            back_prices = runner.get('ex', {}).get('availableToBack', [])
            current_odds = back_prices[0].get('price') if back_prices else None
            
            runner_analysis.append({
                'selection_id': runner_id,
                'current_odds': current_odds,
                'movement': movement,
                'total_matched': runner.get('totalMatched', 0)
            })
        
        # Sort by odds to find favorite
        runner_analysis.sort(key=lambda x: x['current_odds'] if x['current_odds'] else 999)
        
        favorite = runner_analysis[0] if runner_analysis else None
        
        # Calculate favorite trap risk
        favorite_trap_risk = 0
        if favorite:
            favorite_trap_risk = favorite['movement']['manipulation_score']
        
        # Find value runners (drifting out when they shouldn't)
        value_runners = []
        for runner in runner_analysis:
            movement = runner['movement']
            # Value = drifting out but low manipulation score
            if movement['odds_drift'] > 10 and movement['manipulation_score'] < 30:
                value_runners.append({
                    'selection_id': runner['selection_id'],
                    'odds': runner['current_odds'],
                    'drift': movement['odds_drift'],
                    'reason': 'Public overreaction - value emerging'
                })
        
        # Overall manipulation assessment
        avg_manipulation = sum([r['movement']['manipulation_score'] for r in runner_analysis]) / len(runner_analysis) if runner_analysis else 0
        manipulation_detected = avg_manipulation > 40
        
        # Market efficiency (lower = more efficient)
        total_matched = sum([r['total_matched'] for r in runner_analysis])
        market_efficiency = min(100, total_matched / 1000)  # £100k+ = 100% efficient
        
        return {
            'market_efficiency': round(market_efficiency, 2),
            'favorite_trap_risk': favorite_trap_risk,
            'value_runners': value_runners,
            'manipulation_detected': manipulation_detected,
            'average_manipulation_score': round(avg_manipulation, 2),
            'total_matched': total_matched,
            'runner_count': len(runner_analysis),
            'favorite_odds': favorite['current_odds'] if favorite else None
        }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize client
    client = BetfairAPIClient()
    
    # Login
    if client.login():
        print("✓ Connected to Betfair")
        
        # Get upcoming races
        markets = client.get_horse_racing_markets(hours_ahead=4)
        print(f"✓ Found {len(markets)} upcoming races")
        
        if markets:
            # Analyze first market
            market_id = markets[0]['marketId']
            print(f"\n📊 Analyzing market: {markets[0]['event']['name']}")
            
            analyzer = BetfairMarketAnalyzer(client)
            analysis = analyzer.analyze_race_market(market_id)
            
            print(f"Market Efficiency: {analysis['market_efficiency']}%")
            print(f"Favorite Trap Risk: {analysis['favorite_trap_risk']}/100")
            print(f"Manipulation Detected: {analysis['manipulation_detected']}")
            print(f"Value Runners: {len(analysis['value_runners'])}")
        
        # Logout
        client.logout()
    else:
        print("✗ Failed to connect to Betfair")

