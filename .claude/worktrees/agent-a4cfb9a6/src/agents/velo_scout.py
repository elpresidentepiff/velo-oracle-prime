"""
VÉLØ v9.0++ CHAREX - VÉLØ SCOUT Agent

Pulls racecards via Racing API and converts to long-form input.
Autonomous race data watcher and preparation agent.
"""

import os
import requests
import base64
from typing import Dict, List, Optional
from datetime import datetime, date


class VeloScout:
    """
    VÉLØ SCOUT - Race Data Fetcher
    
    Retrieves race information from The Racing API and prepares
    it for analysis by VÉLØ PRIME.
    """
    
    def __init__(self, api_username: Optional[str] = None, api_password: Optional[str] = None):
        """
        Initialize VÉLØ SCOUT agent.
        
        Args:
            api_username: Racing API username (defaults to env var)
            api_password: Racing API password (defaults to env var)
        """
        self.name = "VÉLØ_SCOUT"
        self.version = "v9.0++"
        self.status = "STANDBY"
        
        # API Configuration
        self.api_username = api_username or os.getenv("RACING_API_USERNAME", "")
        self.api_password = api_password or os.getenv("RACING_API_PASSWORD", "")
        self.api_base_url = os.getenv("RACING_API_BASE_URL", "https://api.theracingapi.com/v1")
        
        # Setup authentication
        self._setup_auth()
        
    def _setup_auth(self) -> None:
        """Setup Basic Authentication headers."""
        if self.api_username and self.api_password:
            credentials = f"{self.api_username}:{self.api_password}"
            encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
            self.headers = {
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/json"
            }
        else:
            self.headers = {}
    
    def activate(self) -> None:
        """Activate VÉLØ SCOUT agent."""
        self.status = "ACTIVE"
        print(f"\n🔍 {self.name} ACTIVATED")
        print(f"API Endpoint: {self.api_base_url}")
        print(f"Authentication: {'✅ Configured' if self.headers else '⚠️  Not configured'}\n")
    
    def fetch_today_races(self, region: str = "GB") -> List[Dict]:
        """
        Fetch all races scheduled for today.
        
        Args:
            region: Region code (GB, IRE, etc.)
            
        Returns:
            List of race dictionaries
        """
        if self.status != "ACTIVE":
            raise RuntimeError("VÉLØ SCOUT not active. Call activate() first.")
        
        today = date.today().isoformat()
        endpoint = f"{self.api_base_url}/races"
        
        params = {
            "date": today,
            "region": region
        }
        
        try:
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            races = data.get("races", []) if isinstance(data, dict) else data
            
            print(f"📡 SCOUT: Fetched {len(races)} races for {today}")
            return races
            
        except requests.exceptions.RequestException as e:
            print(f"❌ SCOUT ERROR: Failed to fetch races - {str(e)}")
            return []
    
    def fetch_race_card(self, race_id: str) -> Optional[Dict]:
        """
        Fetch detailed race card for a specific race.
        
        Args:
            race_id: Unique race identifier
            
        Returns:
            Race card dictionary with full details
        """
        if self.status != "ACTIVE":
            raise RuntimeError("VÉLØ SCOUT not active. Call activate() first.")
        
        endpoint = f"{self.api_base_url}/races/{race_id}"
        
        try:
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            race_card = response.json()
            print(f"📡 SCOUT: Fetched race card for {race_id}")
            return race_card
            
        except requests.exceptions.RequestException as e:
            print(f"❌ SCOUT ERROR: Failed to fetch race card - {str(e)}")
            return None
    
    def fetch_runners(self, race_id: str) -> List[Dict]:
        """
        Fetch all runners/horses for a specific race.
        
        Args:
            race_id: Unique race identifier
            
        Returns:
            List of runner dictionaries
        """
        if self.status != "ACTIVE":
            raise RuntimeError("VÉLØ SCOUT not active. Call activate() first.")
        
        endpoint = f"{self.api_base_url}/races/{race_id}/runners"
        
        try:
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            runners = data.get("runners", []) if isinstance(data, dict) else data
            
            print(f"📡 SCOUT: Fetched {len(runners)} runners for race {race_id}")
            return runners
            
        except requests.exceptions.RequestException as e:
            print(f"❌ SCOUT ERROR: Failed to fetch runners - {str(e)}")
            return []
    
    def convert_to_longform(self, race_card: Dict, runners: List[Dict]) -> str:
        """
        Convert API data to long-form text format for VÉLØ PRIME.
        
        Per VÉLØ protocol: All data must be in long-form written message,
        never as CSV or file.
        
        Args:
            race_card: Race details
            runners: List of runners
            
        Returns:
            Long-form text representation
        """
        output = []
        
        # Race header
        output.append("=" * 80)
        output.append(f"RACE: {race_card.get('course', 'Unknown')} - {race_card.get('time', 'Unknown')}")
        output.append(f"Type: {race_card.get('race_type', 'Unknown')}")
        output.append(f"Distance: {race_card.get('distance', 'Unknown')}")
        output.append(f"Going: {race_card.get('going', 'Unknown')}")
        output.append(f"Class: {race_card.get('class', 'Unknown')}")
        output.append(f"Field Size: {len(runners)}")
        output.append("=" * 80)
        output.append("")
        
        # Each runner in detail
        for i, runner in enumerate(runners, 1):
            output.append(f"RUNNER #{i}: {runner.get('name', 'Unknown')}")
            output.append(f"  Number: {runner.get('number', 'N/A')}")
            output.append(f"  Form: {runner.get('form', 'N/A')}")
            output.append(f"  Age: {runner.get('age', 'N/A')}")
            output.append(f"  Weight: {runner.get('weight', 'N/A')}")
            output.append(f"  OR: {runner.get('official_rating', 'N/A')}")
            output.append(f"  TS: {runner.get('topspeed', 'N/A')}")
            output.append(f"  RPR: {runner.get('rpr', 'N/A')}")
            output.append(f"  Jockey: {runner.get('jockey', 'N/A')}")
            output.append(f"  Trainer: {runner.get('trainer', 'N/A')}")
            output.append(f"  Owner: {runner.get('owner', 'N/A')}")
            output.append(f"  Odds: {runner.get('odds', 'N/A')}")
            output.append(f"  Breeding: {runner.get('sire', 'N/A')} - {runner.get('dam', 'N/A')}")
            output.append("")
        
        return "\n".join(output)
    
    def prepare_race_for_analysis(self, race_id: str) -> Optional[str]:
        """
        Complete pipeline: fetch race data and convert to long-form.
        
        Args:
            race_id: Unique race identifier
            
        Returns:
            Long-form text ready for VÉLØ PRIME analysis
        """
        print(f"\n🔍 SCOUT: Preparing race {race_id} for analysis...")
        
        # Fetch race card
        race_card = self.fetch_race_card(race_id)
        if not race_card:
            return None
        
        # Fetch runners
        runners = self.fetch_runners(race_id)
        if not runners:
            return None
        
        # Convert to long-form
        longform_text = self.convert_to_longform(race_card, runners)
        
        print(f"✅ SCOUT: Race data prepared ({len(longform_text)} characters)")
        
        return longform_text
    
    def get_status(self) -> Dict:
        """Get current agent status."""
        return {
            "agent": self.name,
            "version": self.version,
            "status": self.status,
            "api_configured": bool(self.headers),
            "api_endpoint": self.api_base_url
        }


def main():
    """Test VÉLØ SCOUT agent."""
    print("🔍 VÉLØ SCOUT - Race Data Fetcher")
    print("="*60)
    
    scout = VeloScout()
    scout.activate()
    
    # Display status
    status = scout.get_status()
    print(f"\n📊 SCOUT Status:")
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    # Note: Actual API calls require valid credentials
    print("\n⚠️  Note: API calls require valid Racing API credentials")
    print("Set RACING_API_USERNAME and RACING_API_PASSWORD environment variables")


if __name__ == "__main__":
    main()

