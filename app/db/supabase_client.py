"""
Supabase Client for VELO
Provides database operations using Supabase REST API
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests

from app.config.supabase_config import (
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
    SUPABASE_SERVICE_KEY,
    SUPABASE_REST_URL,
    TABLES,
)

logger = logging.getLogger(__name__)


class SupabaseClient:
    """
    Supabase client for VELO database operations
    """
    
    def __init__(self, use_service_key: bool = True):
        """
        Initialize Supabase client
        
        Args:
            use_service_key: If True, use service key (bypasses RLS). If False, use anon key.
        """
        self.base_url = SUPABASE_REST_URL
        self.api_key = SUPABASE_SERVICE_KEY if use_service_key else SUPABASE_ANON_KEY
        
        if not self.api_key:
            raise ValueError("Supabase API key not configured")
        
        self.headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
    
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict:
        """
        Make HTTP request to Supabase REST API
        
        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            endpoint: API endpoint (e.g., "/races")
            data: Request body data
            params: Query parameters
            
        Returns:
            Response data as dictionary
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            if response.status_code == 204:  # No content
                return {}
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Supabase API request failed: {e}")
            raise
    
    # ==================== RACE OPERATIONS ====================
    
    def insert_race(self, race_data: Dict) -> Dict:
        """Insert a new race record"""
        return self._request("POST", f"/{TABLES['races']}", data=race_data)
    
    def get_race(self, race_id: str) -> Optional[Dict]:
        """Get race by ID"""
        result = self._request("GET", f"/{TABLES['races']}", params={"race_id": f"eq.{race_id}"})
        return result[0] if result else None
    
    def update_race(self, race_id: str, updates: Dict) -> Dict:
        """Update race record"""
        return self._request("PATCH", f"/{TABLES['races']}", data=updates, params={"race_id": f"eq.{race_id}"})
    
    # ==================== RUNNER OPERATIONS ====================
    
    def insert_runners(self, runners: List[Dict]) -> List[Dict]:
        """Insert multiple runner records"""
        return self._request("POST", f"/{TABLES['runners']}", data=runners)
    
    def get_runners_by_race(self, race_id: str) -> List[Dict]:
        """Get all runners for a race"""
        return self._request("GET", f"/{TABLES['runners']}", params={"race_id": f"eq.{race_id}"})
    
    # ==================== ENGINE RUN OPERATIONS ====================
    
    def insert_engine_run(self, engine_run: Dict) -> Dict:
        """Insert engine run record"""
        return self._request("POST", f"/{TABLES['engine_runs']}", data=engine_run)
    
    def get_engine_run(self, run_id: str) -> Optional[Dict]:
        """Get engine run by ID"""
        result = self._request("GET", f"/{TABLES['engine_runs']}", params={"run_id": f"eq.{run_id}"})
        return result[0] if result else None
    
    def get_recent_engine_runs(self, limit: int = 100) -> List[Dict]:
        """Get recent engine runs"""
        return self._request("GET", f"/{TABLES['engine_runs']}", params={"order": "created_at.desc", "limit": limit})
    
    # ==================== VERDICT OPERATIONS ====================
    
    def insert_verdict(self, verdict: Dict) -> Dict:
        """Insert engine verdict"""
        return self._request("POST", f"/{TABLES['engine_verdicts']}", data=verdict)
    
    def get_verdicts_by_run(self, run_id: str) -> List[Dict]:
        """Get all verdicts for an engine run"""
        return self._request("GET", f"/{TABLES['engine_verdicts']}", params={"run_id": f"eq.{run_id}"})
    
    # ==================== MARKET SNAPSHOT OPERATIONS ====================
    
    def insert_market_snapshot(self, snapshot: Dict) -> Dict:
        """Insert market snapshot"""
        return self._request("POST", f"/{TABLES['market_snapshots']}", data=snapshot)
    
    def get_market_snapshots(self, race_id: str, limit: int = 100) -> List[Dict]:
        """Get market snapshots for a race"""
        return self._request("GET", f"/{TABLES['market_snapshots']}", params={
            "race_id": f"eq.{race_id}",
            "order": "snapshot_time.desc",
            "limit": limit
        })
    
    # ==================== LEARNING EVENTS OPERATIONS ====================
    
    def insert_learning_event(self, event: Dict) -> Dict:
        """Insert learning event"""
        return self._request("POST", f"/{TABLES['learning_events']}", data=event)
    
    def get_learning_events(self, event_type: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get learning events, optionally filtered by type"""
        params = {"order": "event_time.desc", "limit": limit}
        if event_type:
            params["event_type"] = f"eq.{event_type}"
        return self._request("GET", f"/{TABLES['learning_events']}", params=params)
    
    # ==================== PREDICTIONS OPERATIONS ====================
    
    def insert_prediction(self, prediction: Dict) -> Dict:
        """Insert prediction record"""
        return self._request("POST", f"/{TABLES['predictions']}", data=prediction)
    
    def get_predictions_by_race(self, race_id: str) -> List[Dict]:
        """Get predictions for a race"""
        return self._request("GET", f"/{TABLES['predictions']}", params={"race_id": f"eq.{race_id}"})
    
    # ==================== UTILITY OPERATIONS ====================
    
    def execute_rpc(self, function_name: str, params: Dict) -> Any:
        """Execute a Supabase stored procedure/function"""
        return self._request("POST", f"/rpc/{function_name}", data=params)
    
    def health_check(self) -> bool:
        """Check if Supabase connection is healthy"""
        try:
            self._request("GET", f"/{TABLES['races']}", params={"limit": 1})
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


# Singleton instance
_client: Optional[SupabaseClient] = None


def get_client(use_service_key: bool = True) -> SupabaseClient:
    """
    Get singleton Supabase client instance
    
    Args:
        use_service_key: If True, use service key (bypasses RLS)
        
    Returns:
        SupabaseClient instance
    """
    global _client
    if _client is None:
        _client = SupabaseClient(use_service_key=use_service_key)
    return _client
