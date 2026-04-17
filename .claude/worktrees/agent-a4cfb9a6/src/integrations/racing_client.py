"""
VÉLØ v10 - Racing API Client (Contract-Based)
Wrapper around legacy racing_api.py that returns Pydantic contracts
"""

from typing import List, Optional
import logging

from .racing_api import RacingAPIClient as LegacyRacingClient
from ..modules.contracts import Racecard, Runner, Going
from .http import HttpClient

logger = logging.getLogger("velo.racing")


class RacingClient:
    """
    Modern Racing API client that returns Pydantic contracts
    Uses robust HTTP layer with retry logic
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize Racing API client
        
        Args:
            api_key: Racing API key (from settings if not provided)
        """
        from ..core.settings import settings
        
        self.api_key = api_key or settings.RACING_API_KEY
        self.base_url = settings.RACING_API_BASE_URL
        
        # Use legacy client for now
        self.legacy_client = LegacyRacingClient(api_key=self.api_key)
        
        self.http = HttpClient()
        logger.info("RacingClient initialized")
    
    def get_racecard(
        self,
        date: str,
        course: str,
        time: str
    ) -> Optional[Racecard]:
        """
        Get racecard for a specific race
        
        Args:
            date: Race date (YYYY-MM-DD)
            course: Course name
            time: Race time (HH:MM)
        
        Returns:
            Racecard with runners and race details, or None if unavailable
        """
        try:
            # Get race data from legacy client
            race_data = self.legacy_client.get_race(date, course, time)
            
            if not race_data:
                return None
            
            # Convert runners to contracts
            runners = []
            for runner_data in race_data.get('runners', []):
                runner = Runner(
                    number=runner_data.get('number', 0),
                    name=runner_data.get('name', ''),
                    age=runner_data.get('age'),
                    weight=runner_data.get('weight'),
                    or_rating=runner_data.get('official_rating'),
                    ts=runner_data.get('ts'),
                    rpr=runner_data.get('rpr'),
                    jockey=runner_data.get('jockey'),
                    jockey_sr5y=runner_data.get('jockey_sr5y'),
                    trainer=runner_data.get('trainer'),
                    trainer_sr5y=runner_data.get('trainer_sr5y'),
                    last6=runner_data.get('form', '').split('-') if runner_data.get('form') else None,
                    breeding=runner_data.get('breeding'),
                    owner=runner_data.get('owner'),
                    days_since_last_run=runner_data.get('days_since_last_run'),
                    career_wins=runner_data.get('career_wins'),
                    career_runs=runner_data.get('career_runs')
                )
                runners.append(runner)
            
            # Parse going
            going_str = race_data.get('going', '').lower()
            going = Going.UNKNOWN
            if 'firm' in going_str:
                going = Going.FIRM
            elif 'good to firm' in going_str:
                going = Going.GOOD_TO_FIRM
            elif 'good to soft' in going_str:
                going = Going.GOOD_TO_SOFT
            elif 'good' in going_str:
                going = Going.GOOD
            elif 'soft' in going_str:
                going = Going.SOFT
            elif 'heavy' in going_str:
                going = Going.HEAVY
            
            # Create racecard
            racecard = Racecard(
                date=date,
                course=course,
                time=time,
                race_id=race_data.get('race_id'),
                race_name=race_data.get('race_name'),
                distance=race_data.get('distance'),
                distance_meters=race_data.get('distance_meters'),
                going=going,
                race_class=race_data.get('class'),
                prize_money=race_data.get('prize'),
                runners=runners,
                num_runners=len(runners),
                non_runners=race_data.get('non_runners', [])
            )
            
            return racecard
            
        except Exception as e:
            logger.error(f"Error getting racecard: {e}")
            return None
    
    def get_historical_races(
        self,
        course: str = None,
        date_from: str = None,
        date_to: str = None,
        limit: int = 100
    ) -> List[Racecard]:
        """
        Get historical race data
        
        Args:
            course: Filter by course (optional)
            date_from: Start date (YYYY-MM-DD, optional)
            date_to: End date (YYYY-MM-DD, optional)
            limit: Maximum number of races to return
        
        Returns:
            List of Racecard objects
        """
        try:
            races_data = self.legacy_client.get_historical_races(
                course=course,
                date_from=date_from,
                date_to=date_to,
                limit=limit
            )
            
            racecards = []
            for race_data in races_data:
                try:
                    racecard = self.get_racecard(
                        date=race_data.get('date', ''),
                        course=race_data.get('course', ''),
                        time=race_data.get('time', '')
                    )
                    if racecard:
                        racecards.append(racecard)
                except Exception as e:
                    logger.warning(f"Error converting race to racecard: {e}")
                    continue
            
            return racecards
            
        except Exception as e:
            logger.error(f"Error getting historical races: {e}")
            return []
