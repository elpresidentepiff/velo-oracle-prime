#!/usr/bin/env python3
"""
VÉLØ Feature Mart Refresh Script
Daily refresh of materialized views for hot window intelligence.

Run via cron/Prefect daily:
0 2 * * * /path/to/refresh_features.py

Author: VELO Team
Date: 2026-01-08
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from workers.ingestion_spine.db import DatabaseClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def refresh_all_features():
    """Refresh all materialized views for feature mart."""

    views = [
        'trainer_stats_14d',
        'trainer_stats_30d',
        'trainer_stats_90d',
        'jockey_stats_14d',
        'jockey_stats_30d',
        'jockey_stats_90d',
        'jt_combo_stats_365d',
        'course_distance_stats_36m'
    ]

    db = None

    try:
        db = DatabaseClient()
        logger.info("Database client initialized")

        # Verify connection
        await db.verify_connection()
        logger.info("Database connection verified")

        start_time = datetime.now()

        for view in views:
            view_start = datetime.now()
            logger.info(f"Refreshing {view}...")

            try:
                # For Supabase, we need to execute raw SQL
                # This requires a custom PostgreSQL function or direct psql connection
                query = f"REFRESH MATERIALIZED VIEW {view}"

                # Note: Supabase Python client doesn't support raw SQL execution directly
                # This would need either:
                # 1. A custom PostgreSQL function called via RPC
                # 2. A direct psycopg2/asyncpg connection
                # 3. Manual execution via Supabase SQL editor
                try:
                    # Try using rpc if exec_sql function exists (must be created in DB)
                    db.client.rpc('exec_sql', {'sql': query}).execute()
                except Exception as rpc_error:
                    logger.warning(
                        f"Cannot refresh {view} via RPC. "
                        f"Please run manually: {query}"
                    )
                    logger.debug(f"RPC Error: {rpc_error}")
                    continue

                view_elapsed = (datetime.now() - view_start).total_seconds()
                logger.info(f"✅ {view} refreshed in {view_elapsed:.2f}s")

            except Exception as e:
                logger.error(f"❌ Failed to refresh {view}: {e}")
                # Continue with other views even if one fails
                continue

        total_elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ All features refreshed in {total_elapsed:.2f}s")

    except Exception as e:
        logger.error(f"❌ Feature refresh failed: {e}")
        raise

    finally:
        if db:
            await db.close()
            logger.info("Database client closed")


async def refresh_single_view(view_name: str):
    """
    Refresh a single materialized view.

    Args:
        view_name: Name of the view to refresh
    """
    db = None

    try:
        db = DatabaseClient()
        logger.info(f"Refreshing {view_name}...")

        query = f"REFRESH MATERIALIZED VIEW {view_name}"
        try:
            db.client.rpc('exec_sql', {'sql': query}).execute()
        except Exception as rpc_error:
            logger.error(
                f"Cannot refresh {view_name} via RPC. "
                f"Please run manually: {query}"
            )
            logger.debug(f"RPC Error: {rpc_error}")
            raise

        logger.info(f"✅ {view_name} refreshed successfully")

    except Exception as e:
        logger.error(f"❌ Failed to refresh {view_name}: {e}")
        raise

    finally:
        if db:
            await db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Refresh VÉLØ feature mart views')
    parser.add_argument(
        '--view',
        type=str,
        help='Refresh a single view (optional)',
        choices=[
            'trainer_stats_14d',
            'trainer_stats_30d',
            'trainer_stats_90d',
            'jockey_stats_14d',
            'jockey_stats_30d',
            'jockey_stats_90d',
            'jt_combo_stats_365d',
            'course_distance_stats_36m'
        ]
    )

    args = parser.parse_args()

    if args.view:
        asyncio.run(refresh_single_view(args.view))
    else:
        asyncio.run(refresh_all_features())
