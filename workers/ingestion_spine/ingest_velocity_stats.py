"""
VÉLØ Velocity Stats Ingestion
Imports trainer, jockey, and horse velocity statistics from CSV files into Supabase
"""
import os
import sys
import argparse
import csv
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from supabase import create_client, Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VelocityStatsIngester:
    """Ingests velocity statistics from CSV files into Supabase"""
    
    def __init__(self):
        """Initialize Supabase client"""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment"
            )
        
        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        logger.info("✓ Connected to Supabase")
    
    def ingest_trainer_stats(self, csv_path: str) -> int:
        """
        Ingest trainer statistics from CSV
        
        Expected CSV format:
        trainer_name,last_14d_record,last_14d_sr,last_14d_pl,overall_record,overall_sr,overall_pl
        
        Args:
            csv_path: Path to trainer CSV file
            
        Returns:
            Number of rows inserted
        """
        logger.info(f"Reading trainer stats from {csv_path}")
        
        records = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append({
                    'trainer_name': row['trainer_name'].strip(),
                    'last_14d_record': row.get('last_14d_record', '').strip(),
                    'last_14d_sr': float(row.get('last_14d_sr', 0) or 0),
                    'last_14d_pl': float(row.get('last_14d_pl', 0) or 0),
                    'overall_record': row.get('overall_record', '').strip(),
                    'overall_sr': float(row.get('overall_sr', 0) or 0),
                    'overall_pl': float(row.get('overall_pl', 0) or 0)
                })
        
        logger.info(f"Parsed {len(records)} trainer records")
        
        # Upsert to Supabase (insert or update if exists)
        if records:
            result = self.client.table('trainer_velocity').upsert(records).execute()
            logger.info(f"✓ Inserted/updated {len(records)} trainer records")
            return len(records)
        
        return 0
    
    def ingest_jockey_stats(self, csv_path: str) -> int:
        """
        Ingest jockey statistics from CSV
        
        Expected CSV format:
        jockey_name,last_14d_record,last_14d_sr,last_14d_pl,overall_record,overall_sr,overall_pl
        
        Args:
            csv_path: Path to jockey CSV file
            
        Returns:
            Number of rows inserted
        """
        logger.info(f"Reading jockey stats from {csv_path}")
        
        records = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append({
                    'jockey_name': row['jockey_name'].strip(),
                    'last_14d_record': row.get('last_14d_record', '').strip(),
                    'last_14d_sr': float(row.get('last_14d_sr', 0) or 0),
                    'last_14d_pl': float(row.get('last_14d_pl', 0) or 0),
                    'overall_record': row.get('overall_record', '').strip(),
                    'overall_sr': float(row.get('overall_sr', 0) or 0),
                    'overall_pl': float(row.get('overall_pl', 0) or 0)
                })
        
        logger.info(f"Parsed {len(records)} jockey records")
        
        # Upsert to Supabase
        if records:
            result = self.client.table('jockey_velocity').upsert(records).execute()
            logger.info(f"✓ Inserted/updated {len(records)} jockey records")
            return len(records)
        
        return 0
    
    def ingest_horse_stats(self, csv_path: str) -> int:
        """
        Ingest horse statistics from CSV
        
        Expected CSV format:
        horse_name,stat_type,record,sr
        
        stat_type examples: course_kempton, distance_2m, going_soft
        
        Args:
            csv_path: Path to horse CSV file
            
        Returns:
            Number of rows inserted
        """
        logger.info(f"Reading horse stats from {csv_path}")
        
        records = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append({
                    'horse_name': row['horse_name'].strip(),
                    'stat_type': row['stat_type'].strip(),
                    'record': row.get('record', '').strip(),
                    'sr': float(row.get('sr', 0) or 0)
                })
        
        logger.info(f"Parsed {len(records)} horse records")
        
        # Upsert to Supabase
        if records:
            result = self.client.table('horse_velocity').upsert(records).execute()
            logger.info(f"✓ Inserted/updated {len(records)} horse records")
            return len(records)
        
        return 0
    
    def clear_table(self, table_name: str) -> None:
        """
        Clear all data from a table (use with caution!)
        
        Args:
            table_name: Name of the table to clear
        """
        logger.warning(f"Clearing all data from {table_name}")
        # Delete all records (Supabase doesn't have a truncate in client library)
        result = self.client.table(table_name).delete().neq('created_at', '1900-01-01').execute()
        logger.info(f"✓ Cleared {table_name}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Ingest velocity statistics into Supabase'
    )
    parser.add_argument(
        '--trainers',
        help='Path to trainers CSV file',
        type=str
    )
    parser.add_argument(
        '--jockeys',
        help='Path to jockeys CSV file',
        type=str
    )
    parser.add_argument(
        '--horses',
        help='Path to horses CSV file',
        type=str
    )
    parser.add_argument(
        '--clear',
        help='Clear tables before ingestion',
        action='store_true'
    )
    
    args = parser.parse_args()
    
    # Validate that at least one file is provided
    if not any([args.trainers, args.jockeys, args.horses]):
        parser.error('At least one CSV file (--trainers, --jockeys, or --horses) must be provided')
    
    try:
        ingester = VelocityStatsIngester()
        
        total_inserted = 0
        
        # Clear tables if requested
        if args.clear:
            if args.trainers:
                ingester.clear_table('trainer_velocity')
            if args.jockeys:
                ingester.clear_table('jockey_velocity')
            if args.horses:
                ingester.clear_table('horse_velocity')
        
        # Ingest trainers
        if args.trainers:
            if not os.path.exists(args.trainers):
                logger.error(f"Trainers file not found: {args.trainers}")
            else:
                total_inserted += ingester.ingest_trainer_stats(args.trainers)
        
        # Ingest jockeys
        if args.jockeys:
            if not os.path.exists(args.jockeys):
                logger.error(f"Jockeys file not found: {args.jockeys}")
            else:
                total_inserted += ingester.ingest_jockey_stats(args.jockeys)
        
        # Ingest horses
        if args.horses:
            if not os.path.exists(args.horses):
                logger.error(f"Horses file not found: {args.horses}")
            else:
                total_inserted += ingester.ingest_horse_stats(args.horses)
        
        logger.info(f"\n✅ Ingestion complete! Total records: {total_inserted}")
        
    except Exception as e:
        logger.error(f"❌ Ingestion failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
