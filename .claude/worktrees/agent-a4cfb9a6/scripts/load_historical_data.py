"""
VÉLØ v10.1 - Historical Data Loader
Load and preprocess 1.7M races from raceform.csv

This script:
1. Loads raceform.csv in chunks (memory efficient)
2. Cleans and validates data
3. Parses odds, ratings, positions
4. Saves to PostgreSQL database
5. Creates indexes for fast querying
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from datetime import datetime
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.settings import settings
from src.core import log
import logging

# Setup logging
log.setup_logging("config/logging.json")
logger = logging.getLogger("velo.data_loader")


def parse_odds(sp_str):
    """
    Parse starting price string to decimal odds
    
    Examples:
        "1/3F" -> 1.33
        "5/2" -> 3.5
        "10/1" -> 11.0
        "Evens" -> 2.0
    """
    if pd.isna(sp_str) or sp_str == '–':
        return None
    
    sp_str = str(sp_str).strip()
    
    # Remove 'F' (favorite marker)
    sp_str = sp_str.replace('F', '').strip()
    
    # Handle special cases
    if sp_str.lower() == 'evens':
        return 2.0
    
    # Parse fraction
    if '/' in sp_str:
        try:
            parts = sp_str.split('/')
            numerator = float(parts[0])
            denominator = float(parts[1])
            # Convert fractional to decimal
            return (numerator / denominator) + 1.0
        except:
            return None
    
    # Try parsing as decimal
    try:
        return float(sp_str)
    except:
        return None


def parse_rating(rating_str):
    """
    Parse rating string to integer
    
    Handles: "123", "–", NaN
    """
    if pd.isna(rating_str) or rating_str == '–':
        return None
    
    try:
        return int(rating_str)
    except:
        return None


def parse_position(pos_str):
    """
    Parse position string to integer
    
    Handles: "1", "2", "PU" (pulled up), "F" (fell), etc.
    """
    if pd.isna(pos_str):
        return None
    
    pos_str = str(pos_str).strip()
    
    # Non-finishers
    if pos_str in ['PU', 'F', 'U', 'BD', 'RO', 'UR', 'SU']:
        return None
    
    try:
        return int(float(pos_str))
    except:
        return None


def clean_dataframe(df):
    """
    Clean and preprocess dataframe
    
    - Parse dates
    - Parse odds to decimal
    - Parse ratings to integers
    - Parse positions
    - Handle missing values
    """
    logger.info(f"Cleaning {len(df)} rows...")
    
    # Parse dates
    df['date'] = pd.to_datetime(df['date'])
    
    # Parse odds
    df['sp_decimal'] = df['sp'].apply(parse_odds)
    
    # Parse ratings
    df['or_int'] = df['or'].apply(parse_rating)
    df['rpr_int'] = df['rpr'].apply(parse_rating)
    df['ts_int'] = df['ts'].apply(parse_rating)
    
    # Parse position
    df['pos_int'] = df['pos'].apply(parse_position)
    
    # Add winner flag
    df['is_winner'] = (df['pos_int'] == 1).astype(int)
    
    # Extract year, month for partitioning
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    
    # Filter UK races only (optional - keep all for now)
    # uk_courses = df['course'].str.contains('(IRE)|(FR)|(USA)|(UAE)', na=False)
    # df = df[~uk_courses]
    
    logger.info(f"✅ Cleaned {len(df)} rows")
    
    return df


def load_data_chunked(filepath, chunksize=50000):
    """
    Load raceform.csv in chunks and yield cleaned dataframes
    
    Args:
        filepath: Path to raceform.csv
        chunksize: Rows per chunk
    
    Yields:
        Cleaned dataframes
    """
    logger.info(f"Loading data from {filepath} (chunks of {chunksize})...")
    
    total_rows = 0
    
    for i, chunk in enumerate(pd.read_csv(filepath, chunksize=chunksize, low_memory=False)):
        logger.info(f"Processing chunk {i+1} ({len(chunk)} rows)...")
        
        # Clean chunk
        chunk_clean = clean_dataframe(chunk)
        
        total_rows += len(chunk_clean)
        
        yield chunk_clean
    
    logger.info(f"✅ Loaded {total_rows} total rows")


def create_database_tables(engine):
    """
    Create database tables if they don't exist
    """
    logger.info("Creating database tables...")
    
    # We'll use pandas to_sql with if_exists='append'
    # Tables will be created automatically
    
    logger.info("✅ Database ready")


def load_to_database(filepath, table_name='historical_races', chunksize=50000):
    """
    Load raceform.csv to PostgreSQL database
    
    Args:
        filepath: Path to raceform.csv
        table_name: Database table name
        chunksize: Rows per chunk
    """
    with log.EventLogger("load_historical_data", filepath=filepath):
        # Create database engine
        engine = create_engine(settings.db_url)
        
        logger.info(f"Connected to database: {settings.DB_NAME}")
        
        # Create tables
        create_database_tables(engine)
        
        # Load data in chunks
        total_loaded = 0
        
        for i, chunk in enumerate(load_data_chunked(filepath, chunksize)):
            # Save to database
            chunk.to_sql(
                table_name,
                engine,
                if_exists='append',
                index=False,
                method='multi'
            )
            
            total_loaded += len(chunk)
            
            logger.info(f"✅ Loaded chunk {i+1} ({total_loaded} total rows)")
        
        logger.info(f"🎉 Successfully loaded {total_loaded} rows to {table_name}")
        
        # Create indexes
        logger.info("Creating indexes...")
        
        with engine.connect() as conn:
            # Index on date for time-based queries
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_date ON {table_name} (date)")
            
            # Index on course for course-specific queries
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_course ON {table_name} (course)")
            
            # Index on horse for horse history
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_horse ON {table_name} (horse)")
            
            # Index on jockey for jockey stats
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_jockey ON {table_name} (jockey)")
            
            # Index on trainer for trainer stats
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_trainer ON {table_name} (trainer)")
            
            # Composite index for race lookups
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_race ON {table_name} (date, course, race_id)")
            
            conn.commit()
        
        logger.info("✅ Indexes created")
        
        return total_loaded


def main():
    """
    Main entry point
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Load historical racing data')
    parser.add_argument('--filepath', default='/home/ubuntu/upload/raceform.csv', help='Path to raceform.csv')
    parser.add_argument('--table', default='historical_races', help='Database table name')
    parser.add_argument('--chunksize', type=int, default=50000, help='Rows per chunk')
    parser.add_argument('--dry-run', action='store_true', help='Test without loading to database')
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("DRY RUN MODE - Testing data loading...")
        
        # Load first chunk only
        for i, chunk in enumerate(load_data_chunked(args.filepath, args.chunksize)):
            logger.info(f"Chunk {i+1} shape: {chunk.shape}")
            logger.info(f"Columns: {list(chunk.columns)}")
            logger.info(f"Sample data:\n{chunk.head()}")
            
            if i >= 0:  # Just first chunk
                break
        
        logger.info("✅ Dry run complete")
    else:
        # Load to database
        total = load_to_database(args.filepath, args.table, args.chunksize)
        
        logger.info(f"🎉 COMPLETE: {total} races loaded to database")


if __name__ == "__main__":
    main()

