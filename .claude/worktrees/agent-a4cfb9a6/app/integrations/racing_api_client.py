"""
Racing API Client for VÉLØ v11
Provides live race data, form, odds, and market microstructure
"""

import requests
from typing import Dict, List, Optional
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


class RacingAPIClient:
    """
    Client for The Racing API
    Provides comprehensive race data for VÉLØ v11 data fabric
    """
    
    BASE_URL = "https://api.theracingapi.com/v1"
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.auth = (username, password)
        
    def get_todays_meetings(self, region: str = "GB") -> List[Dict]:
        """Get all meetings for today"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/meetings",
                params={"date": date.today().isoformat(), "region": region}
            )
            response.raise_for_status()
            return response.json().get('meetings', [])
        except Exception as e:
            logger.error(f"Error fetching meetings: {e}")
            return []
    
    def get_race_card(self, race_id: str) -> Optional[Dict]:
        """Get detailed race card with runners"""
        try:
            response = self.session.get(f"{self.BASE_URL}/racecards/{race_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching race card {race_id}: {e}")
            return None
    
    def get_runner_form(self, horse_id: str, limit: int = 10) -> List[Dict]:
        """Get horse form history"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/horses/{horse_id}/form",
                params={"limit": limit}
            )
            response.raise_for_status()
            return response.json().get('form', [])
        except Exception as e:
            logger.error(f"Error fetching form for horse {horse_id}: {e}")
            return []
    
    def get_odds_timeline(self, race_id: str) -> List[Dict]:
        """Get odds movement timeline"""
        try:
            response = self.session.get(f"{self.BASE_URL}/odds/{race_id}/timeline")
            response.raise_for_status()
            return response.json().get('timeline', [])
        except Exception as e:
            logger.error(f"Error fetching odds timeline {race_id}: {e}")
            return []
    
    def get_trainer_stats(self, trainer_id: str, track: Optional[str] = None) -> Dict:
        """Get trainer statistics"""
        try:
            params = {}
            if track:
                params['track'] = track
            response = self.session.get(
                f"{self.BASE_URL}/trainers/{trainer_id}/stats",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching trainer stats {trainer_id}: {e}")
            return {}
    
    def get_jockey_stats(self, jockey_id: str, track: Optional[str] = None) -> Dict:
        """Get jockey statistics"""
        try:
            params = {}
            if track:
                params['track'] = track
            response = self.session.get(
                f"{self.BASE_URL}/jockeys/{jockey_id}/stats",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching jockey stats {jockey_id}: {e}")
            return {}
    
    def get_race_results(self, race_id: str) -> Optional[Dict]:
        """Get race results after it's run"""
        try:
            response = self.session.get(f"{self.BASE_URL}/results/{race_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching results {race_id}: {e}")
            return None


# Initialize with credentials
racing_api = RacingAPIClient(
    username="VkP2i6RRIDp2GGrxR6XAaViB",
    password="fqvqglMujliFV94D38uPvwUA"
)
