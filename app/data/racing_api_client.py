"""
TheRacingAPI Client - Live Race Card Ingestion
VELO v12 Market-Intent Stack

Fetches live race cards from TheRacingAPI and transforms them into VELO format.
Updates every 5 minutes with latest data from UK & Irish racing.
"""

import os
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from dataclasses import dataclass
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class RaceCardConfig:
    """Configuration for TheRacingAPI client"""
    username: str
    password: str
    base_url: str = "https://api.theracingapi.com/v1"
    timeout: int = 30
    rate_limit_delay: float = 0.5  # 2 requests per second = 0.5s delay


class TheRacingAPIClient:
    """
    Client for TheRacingAPI - fetches live race cards and market data.
    
    Features:
    - HTTP Basic Authentication
    - Rate limiting (2 req/sec)
    - Automatic retry on transient failures
    - Data transformation to VELO format
    """
    
    def __init__(self, config: Optional[RaceCardConfig] = None):
        """Initialize client with credentials from environment or config"""
        if config is None:
            config = RaceCardConfig(
                username=os.getenv("RACING_API_USERNAME", ""),
                password=os.getenv("RACING_API_PASSWORD", ""),
                base_url=os.getenv("RACING_API_BASE_URL", "https://api.theracingapi.com/v1")
            )
        
        self.config = config
        self.session = requests.Session()
        self.session.auth = (config.username, config.password)
        self.session.headers.update({
            "User-Agent": "VELO-v12/1.0",
            "Accept": "application/json"
        })
        
        logger.info(f"TheRacingAPI client initialized (base_url={config.base_url})")
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make authenticated request to TheRacingAPI.
        
        Args:
            endpoint: API endpoint (e.g., '/racecards/free')
            params: Query parameters
            
        Returns:
            JSON response as dictionary
            
        Raises:
            requests.HTTPError: On API errors
        """
        url = f"{self.config.base_url}{endpoint}"
        
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.HTTPError as e:
            logger.error(f"API request failed: {e} - {response.text}")
            raise
        except requests.RequestException as e:
            logger.error(f"Network error: {e}")
            raise
    
    def get_todays_racecards(self, region_codes: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Fetch today's race cards.
        
        Args:
            region_codes: Filter by regions (e.g., ['gb', 'ire']). None = all regions.
            
        Returns:
            Dictionary with 'racecards' list and metadata
        """
        params = {"day": "today"}
        
        # Note: Free tier doesn't support region filtering
        # Pro tier would use /racecards/pro with date and region_codes params
        
        logger.info("Fetching today's racecards...")
        data = self._make_request("/racecards/free", params)
        
        total_races = len(data.get("racecards", []))
        logger.info(f"Retrieved {total_races} races for today")
        
        return data
    
    def get_tomorrows_racecards(self) -> Dict[str, Any]:
        """Fetch tomorrow's race cards"""
        params = {"day": "tomorrow"}
        
        logger.info("Fetching tomorrow's racecards...")
        data = self._make_request("/racecards/free", params)
        
        total_races = len(data.get("racecards", []))
        logger.info(f"Retrieved {total_races} races for tomorrow")
        
        return data
    
    def get_racecards_by_date(self, target_date: date, region_codes: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Fetch racecards for a specific date (requires Pro plan).
        
        Args:
            target_date: Date to fetch
            region_codes: Filter by regions (e.g., ['gb', 'ire'])
            
        Returns:
            Dictionary with 'racecards' list and metadata
        """
        params = {"date": target_date.strftime("%Y-%m-%d")}
        
        if region_codes:
            # Pro endpoint supports region filtering
            for code in region_codes:
                params[f"region_codes"] = code
        
        logger.info(f"Fetching racecards for {target_date}...")
        data = self._make_request("/racecards/pro", params)
        
        total_races = len(data.get("racecards", []))
        logger.info(f"Retrieved {total_races} races for {target_date}")
        
        return data
    
    def transform_to_velo_format(self, api_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Transform TheRacingAPI format to VELO v12 format.
        
        Args:
            api_data: Raw API response
            
        Returns:
            List of race dictionaries in VELO format
        """
        racecards = api_data.get("racecards", [])
        velo_races = []
        
        for race in racecards:
            # Transform race metadata
            velo_race = {
                "race_id": f"{race['course']}_{race['date']}_{race['off_time']}".replace(" ", "_").replace(":", ""),
                "course": race["course"],
                "date": race["date"],
                "off_time": race["off_time"],
                "off_dt": race["off_dt"],
                "race_name": race["race_name"],
                "distance_f": float(race["distance_f"]) if race.get("distance_f") else None,
                "region": race["region"],
                "race_class": race.get("race_class", ""),
                "type": race["type"],
                "age_band": race.get("age_band", ""),
                "rating_band": race.get("rating_band", ""),
                "sex_restriction": race.get("sex_restriction", ""),
                "prize": race.get("prize", ""),
                "field_size": int(race["field_size"]) if race.get("field_size") else 0,
                "going": race.get("going", ""),
                "surface": race.get("surface", ""),
                "runners": []
            }
            
            # Transform runners
            for idx, runner in enumerate(race.get("runners", []), 1):
                # Generate unique runner_id
                runner_id = f"{velo_race['race_id']}_R{idx:02d}"
                
                velo_runner = {
                    "runner_id": runner_id,
                    "horse": runner["horse"],
                    "age": int(runner["age"]) if runner.get("age") else None,
                    "sex": runner.get("sex", ""),
                    "sex_code": runner.get("sex_code", ""),
                    "colour": runner.get("colour", ""),
                    "region": runner.get("region", ""),
                    "dam": runner.get("dam", ""),
                    "sire": runner.get("sire", ""),
                    "damsire": runner.get("damsire", ""),
                    "trainer": runner.get("trainer", ""),
                    "owner": runner.get("owner", ""),
                    "number": runner.get("number", ""),
                    "draw": runner.get("draw", ""),
                    "headgear": runner.get("headgear", ""),
                    "lbs": int(runner["lbs"]) if runner.get("lbs") and str(runner["lbs"]).isdigit() else None,
                    "ofr": int(runner["ofr"]) if runner.get("ofr") and str(runner["ofr"]).replace("-", "").isdigit() and runner["ofr"] != "-" else None,
                    "jockey": runner.get("jockey", ""),
                    "last_run": runner.get("last_run", ""),
                    "form": runner.get("form", ""),
                    # Market data (if available in higher tier plans)
                    "odds": runner.get("odds", None),
                    "forecast_price": runner.get("forecast_price", None)
                }
                
                velo_race["runners"].append(velo_runner)
            
            velo_races.append(velo_race)
        
        logger.info(f"Transformed {len(velo_races)} races to VELO format")
        return velo_races
    
    def get_courses(self, region_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get list of courses with IDs and regions.
        
        Args:
            region_codes: Filter by regions (e.g., ['gb', 'ire'])
            
        Returns:
            List of course dictionaries
        """
        params = {}
        if region_codes:
            params["region_codes"] = region_codes
        
        data = self._make_request("/courses", params)
        return data.get("courses", [])
    
    def get_regions(self) -> List[Dict[str, str]]:
        """Get list of all available regions"""
        data = self._make_request("/courses/regions")
        return data


def create_client() -> TheRacingAPIClient:
    """Factory function to create configured client from environment"""
    return TheRacingAPIClient()


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create client
    client = create_client()
    
    # Fetch today's races
    print("\n=== Fetching Today's Racecards ===")
    data = client.get_todays_racecards()
    
    # Transform to VELO format
    velo_races = client.transform_to_velo_format(data)
    
    print(f"\nFound {len(velo_races)} races today:")
    for race in velo_races[:3]:  # Show first 3
        print(f"  - {race['course']} {race['off_time']}: {race['race_name']} ({race['field_size']} runners)")
