"""
VÉLØ Oracle - Supabase Database Client
========================================

Provides Supabase connectivity for predictions, models, and race data.

Author: VÉLØ Oracle Team
Version: 2.0.0
"""

import os
from typing import List, Dict, Optional, Any
from datetime import datetime
from supabase import create_client, Client
from loguru import logger


class SupabaseClient:
    """
    Supabase client for VÉLØ Oracle backend.
    
    Handles all database operations for predictions, models, race cards, and results.
    """
    
    def __init__(self, url: str = None, key: str = None):
        """
        Initialize Supabase client.
        
        Args:
            url: Supabase project URL (or from SUPABASE_URL env var)
            key: Supabase anon/service key (or from SUPABASE_KEY env var)
        """
        self.url = url or os.getenv('SUPABASE_URL')
        self.key = key or os.getenv('SUPABASE_KEY')
        
        if not self.url or not self.key:
            raise ValueError("Supabase URL and KEY must be provided or set in environment")
        
        self.client: Client = create_client(self.url, self.key)
        logger.info(f"✅ Supabase client initialized: {self.url}")
    
    # ========================================================================
    # PREDICTIONS
    # ========================================================================
    
    def log_prediction(
        self,
        race_id: str,
        horse_name: str,
        model_name: str,
        predicted_position: int,
        confidence: float,
        win_probability: float,
        metadata: Dict = None
    ) -> Dict:
        """
        Log a prediction to Supabase.
        
        Args:
            race_id: Unique race identifier
            horse_name: Horse name
            model_name: Model that made the prediction
            predicted_position: Predicted finishing position
            confidence: Confidence score (0-1)
            win_probability: Win probability (0-1)
            metadata: Additional prediction metadata
            
        Returns:
            Inserted prediction record
        """
        try:
            data = {
                'race_id': race_id,
                'horse_name': horse_name,
                'model_name': model_name,
                'predicted_position': predicted_position,
                'confidence': confidence,
                'win_probability': win_probability,
                'metadata': metadata or {},
                'created_at': datetime.utcnow().isoformat()
            }
            
            result = self.client.table('predictions').insert(data).execute()
            logger.info(f"✅ Prediction logged: {horse_name} in {race_id}")
            return result.data[0] if result.data else {}
            
        except Exception as e:
            logger.error(f"❌ Failed to log prediction: {e}")
            raise
    
    def get_predictions_by_race(self, race_id: str) -> List[Dict]:
        """
        Get all predictions for a specific race.
        
        Args:
            race_id: Race identifier
            
        Returns:
            List of prediction records
        """
        try:
            result = self.client.table('predictions')\
                .select('*')\
                .eq('race_id', race_id)\
                .execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"❌ Failed to get predictions: {e}")
            return []
    
    def update_prediction_result(
        self,
        prediction_id: int,
        actual_position: int,
        actual_sp: float = None,
        profit_loss: float = None
    ) -> Dict:
        """
        Update prediction with actual race result.
        
        Args:
            prediction_id: Prediction ID
            actual_position: Actual finishing position
            actual_sp: Actual starting price
            profit_loss: Profit/loss if bet was placed
            
        Returns:
            Updated prediction record
        """
        try:
            data = {
                'actual_position': actual_position,
                'actual_sp': actual_sp,
                'profit_loss': profit_loss,
                'result': 'win' if actual_position == 1 else 'loss',
                'updated_at': datetime.utcnow().isoformat()
            }
            
            result = self.client.table('predictions')\
                .update(data)\
                .eq('id', prediction_id)\
                .execute()
            
            logger.info(f"✅ Prediction result updated: {prediction_id}")
            return result.data[0] if result.data else {}
            
        except Exception as e:
            logger.error(f"❌ Failed to update prediction result: {e}")
            raise
    
    # ========================================================================
    # RACE CARDS
    # ========================================================================
    
    def store_racecard(
        self,
        race_id: str,
        race_date: str,
        course: str,
        race_time: str,
        race_name: str,
        runners: List[Dict],
        metadata: Dict = None
    ) -> Dict:
        """
        Store race card data in Supabase.
        
        Args:
            race_id: Unique race identifier
            race_date: Race date (YYYY-MM-DD)
            course: Course name
            race_time: Race time (HH:MM)
            race_name: Race name
            runners: List of runner dictionaries
            metadata: Additional race metadata
            
        Returns:
            Inserted race card record
        """
        try:
            data = {
                'race_id': race_id,
                'race_date': race_date,
                'course': course,
                'race_time': race_time,
                'race_name': race_name,
                'runners': runners,
                'metadata': metadata or {},
                'created_at': datetime.utcnow().isoformat()
            }
            
            result = self.client.table('races')\
                .insert(data)\
                .execute()
            
            logger.info(f"✅ Race card stored: {race_id} - {course}")
            return result.data[0] if result.data else {}
            
        except Exception as e:
            logger.error(f"❌ Failed to store race card: {e}")
            raise
    
    def get_racecard(self, race_id: str) -> Optional[Dict]:
        """
        Get race card data from Supabase.
        
        Args:
            race_id: Race identifier
            
        Returns:
            Race card record or None
        """
        try:
            result = self.client.table('races')\
                .select('*')\
                .eq('race_id', race_id)\
                .execute()
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.error(f"❌ Failed to get race card: {e}")
            return None
    
    def get_upcoming_races(self, limit: int = 10) -> List[Dict]:
        """
        Get upcoming races.
        
        Args:
            limit: Maximum number of races to return
            
        Returns:
            List of race records
        """
        try:
            today = datetime.utcnow().date().isoformat()
            
            result = self.client.table('races')\
                .select('*')\
                .gte('race_date', today)\
                .order('race_date', desc=False)\
                .order('race_time', desc=False)\
                .limit(limit)\
                .execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"❌ Failed to get upcoming races: {e}")
            return []
    
    # ========================================================================
    # MODELS
    # ========================================================================
    
    def store_model_log(
        self,
        model_name: str,
        model_version: str,
        accuracy: float,
        performance_metrics: Dict,
        metadata: Dict = None
    ) -> Dict:
        """
        Store model performance log.
        
        Args:
            model_name: Model name
            model_version: Model version
            accuracy: Model accuracy
            performance_metrics: Performance metrics dictionary
            metadata: Additional metadata
            
        Returns:
            Inserted model log record
        """
        try:
            data = {
                'model_name': model_name,
                'model_version': model_version,
                'accuracy': accuracy,
                'performance_metrics': performance_metrics,
                'metadata': metadata or {},
                'created_at': datetime.utcnow().isoformat()
            }
            
            result = self.client.table('models')\
                .insert(data)\
                .execute()
            
            logger.info(f"✅ Model log stored: {model_name} v{model_version}")
            return result.data[0] if result.data else {}
            
        except Exception as e:
            logger.error(f"❌ Failed to store model log: {e}")
            raise
    
    def get_models(self) -> List[Dict]:
        """
        Get all model records.
        
        Returns:
            List of model records
        """
        try:
            result = self.client.table('models')\
                .select('*')\
                .order('created_at', desc=True)\
                .execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"❌ Failed to get models: {e}")
            return []
    
    def get_active_models(self) -> List[Dict]:
        """
        Get active model records.
        
        Returns:
            List of active model records
        """
        try:
            result = self.client.table('models')\
                .select('*')\
                .eq('is_active', True)\
                .order('created_at', desc=True)\
                .execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"❌ Failed to get active models: {e}")
            return []
    
    # ========================================================================
    # RESULTS
    # ========================================================================
    
    def store_race_result(
        self,
        race_id: str,
        results: List[Dict],
        metadata: Dict = None
    ) -> Dict:
        """
        Store race results.
        
        Args:
            race_id: Race identifier
            results: List of result dictionaries (position, horse, sp, etc.)
            metadata: Additional metadata
            
        Returns:
            Inserted result record
        """
        try:
            data = {
                'race_id': race_id,
                'results': results,
                'metadata': metadata or {},
                'created_at': datetime.utcnow().isoformat()
            }
            
            result = self.client.table('results')\
                .insert(data)\
                .execute()
            
            logger.info(f"✅ Race result stored: {race_id}")
            return result.data[0] if result.data else {}
            
        except Exception as e:
            logger.error(f"❌ Failed to store race result: {e}")
            raise
    
    def get_race_result(self, race_id: str) -> Optional[Dict]:
        """
        Get race result.
        
        Args:
            race_id: Race identifier
            
        Returns:
            Result record or None
        """
        try:
            result = self.client.table('results')\
                .select('*')\
                .eq('race_id', race_id)\
                .execute()
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.error(f"❌ Failed to get race result: {e}")
            return None
    
    # ========================================================================
    # PREDICTION LOGS (for analysis)
    # ========================================================================
    
    def get_prediction_performance(
        self,
        model_name: str = None,
        days: int = 30
    ) -> Dict:
        """
        Get prediction performance statistics.
        
        Args:
            model_name: Filter by model name (optional)
            days: Number of days to analyze
            
        Returns:
            Performance statistics dictionary
        """
        try:
            # This would use a Supabase view or RPC function
            # For now, return a placeholder
            result = self.client.rpc('get_prediction_performance', {
                'model_name_filter': model_name,
                'days_back': days
            }).execute()
            
            return result.data if result.data else {}
            
        except Exception as e:
            logger.warning(f"⚠️ Prediction performance query not available: {e}")
            return {}
    
    # ========================================================================
    # UTILITY
    # ========================================================================
    
    def health_check(self) -> bool:
        """
        Check Supabase connection health.
        
        Returns:
            True if connection is healthy
        """
        try:
            # Try a simple query
            result = self.client.table('models').select('id').limit(1).execute()
            logger.info("✅ Supabase health check passed")
            return True
        except Exception as e:
            logger.error(f"❌ Supabase health check failed: {e}")
            return False


