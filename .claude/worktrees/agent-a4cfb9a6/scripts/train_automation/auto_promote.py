#!/usr/bin/env python3
"""
VÉLØ Oracle - Auto Promote
Automatically promote model to production if criteria met
"""
import sys
import os
from pathlib import Path
import logging
from datetime import datetime
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Promotion criteria thresholds
PROMOTION_CRITERIA = {
    "auc_improvement": 0.005,  # Must improve by at least 0.5%
    "calibration_improvement": 0.01,  # Must improve by 1%
    "max_volatility": 0.15,  # Volatility must be below 15%
    "max_risk_score": 30,  # Risk score must be below 30
    "min_stability": 0.75  # Stability must be above 75%
}


def get_current_production(model_name: str) -> Dict[str, Any]:
    """Get current production model version"""
    
    # Stub: Would fetch from model registry
    return {
        "version": "v13.0",
        "auc": 0.828,
        "calibration_error": 0.048,
        "volatility": 0.12,
        "risk_score": 25,
        "stability": 0.87
    }


def get_candidate_model(model_name: str, version: str) -> Dict[str, Any]:
    """Get candidate model for promotion"""
    
    # Stub: Would fetch from model registry
    return {
        "version": version,
        "auc": 0.831,
        "calibration_error": 0.045,
        "volatility": 0.10,
        "risk_score": 22,
        "stability": 0.89
    }


def check_promotion_criteria(
    current: Dict[str, Any],
    candidate: Dict[str, Any]
) -> Dict[str, Any]:
    """Check if candidate meets promotion criteria"""
    
    checks = {}
    
    # 1. AUC improved
    auc_improvement = candidate["auc"] - current["auc"]
    checks["auc_improved"] = auc_improvement >= PROMOTION_CRITERIA["auc_improvement"]
    checks["auc_improvement"] = auc_improvement
    
    # 2. Calibration improved
    calibration_improvement = current["calibration_error"] - candidate["calibration_error"]
    checks["calibration_improved"] = calibration_improvement >= PROMOTION_CRITERIA["calibration_improvement"]
    checks["calibration_improvement"] = calibration_improvement
    
    # 3. Volatility tolerance met
    checks["volatility_ok"] = candidate["volatility"] <= PROMOTION_CRITERIA["max_volatility"]
    checks["volatility"] = candidate["volatility"]
    
    # 4. Risk score below threshold
    checks["risk_ok"] = candidate["risk_score"] <= PROMOTION_CRITERIA["max_risk_score"]
    checks["risk_score"] = candidate["risk_score"]
    
    # 5. Stability above threshold
    checks["stability_ok"] = candidate["stability"] >= PROMOTION_CRITERIA["min_stability"]
    checks["stability"] = candidate["stability"]
    
    # All checks must pass
    checks["all_passed"] = all([
        checks["auc_improved"],
        checks["calibration_improved"],
        checks["volatility_ok"],
        checks["risk_ok"],
        checks["stability_ok"]
    ])
    
    return checks


def promote_to_production(model_name: str, version: str) -> bool:
    """Promote model version to production"""
    
    try:
        from app.ml.model_ops import promote_model_version
        
        success = promote_model_version(model_name, version, to_status="production")
        
        if success:
            logger.info(f"✅ Model promoted: {model_name} {version} -> production")
        else:
            logger.error(f"❌ Failed to promote model")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Promotion error: {e}")
        return False


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Auto-promote model to production")
    parser.add_argument(
        "--model",
        required=True,
        help="Model name"
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Version to promote"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force promotion without checks"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info(f"VÉLØ Oracle - Auto Promote: {args.model.upper()}")
    logger.info(f"Candidate Version: {args.version}")
    logger.info("=" * 60)
    
    # Get current production
    logger.info("\nFetching current production model...")
    current = get_current_production(args.model)
    logger.info(f"Current Production: {current['version']}")
    logger.info(f"  AUC: {current['auc']:.3f}")
    logger.info(f"  Calibration Error: {current['calibration_error']:.3f}")
    
    # Get candidate
    logger.info(f"\nFetching candidate model...")
    candidate = get_candidate_model(args.model, args.version)
    logger.info(f"Candidate: {candidate['version']}")
    logger.info(f"  AUC: {candidate['auc']:.3f}")
    logger.info(f"  Calibration Error: {candidate['calibration_error']:.3f}")
    
    # Check criteria
    if not args.force:
        logger.info("\n" + "=" * 60)
        logger.info("PROMOTION CRITERIA CHECKS")
        logger.info("=" * 60)
        
        checks = check_promotion_criteria(current, candidate)
        
        logger.info(f"\n1. AUC Improved: {'✅' if checks['auc_improved'] else '❌'}")
        logger.info(f"   Improvement: {checks['auc_improvement']:+.4f}")
        logger.info(f"   Required: {PROMOTION_CRITERIA['auc_improvement']:.4f}")
        
        logger.info(f"\n2. Calibration Improved: {'✅' if checks['calibration_improved'] else '❌'}")
        logger.info(f"   Improvement: {checks['calibration_improvement']:+.4f}")
        logger.info(f"   Required: {PROMOTION_CRITERIA['calibration_improvement']:.4f}")
        
        logger.info(f"\n3. Volatility Tolerance: {'✅' if checks['volatility_ok'] else '❌'}")
        logger.info(f"   Volatility: {checks['volatility']:.3f}")
        logger.info(f"   Max Allowed: {PROMOTION_CRITERIA['max_volatility']:.3f}")
        
        logger.info(f"\n4. Risk Score: {'✅' if checks['risk_ok'] else '❌'}")
        logger.info(f"   Score: {checks['risk_score']}")
        logger.info(f"   Max Allowed: {PROMOTION_CRITERIA['max_risk_score']}")
        
        logger.info(f"\n5. Stability: {'✅' if checks['stability_ok'] else '❌'}")
        logger.info(f"   Stability: {checks['stability']:.3f}")
        logger.info(f"   Min Required: {PROMOTION_CRITERIA['min_stability']:.3f}")
        
        logger.info("\n" + "=" * 60)
        
        if checks["all_passed"]:
            logger.info("✅ ALL CRITERIA PASSED")
            logger.info("=" * 60)
            
            # Promote
            logger.info(f"\nPromoting {args.model} {args.version} to production...")
            success = promote_to_production(args.model, args.version)
            
            if success:
                logger.info("\n✅ PROMOTION SUCCESSFUL")
                logger.info(f"{args.model} {args.version} is now in production")
                return 0
            else:
                logger.error("\n❌ PROMOTION FAILED")
                return 1
        else:
            logger.error("❌ CRITERIA NOT MET - Promotion blocked")
            logger.info("=" * 60)
            return 1
    else:
        logger.warning("\n⚠️ FORCE MODE - Skipping criteria checks")
        logger.info(f"\nPromoting {args.model} {args.version} to production...")
        success = promote_to_production(args.model, args.version)
        
        if success:
            logger.info("\n✅ PROMOTION SUCCESSFUL (FORCED)")
            return 0
        else:
            logger.error("\n❌ PROMOTION FAILED")
            return 1


if __name__ == "__main__":
    sys.exit(main())
