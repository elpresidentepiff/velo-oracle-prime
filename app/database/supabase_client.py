"""
Supabase database client
"""
from typing import Dict, Any, Optional
from app.core import log, settings

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    log.warning("Supabase client not available")


class SupabaseClient:
    """Client for Supabase database operations"""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Supabase client"""
        if not SUPABASE_AVAILABLE:
            log.warning("Supabase package not installed")
            return
        
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            log.warning("Supabase credentials not configured")
            return
        
        try:
            self.client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY
            )
            log.info("Supabase client initialized")
        except Exception as e:
            log.error(f"Failed to initialize Supabase client: {e}")
    
    async def log_prediction(
        self,
        race_id: str,
        prediction: float,
        confidence: float,
        model_version: str,
        features: Dict[str, Any]
    ) -> bool:
        """Log a prediction to the database"""
        if not self.client:
            log.warning("Supabase client not available, skipping log")
            return False
        
        try:
            data = {
                "race_id": race_id,
                "prediction": prediction,
                "confidence": confidence,
                "model_version": model_version,
                "features": features
            }
            
            result = self.client.table("predictions").insert(data).execute()
            log.info(f"Logged prediction for race {race_id}")
            return True
        
        except Exception as e:
            log.error(f"Failed to log prediction: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if database is connected"""
        return self.client is not None


# Global Supabase client instance
supabase_client = SupabaseClient()

