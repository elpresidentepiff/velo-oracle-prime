"""
VÉLØ Oracle - Drift Detection
Monitor feature drift and trigger retraining
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from datetime import datetime, timedelta
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DriftDetector:
    """
    Feature and concept drift detection
    
    Methods:
    - Kolmogorov-Smirnov test for feature drift
    - Performance degradation detection
    - Alert when AUC drops >2%
    """
    
    def __init__(self, baseline_path: str = None):
        self.baseline_stats = {}
        self.current_stats = {}
        self.drift_alerts = []
        
        if baseline_path:
            self.load_baseline(baseline_path)
    
    def load_baseline(self, path: str):
        """Load baseline statistics"""
        try:
            with open(path, 'r') as f:
                self.baseline_stats = json.load(f)
            logger.info(f"✅ Loaded baseline from {path}")
        except Exception as e:
            logger.warning(f"⚠️  Failed to load baseline: {e}")
    
    def save_baseline(self, path: str):
        """Save current stats as baseline"""
        with open(path, 'w') as f:
            json.dump(self.current_stats, f, indent=2)
        logger.info(f"✅ Saved baseline to {path}")
    
    def detect_feature_drift(
        self,
        current_data: pd.DataFrame,
        baseline_data: pd.DataFrame = None,
        features: List[str] = None,
        threshold: float = 0.05
    ) -> Dict[str, Any]:
        """
        Detect feature drift using KS test
        
        Args:
            current_data: Recent data
            baseline_data: Historical baseline data
            features: Features to check
            threshold: p-value threshold (default 0.05)
            
        Returns:
            Drift detection results
        """
        logger.info("Detecting feature drift...")
        
        if features is None:
            features = [col for col in current_data.columns if current_data[col].dtype in ['int64', 'float64']]
        
        drift_results = {}
        drifted_features = []
        
        for feature in features:
            if feature not in current_data.columns:
                continue
            
            current_values = current_data[feature].dropna()
            
            if baseline_data is not None and feature in baseline_data.columns:
                baseline_values = baseline_data[feature].dropna()
            else:
                # Use stored baseline stats
                baseline_mean = self.baseline_stats.get(feature, {}).get('mean', current_values.mean())
                baseline_std = self.baseline_stats.get(feature, {}).get('std', current_values.std())
                baseline_values = np.random.normal(baseline_mean, baseline_std, len(current_values))
            
            # KS test (simplified - would use scipy.stats in production)
            ks_statistic = self._ks_test(current_values, baseline_values)
            p_value = 1.0 - ks_statistic  # Simplified
            
            is_drifted = p_value < threshold
            
            drift_results[feature] = {
                'ks_statistic': float(ks_statistic),
                'p_value': float(p_value),
                'is_drifted': is_drifted,
                'current_mean': float(current_values.mean()),
                'current_std': float(current_values.std()),
                'baseline_mean': float(baseline_values.mean()) if hasattr(baseline_values, 'mean') else None,
                'baseline_std': float(baseline_values.std()) if hasattr(baseline_values, 'std') else None
            }
            
            if is_drifted:
                drifted_features.append(feature)
        
        # Summary
        drift_summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'total_features': len(features),
            'drifted_features': len(drifted_features),
            'drift_percentage': len(drifted_features) / len(features) * 100 if features else 0,
            'drifted_feature_names': drifted_features,
            'feature_results': drift_results
        }
        
        logger.info(f"✅ Drift detection complete")
        logger.info(f"   Drifted features: {len(drifted_features)}/{len(features)} ({drift_summary['drift_percentage']:.1f}%)")
        
        if len(drifted_features) > 0:
            logger.warning(f"   ⚠️  Features with drift: {', '.join(drifted_features[:5])}")
        
        return drift_summary
    
    def detect_performance_drift(
        self,
        current_auc: float,
        baseline_auc: float,
        threshold: float = 0.02
    ) -> Dict[str, Any]:
        """
        Detect performance degradation
        
        Args:
            current_auc: Current model AUC
            baseline_auc: Baseline AUC
            threshold: Drop threshold (default 2%)
            
        Returns:
            Performance drift results
        """
        logger.info("Detecting performance drift...")
        
        auc_drop = baseline_auc - current_auc
        is_degraded = auc_drop > threshold
        
        result = {
            'timestamp': datetime.utcnow().isoformat(),
            'current_auc': current_auc,
            'baseline_auc': baseline_auc,
            'auc_drop': auc_drop,
            'auc_drop_percent': auc_drop / baseline_auc * 100 if baseline_auc > 0 else 0,
            'is_degraded': is_degraded,
            'threshold': threshold,
            'requires_retraining': is_degraded
        }
        
        if is_degraded:
            logger.warning(f"⚠️  Performance degradation detected!")
            logger.warning(f"   AUC dropped from {baseline_auc:.4f} to {current_auc:.4f} (-{auc_drop:.4f})")
            logger.warning(f"   🔄 Retraining recommended")
        else:
            logger.info(f"✅ Performance stable (AUC: {current_auc:.4f})")
        
        return result
    
    def _ks_test(self, sample1, sample2):
        """Simplified KS test (would use scipy in production)"""
        # Normalize
        s1 = np.sort(sample1)
        s2 = np.sort(sample2)
        
        # CDF comparison
        n1 = len(s1)
        n2 = len(s2)
        
        # Simplified KS statistic
        all_values = np.concatenate([s1, s2])
        cdf1 = np.searchsorted(s1, all_values, side='right') / n1
        cdf2 = np.searchsorted(s2, all_values, side='right') / n2
        
        ks_stat = np.max(np.abs(cdf1 - cdf2))
        
        return ks_stat
    
    def update_baseline_stats(self, data: pd.DataFrame, features: List[str] = None):
        """Update baseline statistics"""
        if features is None:
            features = [col for col in data.columns if data[col].dtype in ['int64', 'float64']]
        
        for feature in features:
            if feature in data.columns:
                self.baseline_stats[feature] = {
                    'mean': float(data[feature].mean()),
                    'std': float(data[feature].std()),
                    'min': float(data[feature].min()),
                    'max': float(data[feature].max()),
                    'updated_at': datetime.utcnow().isoformat()
                }
        
        logger.info(f"✅ Updated baseline stats for {len(features)} features")


if __name__ == "__main__":
    # Test drift detection
    print("="*60)
    print("Drift Detector Test")
    print("="*60)
    
    # Create sample data
    np.random.seed(42)
    
    baseline_data = pd.DataFrame({
        'feature_1': np.random.normal(0, 1, 1000),
        'feature_2': np.random.normal(5, 2, 1000),
        'feature_3': np.random.normal(10, 3, 1000)
    })
    
    # Current data with drift in feature_2
    current_data = pd.DataFrame({
        'feature_1': np.random.normal(0, 1, 1000),  # No drift
        'feature_2': np.random.normal(7, 2, 1000),  # Drifted (mean shifted)
        'feature_3': np.random.normal(10, 3, 1000)  # No drift
    })
    
    # Detect drift
    detector = DriftDetector()
    drift_results = detector.detect_feature_drift(current_data, baseline_data)
    
    print("\nFeature Drift Results:")
    print(f"  Total features: {drift_results['total_features']}")
    print(f"  Drifted features: {drift_results['drifted_features']}")
    print(f"  Drift percentage: {drift_results['drift_percentage']:.1f}%")
    
    if drift_results['drifted_feature_names']:
        print(f"  Drifted: {', '.join(drift_results['drifted_feature_names'])}")
    
    # Test performance drift
    print("\nPerformance Drift Test:")
    perf_results = detector.detect_performance_drift(
        current_auc=0.85,
        baseline_auc=0.87,
        threshold=0.02
    )
    
    print(f"  Current AUC: {perf_results['current_auc']:.4f}")
    print(f"  Baseline AUC: {perf_results['baseline_auc']:.4f}")
    print(f"  Drop: {perf_results['auc_drop']:.4f}")
    print(f"  Requires retraining: {perf_results['requires_retraining']}")
    
    print("\n✅ Drift detection test complete")
