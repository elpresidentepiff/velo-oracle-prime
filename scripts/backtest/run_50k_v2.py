#!/usr/bin/env python3
"""
VÉLØ Oracle - Run 50K Backtest V2
CLI script to run enhanced 50K sample backtest
"""
import sys
import os
from pathlib import Path
import argparse
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.services.backtest.backtest_50k_v2 import run_backtest_50k_v2
from src.data.supabase_client import get_supabase_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run VÉLØ Oracle 50K Backtest V2"
    )
    parser.add_argument(
        "--dataset",
        default="data/train_1_7m.parquet",
        help="Path to training dataset"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=50_000,
        help="Number of samples to test"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=2025,
        help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--log-to-supabase",
        action="store_true",
        help="Log results to Supabase"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("VÉLØ Oracle - 50K Backtest V2")
    logger.info("=" * 60)
    logger.info(f"Dataset: {args.dataset}")
    logger.info(f"Sample Size: {args.sample_size:,}")
    logger.info(f"Seed: {args.seed}")
    logger.info("=" * 60)
    
    # Run backtest
    result = run_backtest_50k_v2(
        dataset_path=args.dataset,
        sample_size=args.sample_size,
        seed=args.seed,
        date_range=None
    )
    
    # Display results
    logger.info("\n" + "=" * 60)
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 60)
    logger.info(f"Backtest ID: {result['backtest_id']}")
    logger.info(f"Version: {result['version']}")
    logger.info(f"Status: {result['status']}")
    logger.info(f"Sample Size: {result.get('sample_size', 0):,}")
    
    if result['status'] == 'complete':
        metrics = result['metrics']
        logger.info("\nMETRICS:")
        logger.info(f"  ROI: {metrics['roi']:.2%}")
        logger.info(f"  Win Rate: {metrics['win_rate']:.2%}")
        logger.info(f"  AUC: {metrics['auc']:.3f}")
        logger.info(f"  Log Loss: {metrics['log_loss']:.3f}")
        logger.info(f"  Max Drawdown: {metrics['mdd']:.2%}")
        logger.info(f"  Number of Bets: {metrics['num_bets']:,}")
        
        # Log to Supabase if requested
        if args.log_to_supabase:
            try:
                logger.info("\nLogging to Supabase...")
                db = get_supabase_client()
                success = db.log_backtest_summary(
                    backtest_id=result['backtest_id'],
                    version=result['version'],
                    sample_size=result['sample_size'],
                    metrics=metrics,
                    config=result['config'],
                    status=result['status']
                )
                
                if success:
                    logger.info("✅ Results logged to Supabase")
                else:
                    logger.warning("⚠️ Failed to log to Supabase")
                    
            except Exception as e:
                logger.warning(f"⚠️ Supabase logging failed: {e}")
    else:
        logger.error(f"\n❌ Backtest failed: {result.get('error', 'Unknown error')}")
    
    logger.info("=" * 60)
    
    return 0 if result['status'] == 'complete' else 1


if __name__ == "__main__":
    sys.exit(main())
