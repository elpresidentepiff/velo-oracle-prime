"""
TheRacingAPI Client for VELO v12
Handles authentication and race card retrieval
"""

import os
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

class RacingAPIClient:
    """Client for TheRacingAPI"""
    
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        self.username = username or os.getenv("RACING_API_USERNAME")
        self.password = password or os.getenv("RACING_API_PASSWORD")
        self.base_url = base_url or os.getenv("RACING_API_BASE_URL", "https://api.theracingapi.com/v1")
        
        if not self.username or not self.password:
            raise ValueError("RACING_API_USERNAME and RACING_API_PASSWORD are required")
        
        self.session = requests.Session()
        self.session.auth = (self.username, self.password)
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "VELO-v12/1.0"
        })
        
        logger.info(f"RacingAPIClient initialized with base_URL: {self.base_url}")
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated request to TheRacingAPI"""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            logger.error(f"Response: {e.response.text if e.response else 'No response'}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            raise
    
    def get_racecards(self, race_date: Optional[date] = None, region: str = "GB") -> List[Dict]:
        """
        Get race cards for a specific date
        
        Args:
            race_date: Date to get race cards for (defaults to today)
            region: Region code (GB, IRE, US, etc.)
        
        Returns:
            List of race card dictionaries
        """
        if race_date is None:
            race_date = date.today()
        
        date_str = race_date.strftime("%Y-%m-%d")
        
        logger.info(f"Fetching race cards for {date_str} ({region})")
        
        try:
            data = self._make_request("racecards", params={
                "date": date_str,
                "region": region
            })
            
            races = data.get("racecards", [])
            logger.info(f"Retrieved {len(races)} race cards")
            return races
            
        except Exception as e:
            logger.error(f"Failed to fetch race cards: {e}")
            return []
    
    def get_race_details(self, race_id: str) -> Optional[Dict]:
        """
        Get detailed information for a specific race
        
        Args:
            race_id: Unique race identifier
        
        Returns:
            Race details dictionary or None if not found
        """
        logger.info(f"Fetching race details for {race_id}")
        
        try:
            data = self._make_request(f"races/{race_id}")
            return data.get("race")
        except Exception as e:
            logger.error(f"Failed to fetch race details: {e}")
            return None
    
    def get_race_results(self, race_id: str) -> Optional[Dict]:
        """
        Get results for a completed race
        
        Args:
            race_id: Unique race identifier
        
        Returns:
            Race results dictionary or None if not available
        """
        logger.info(f"Fetching race results for {race_id}")
        
        try:
            data = self._make_request(f"results/{race_id}")
            return data.get("result")
        except Exception as e:
            logger.error(f"Failed to fetch race results: {e}")
            return None
    
    def health_check(self) -> bool:
        """Test API connection and authentication"""
        try:
            # Try to fetch today's race cards as a health check
            self.get_racecards()
            logger.info("✅ RacingAPI health check passed")
            return True
        except Exception as e:
            logger.error(f"❌ RacingAPI health check failed: {e}")
            return False


def get_racing_api_client() -> RacingAPIClient:
    """Factory function to create RacingAPIClient instance"""
    return RacingAPIClient()


if __name__ == "__main__":
    # Test the client
    logging.basicConfig(level=logging.INFO)
    
    client = RacingAPIClient(
        username="VkP2i6RRIDp2GGrxR6XAaViB",
        password="fqvqglMujliFV94D38uPvwUA"
    )
    
    print("Testing RacingAPI connection...")
    if client.health_check():
        print("✅ Connection successful")
        
        # Get today's race cards
        racecards = client.get_racecards()
        print(f"\n📋 Found {len(racecards)} races today")
        
        if racecards:
            first_race = racecards[0]
            print(f"\nFirst race: {first_race.get('course')} {first_race.get('off_time')}")
    else:
        print("❌ Connection failed")
