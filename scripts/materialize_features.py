"""
Materialize features from offline to online store
"""
import sys
sys.path.insert(0, '/home/ubuntu/velo-oracle')

from datetime import datetime, timedelta
from pathlib import Path
from feast import FeatureStore
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logger.info("="*60)
    logger.info("VÉLØ Oracle - Materialize Features")
    logger.info("="*60)
    
    # Initialize Feast
    repo_path = Path("/home/ubuntu/velo-oracle/feast_repo")
    logger.info(f"Initializing Feast from: {repo_path}")
    
    store = FeatureStore(repo_path=str(repo_path))
    
    # Materialize last 90 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    logger.info(f"\nMaterializing features...")
    logger.info(f"  Start: {start_date}")
    logger.info(f"  End: {end_date}")
    
    try:
        store.materialize(
            start_date=start_date,
            end_date=end_date
        )
        
        logger.info("\n✓ Features materialized successfully!")
        logger.info("  Online store is ready for low-latency serving")
        
    except Exception as e:
        logger.error(f"Materialization failed: {e}")
        raise


if __name__ == "__main__":
    main()