# Singleton instance
_supabase_client: Optional[SupabaseClient] = None


def get_supabase_client() -> SupabaseClient:
    """
    Get singleton Supabase client instance.
    
    Returns:
        SupabaseClient instance
    """
    global _supabase_client
    
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
    
    return _supabase_client


# Test the connection
if __name__ == "__main__":
    import sys
    
    # Set credentials for testing
    os.environ['SUPABASE_URL'] = 'https://ltbsxbvfsxtnharjvqcm.supabase.co'
    os.environ['SUPABASE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx0YnN4YnZmc3h0bmhhcmp2cWNtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjM0ODgzNjksImV4cCI6MjA3OTA2NDM2OX0.iS1Sixo77BhZ2UQVwqVQcGOyBocSIy9ApABvsgLGmhY'
    
    print("🔮 VÉLØ Oracle - Supabase Client Test\n")
    print("="*60)
    
    try:
        client = SupabaseClient()
        
        # Health check
        print("\n1. Health Check...")
        if client.health_check():
            print("   ✅ Connection successful")
        else:
            print("   ❌ Connection failed")
            sys.exit(1)
        
        # Test get models
        print("\n2. Fetching models...")
        models = client.get_models()
        print(f"   Found {len(models)} model(s)")
        
        # Test get upcoming races
        print("\n3. Fetching upcoming races...")
        races = client.get_upcoming_races(limit=5)
        print(f"   Found {len(races)} upcoming race(s)")
        
        print("\n" + "="*60)
        print("✅ Supabase client working!\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)
