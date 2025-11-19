#!/usr/bin/env python3
"""
VÉLØ Oracle - Auto Compare
Compare last 5 model versions and select best
"""
import sys
import os
from pathlib import Path
import logging
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_model_versions(model_name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Load last N versions of a model"""
    
    # Stub: Would load from model registry
    versions = [
        {
            "version": "v13.1",
            "auc": 0.831,
            "accuracy": 0.742,
            "log_loss": 0.512,
            "calibration_error": 0.045,
            "stability": 0.89
        },
        {
            "version": "v13.0",
            "auc": 0.828,
            "accuracy": 0.738,
            "log_loss": 0.518,
            "calibration_error": 0.048,
            "stability": 0.87
        },
        {
            "version": "v12.9",
            "auc": 0.825,
            "accuracy": 0.735,
            "log_loss": 0.522,
            "calibration_error": 0.051,
            "stability": 0.85
        },
        {
            "version": "v12.8",
            "auc": 0.822,
            "accuracy": 0.732,
            "log_loss": 0.528,
            "calibration_error": 0.053,
            "stability": 0.83
        },
        {
            "version": "v12.7",
            "auc": 0.819,
            "accuracy": 0.729,
            "log_loss": 0.535,
            "calibration_error": 0.056,
            "stability": 0.81
        }
    ]
    
    return versions[:limit]


def compare_on_dataset(versions: List[Dict], dataset_path: str = "data/test.parquet") -> Dict[str, Any]:
    """Run comparison on same dataset"""
    
    logger.info(f"Running comparison on dataset: {dataset_path}")
    logger.info(f"Comparing {len(versions)} versions...")
    
    # Stub: Would run actual comparison
    # For now, return metrics from versions
    
    comparison = {
        "dataset": dataset_path,
        "versions_compared": len(versions),
        "results": versions
    }
    
    return comparison


def calculate_stability_metrics(versions: List[Dict]) -> Dict[str, float]:
    """Calculate stability metrics across versions"""
    
    if len(versions) < 2:
        return {"stability_score": 0.0, "variance": 0.0}
    
    # Calculate AUC variance
    aucs = [v["auc"] for v in versions]
    auc_variance = sum((x - sum(aucs)/len(aucs))**2 for x in aucs) / len(aucs)
    
    # Stability score (lower variance = higher stability)
    stability_score = max(0.0, 1.0 - (auc_variance * 10))
    
    return {
        "stability_score": stability_score,
        "auc_variance": auc_variance,
        "auc_trend": "improving" if aucs[0] > aucs[-1] else "declining"
    }


def calculate_calibration_error(version: Dict) -> float:
    """Calculate calibration error for a version"""
    return version.get("calibration_error", 0.05)


def select_best_model(versions: List[Dict], stability_metrics: Dict) -> Dict[str, Any]:
    """Select best model based on multiple criteria"""
    
    # Scoring weights
    weights = {
        "auc": 0.40,
        "calibration": 0.30,
        "stability": 0.30
    }
    
    best_version = None
    best_score = -1
    
    for version in versions:
        # Normalize metrics to 0-1
        auc_score = version["auc"]  # Already 0-1
        calibration_score = 1.0 - version["calibration_error"]  # Lower is better
        stability_score = version["stability"]  # Already 0-1
        
        # Weighted score
        score = (
            auc_score * weights["auc"] +
            calibration_score * weights["calibration"] +
            stability_score * weights["stability"]
        )
        
        if score > best_score:
            best_score = score
            best_version = version
    
    return {
        "best_version": best_version["version"],
        "score": best_score,
        "metrics": best_version,
        "reasons": [
            f"AUC: {best_version['auc']:.3f}",
            f"Calibration Error: {best_version['calibration_error']:.3f}",
            f"Stability: {best_version['stability']:.3f}"
        ]
    }


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Compare model versions")
    parser.add_argument(
        "--model",
        default="sqpe",
        help="Model name to compare"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of versions to compare"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info(f"VÉLØ Oracle - Model Comparison: {args.model.upper()}")
    logger.info("=" * 60)
    
    # Load versions
    logger.info(f"Loading last {args.limit} versions...")
    versions = load_model_versions(args.model, args.limit)
    
    logger.info(f"Loaded {len(versions)} versions")
    
    # Run comparison
    comparison = compare_on_dataset(versions)
    
    # Calculate stability
    stability_metrics = calculate_stability_metrics(versions)
    
    logger.info("\nSTABILITY METRICS:")
    logger.info(f"  Stability Score: {stability_metrics['stability_score']:.3f}")
    logger.info(f"  AUC Variance: {stability_metrics['auc_variance']:.6f}")
    logger.info(f"  Trend: {stability_metrics['auc_trend']}")
    
    # Select best model
    best = select_best_model(versions, stability_metrics)
    
    logger.info("\n" + "=" * 60)
    logger.info("BEST MODEL SELECTED")
    logger.info("=" * 60)
    logger.info(f"Version: {best['best_version']}")
    logger.info(f"Overall Score: {best['score']:.3f}")
    logger.info("\nReasons:")
    for reason in best['reasons']:
        logger.info(f"  - {reason}")
    
    logger.info("\n" + "=" * 60)
    logger.info("ALL VERSIONS COMPARISON")
    logger.info("=" * 60)
    
    for i, version in enumerate(versions, 1):
        logger.info(f"\n{i}. {version['version']}")
        logger.info(f"   AUC: {version['auc']:.3f}")
        logger.info(f"   Accuracy: {version['accuracy']:.3f}")
        logger.info(f"   Log Loss: {version['log_loss']:.3f}")
        logger.info(f"   Calibration Error: {version['calibration_error']:.3f}")
        logger.info(f"   Stability: {version['stability']:.3f}")
    
    logger.info("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
