#!/usr/bin/env python3
"""
VÉLØ Oracle - Daily Monitoring Script
Run daily to check for drift and performance issues
"""
import sys
sys.path.insert(0, '/home/ubuntu/velo-oracle-storage')

from app.monitoring.drift_detector import DriftDetector
from app.monitoring.performance_tracker import PerformanceTracker
import pandas as pd
import json
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_daily_monitor():
    """Run daily monitoring checks"""
    
    logger.info("="*60)
    logger.info("VÉLØ Oracle - Daily Monitoring")
    logger.info(f"Date: {datetime.utcnow().date()}")
    logger.info("="*60)
    
    # 1. Load recent data
    logger.info("\n1. Loading recent data...")
    try:
        recent_data = pd.read_csv(
            "storage/velo-datasets/racing_full_1_7m.csv",
            nrows=10000
        )
        logger.info(f"✅ Loaded {len(recent_data):,} recent samples")
    except Exception as e:
        logger.error(f"❌ Failed to load data: {e}")
        return
    
    # 2. Check feature drift
    logger.info("\n2. Checking feature drift...")
    detector = DriftDetector()
    
    drift_results = detector.detect_feature_drift(
        current_data=recent_data,
        threshold=0.05
    )
    
    drift_alert = drift_results['drift_percentage'] > 20
    
    if drift_alert:
        logger.warning(f"⚠️  HIGH DRIFT ALERT: {drift_results['drift_percentage']:.1f}% of features drifted")
    else:
        logger.info(f"✅ Drift within acceptable range: {drift_results['drift_percentage']:.1f}%")
    
    # 3. Check performance
    logger.info("\n3. Checking model performance...")
    tracker = PerformanceTracker()
    
    # Get latest metrics
    latest = tracker.get_latest_metrics('sqpe_v14')
    
    if latest:
        current_auc = latest['metrics'].get('auc', 0.87)
        baseline_auc = 0.87
        
        perf_results = detector.detect_performance_drift(
            current_auc=current_auc,
            baseline_auc=baseline_auc,
            threshold=0.02
        )
        
        if perf_results['requires_retraining']:
            logger.warning("⚠️  RETRAINING REQUIRED")
        else:
            logger.info("✅ Performance stable")
    else:
        logger.info("No performance history available")
    
    # 4. Generate report
    logger.info("\n4. Generating monitoring report...")
    
    report = {
        'timestamp': datetime.utcnow().isoformat(),
        'drift': drift_results,
        'performance': perf_results if latest else {},
        'alerts': {
            'high_drift': drift_alert,
            'requires_retraining': perf_results.get('requires_retraining', False) if latest else False
        },
        'recommendations': []
    }
    
    if drift_alert:
        report['recommendations'].append("Investigate drifted features")
        report['recommendations'].append("Consider feature re-engineering")
    
    if report['alerts']['requires_retraining']:
        report['recommendations'].append("Schedule model retraining")
        report['recommendations'].append("Review recent data quality")
    
    # Save report
    report_path = f"logs/monitoring_report_{datetime.utcnow().date()}.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"✅ Report saved to {report_path}")
    
    # 5. Summary
    logger.info("\n" + "="*60)
    logger.info("MONITORING SUMMARY")
    logger.info("="*60)
    logger.info(f"Drift: {drift_results['drift_percentage']:.1f}% ({drift_results['drifted_features']} features)")
    if latest:
        logger.info(f"Performance: AUC {current_auc:.4f}")
    logger.info(f"Alerts: {sum(report['alerts'].values())}")
    logger.info(f"Recommendations: {len(report['recommendations'])}")
    logger.info("="*60)
    
    return report


if __name__ == "__main__":
    report = run_daily_monitor()
    
    if report and report['alerts']['requires_retraining']:
        print("\n🔄 ACTION REQUIRED: Model retraining recommended")
        sys.exit(1)
    else:
        print("\n✅ All systems nominal")
        sys.exit(0)
