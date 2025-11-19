"""
VÉLØ Oracle - Performance Tracker
Track model performance metrics over time
"""
import json
from datetime import datetime
from typing import Dict, Any, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceTracker:
    """
    Track model performance metrics
    
    Metrics:
    - AUC
    - Log Loss
    - ROI
    - Win Rate
    - Calibration Error
    """
    
    def __init__(self, log_path: str = "logs/performance_log.json"):
        self.log_path = log_path
        self.metrics_history = []
        self.load_history()
    
    def load_history(self):
        """Load performance history"""
        try:
            with open(self.log_path, 'r') as f:
                self.metrics_history = json.load(f)
            logger.info(f"✅ Loaded {len(self.metrics_history)} performance records")
        except:
            self.metrics_history = []
            logger.info("No existing performance history found")
    
    def save_history(self):
        """Save performance history"""
        with open(self.log_path, 'w') as f:
            json.dump(self.metrics_history, f, indent=2)
        logger.info(f"✅ Saved performance history ({len(self.metrics_history)} records)")
    
    def log_metrics(
        self,
        model_name: str,
        metrics: Dict[str, float],
        metadata: Dict[str, Any] = None
    ):
        """Log performance metrics"""
        
        record = {
            'timestamp': datetime.utcnow().isoformat(),
            'model_name': model_name,
            'metrics': metrics,
            'metadata': metadata or {}
        }
        
        self.metrics_history.append(record)
        self.save_history()
        
        logger.info(f"✅ Logged metrics for {model_name}")
        for metric, value in metrics.items():
            logger.info(f"   {metric}: {value}")
    
    def get_latest_metrics(self, model_name: str = None) -> Dict[str, Any]:
        """Get latest metrics for a model"""
        
        if model_name:
            records = [r for r in self.metrics_history if r['model_name'] == model_name]
        else:
            records = self.metrics_history
        
        if records:
            return records[-1]
        else:
            return {}
    
    def get_metric_trend(
        self,
        model_name: str,
        metric_name: str,
        window: int = 10
    ) -> List[float]:
        """Get trend for a specific metric"""
        
        records = [r for r in self.metrics_history if r['model_name'] == model_name]
        values = [r['metrics'].get(metric_name) for r in records[-window:]]
        
        return [v for v in values if v is not None]
    
    def check_degradation(
        self,
        model_name: str,
        metric_name: str = 'auc',
        threshold: float = 0.02,
        window: int = 5
    ) -> Dict[str, Any]:
        """Check for performance degradation"""
        
        trend = self.get_metric_trend(model_name, metric_name, window)
        
        if len(trend) < 2:
            return {
                'degraded': False,
                'reason': 'Insufficient data'
            }
        
        baseline = trend[0]
        current = trend[-1]
        drop = baseline - current
        
        is_degraded = drop > threshold
        
        return {
            'degraded': is_degraded,
            'baseline': baseline,
            'current': current,
            'drop': drop,
            'threshold': threshold,
            'trend': trend
        }


if __name__ == "__main__":
    # Test performance tracker
    print("="*60)
    print("Performance Tracker Test")
    print("="*60)
    
    tracker = PerformanceTracker(log_path="logs/test_performance_log.json")
    
    # Log some metrics
    tracker.log_metrics(
        model_name="sqpe_v14",
        metrics={
            'auc': 0.87,
            'logloss': 0.42,
            'roi': 1.21
        },
        metadata={'dataset': 'test_10k'}
    )
    
    tracker.log_metrics(
        model_name="sqpe_v14",
        metrics={
            'auc': 0.85,
            'logloss': 0.45,
            'roi': 1.15
        },
        metadata={'dataset': 'test_10k'}
    )
    
    # Check degradation
    degradation = tracker.check_degradation('sqpe_v14', 'auc', threshold=0.02)
    
    print("\nDegradation Check:")
    print(f"  Degraded: {degradation['degraded']}")
    if degradation.get('drop'):
        print(f"  Baseline: {degradation['baseline']:.4f}")
        print(f"  Current: {degradation['current']:.4f}")
        print(f"  Drop: {degradation['drop']:.4f}")
    
    print("\n✅ Performance tracker test complete")
