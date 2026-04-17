"""
VÉLØ Oracle - Supabase Telemetry Pipeline
Persistent logging and telemetry to Supabase
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.warning("supabase-py not installed. Run: pip install supabase")


class SupabaseTelemetry:
    """
    Supabase telemetry pipeline
    
    Tables:
    - predictions: Prediction logs
    - backtests: Backtest results
    - model_metrics: Model performance metrics
    - drift_alerts: Drift detection alerts
    - system_health: System health checks
    """
    
    def __init__(
        self,
        supabase_url: str = None,
        supabase_key: str = None
    ):
        if not SUPABASE_AVAILABLE:
            logger.warning("Supabase not available - running in mock mode")
            self.client = None
            return
        
        if not supabase_url or not supabase_key:
            logger.warning("Supabase credentials not provided - running in mock mode")
            self.client = None
            return
        
        self.client: Client = create_client(supabase_url, supabase_key)
        logger.info("✅ Connected to Supabase")
    
    def log_prediction(
        self,
        race_id: str,
        runner_id: str,
        probability: float,
        edge: float,
        confidence: float,
        risk_band: str,
        market_odds: float = None,
        actual_result: str = None
    ) -> bool:
        """
        Log prediction to Supabase
        
        Args:
            race_id: Race identifier
            runner_id: Runner identifier
            probability: Model probability
            edge: Calculated edge
            confidence: Confidence score
            risk_band: Risk classification
            market_odds: Market odds (optional)
            actual_result: Actual race result (optional)
            
        Returns:
            Success status
        """
        try:
            data = {
                "timestamp": datetime.utcnow().isoformat(),
                "race_id": race_id,
                "runner_id": runner_id,
                "probability": probability,
                "edge": edge,
                "confidence": confidence,
                "risk_band": risk_band,
                "market_odds": market_odds,
                "actual_result": actual_result
            }
            
            if self.client:
                self.client.table("predictions").insert(data).execute()
                logger.info(f"✅ Logged prediction: {race_id}/{runner_id}")
            else:
                logger.info(f"📝 [MOCK] Logged prediction: {race_id}/{runner_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to log prediction: {e}")
            return False
    
    def log_backtest(
        self,
        backtest_id: str,
        version: str,
        sample_size: int,
        roi: float,
        win_rate: float,
        auc: float,
        log_loss: float,
        max_drawdown: float,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """Log backtest results"""
        try:
            data = {
                "timestamp": datetime.utcnow().isoformat(),
                "backtest_id": backtest_id,
                "version": version,
                "sample_size": sample_size,
                "roi": roi,
                "win_rate": win_rate,
                "auc": auc,
                "log_loss": log_loss,
                "max_drawdown": max_drawdown,
                "metadata": json.dumps(metadata) if metadata else None
            }
            
            if self.client:
                self.client.table("backtests").insert(data).execute()
                logger.info(f"✅ Logged backtest: {backtest_id}")
            else:
                logger.info(f"📝 [MOCK] Logged backtest: {backtest_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to log backtest: {e}")
            return False
    
    def log_model_metrics(
        self,
        model_name: str,
        version: str,
        auc: float,
        log_loss: float,
        accuracy: float = None,
        precision: float = None,
        recall: float = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """Log model performance metrics"""
        try:
            data = {
                "timestamp": datetime.utcnow().isoformat(),
                "model_name": model_name,
                "version": version,
                "auc": auc,
                "log_loss": log_loss,
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "metadata": json.dumps(metadata) if metadata else None
            }
            
            if self.client:
                self.client.table("model_metrics").insert(data).execute()
                logger.info(f"✅ Logged metrics: {model_name} {version}")
            else:
                logger.info(f"📝 [MOCK] Logged metrics: {model_name} {version}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to log metrics: {e}")
            return False
    
    def log_drift_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        details: Dict[str, Any] = None
    ) -> bool:
        """Log drift detection alert"""
        try:
            data = {
                "timestamp": datetime.utcnow().isoformat(),
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "details": json.dumps(details) if details else None
            }
            
            if self.client:
                self.client.table("drift_alerts").insert(data).execute()
                logger.warning(f"⚠️  Logged drift alert: {alert_type}")
            else:
                logger.warning(f"📝 [MOCK] Logged drift alert: {alert_type}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to log drift alert: {e}")
            return False
    
    def log_system_health(
        self,
        component: str,
        status: str,
        response_time_ms: float = None,
        error_count: int = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """Log system health check"""
        try:
            data = {
                "timestamp": datetime.utcnow().isoformat(),
                "component": component,
                "status": status,
                "response_time_ms": response_time_ms,
                "error_count": error_count,
                "metadata": json.dumps(metadata) if metadata else None
            }
            
            if self.client:
                self.client.table("system_health").insert(data).execute()
                logger.info(f"✅ Logged health: {component} ({status})")
            else:
                logger.info(f"📝 [MOCK] Logged health: {component} ({status})")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to log health: {e}")
            return False
    
    def get_recent_predictions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent predictions"""
        try:
            if self.client:
                response = self.client.table("predictions")\
                    .select("*")\
                    .order("timestamp", desc=True)\
                    .limit(limit)\
                    .execute()
                return response.data
            else:
                logger.info(f"📝 [MOCK] Get recent predictions (limit={limit})")
                return []
        except Exception as e:
            logger.error(f"❌ Failed to get predictions: {e}")
            return []
    
    def get_model_performance_history(
        self,
        model_name: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get model performance history"""
        try:
            if self.client:
                response = self.client.table("model_metrics")\
                    .select("*")\
                    .eq("model_name", model_name)\
                    .order("timestamp", desc=True)\
                    .limit(limit)\
                    .execute()
                return response.data
            else:
                logger.info(f"📝 [MOCK] Get performance history for {model_name}")
                return []
        except Exception as e:
            logger.error(f"❌ Failed to get performance history: {e}")
            return []


if __name__ == "__main__":
    # Test telemetry
    print("="*60)
    print("Supabase Telemetry Test")
    print("="*60)
    
    # Create telemetry instance (mock mode)
    telemetry = SupabaseTelemetry()
    
    # Test prediction logging
    print("\n1. Log Prediction:")
    telemetry.log_prediction(
        race_id="TEST_001",
        runner_id="R1",
        probability=0.25,
        edge=0.05,
        confidence=0.85,
        risk_band="MEDIUM",
        market_odds=5.0
    )
    
    # Test backtest logging
    print("\n2. Log Backtest:")
    telemetry.log_backtest(
        backtest_id="BT_TEST_001",
        version="v15.0",
        sample_size=50000,
        roi=1.21,
        win_rate=0.4024,
        auc=0.719,
        log_loss=0.533,
        max_drawdown=0.20
    )
    
    # Test model metrics logging
    print("\n3. Log Model Metrics:")
    telemetry.log_model_metrics(
        model_name="SQPE",
        version="v15.0",
        auc=0.846,
        log_loss=0.412,
        accuracy=0.742
    )
    
    # Test drift alert logging
    print("\n4. Log Drift Alert:")
    telemetry.log_drift_alert(
        alert_type="feature_drift",
        severity="WARNING",
        message="3 features drifted beyond threshold",
        details={"drifted_features": ["speed", "rating", "form"]}
    )
    
    # Test system health logging
    print("\n5. Log System Health:")
    telemetry.log_system_health(
        component="UMA",
        status="healthy",
        response_time_ms=45.2,
        error_count=0
    )
    
    print("\n✅ Telemetry test complete")
    print("Note: Running in mock mode. Configure Supabase credentials for production.")
