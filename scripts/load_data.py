"""
VÉLØ v10.1 - Data Loader
=========================

Load Kaggle racing data into SQLite database.
Handles 1.95M records from raceform.csv and recent.csv.

Author: VÉLØ Oracle Team
Version: 10.1.0
"""

import sqlite3
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_database(db_path: str):
    """Create SQLite database with schema."""
    logger.info(f"Creating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create racing_data table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS racing_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            course TEXT,
            race_id TEXT,
            off_time TEXT,
            race_name TEXT,
            type TEXT,
            class TEXT,
            pattern TEXT,
            rating_band TEXT,
            age_band TEXT,
            sex_rest TEXT,
            dist TEXT,
            going TEXT,
            ran INTEGER,
            num REAL,
            pos TEXT,
            draw INTEGER,
            ovr_btn REAL,
            btn REAL,
            horse TEXT,
            age INTEGER,
            sex TEXT,
            wgt TEXT,
            hg TEXT,
            time TEXT,
            sp TEXT,
            jockey TEXT,
            trainer TEXT,
            prize TEXT,
            official_rating TEXT,
            rpr TEXT,
            ts TEXT,
            sire TEXT,
            dam TEXT,
            damsire TEXT,
            owner TEXT,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    logger.info("Creating indexes...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON racing_data(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_course ON racing_data(course)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_race_id ON racing_data(race_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_horse ON racing_data(horse)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jockey ON racing_data(jockey)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trainer ON racing_data(trainer)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_type ON racing_data(type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_date_course ON racing_data(date, course)")
    
    conn.commit()
    conn.close()
    
    logger.info("Database schema created")


def load_csv_to_db(csv_path: str, db_path: str, chunk_size: int = 50000):
    """Load CSV data into database in chunks."""
    logger.info(f"Loading {csv_path}...")
    
    conn = sqlite3.connect(db_path)
    
    # Column mapping (CSV columns to DB columns)
    column_mapping = {
        'date': 'date',
        'course': 'course',
        'race_id': 'race_id',
        'off': 'off_time',
        'race_name': 'race_name',
        'type': 'type',
        'class': 'class',
        'pattern': 'pattern',
        'rating_band': 'rating_band',
        'age_band': 'age_band',
        'sex_rest': 'sex_rest',
        'dist': 'dist',
        'going': 'going',
        'ran': 'ran',
        'num': 'num',
        'pos': 'pos',
        'draw': 'draw',
        'ovr_btn': 'ovr_btn',
        'btn': 'btn',
        'horse': 'horse',
        'age': 'age',
        'sex': 'sex',
        'wgt': 'wgt',
        'hg': 'hg',
        'time': 'time',
        'sp': 'sp',
        'jockey': 'jockey',
        'trainer': 'trainer',
        'prize': 'prize',
        'or': 'official_rating',
        'rpr': 'rpr',
        'ts': 'ts',
        'sire': 'sire',
        'dam': 'dam',
        'damsire': 'damsire',
        'owner': 'owner',
        'comment': 'comment'
    }
    
    # Load in chunks
    total_rows = 0
    chunk_num = 0
    
    for chunk in pd.read_csv(csv_path, chunksize=chunk_size, low_memory=False):
        chunk_num += 1
        
        # Rename columns
        chunk = chunk.rename(columns=column_mapping)
        
        # Select only the columns we need
        db_columns = list(column_mapping.values())
        chunk = chunk[[col for col in db_columns if col in chunk.columns]]
        
        # Write to database
        chunk.to_sql('racing_data', conn, if_exists='append', index=False)
        
        total_rows += len(chunk)
        logger.info(f"  Loaded chunk {chunk_num}: {total_rows:,} rows total")
    
    conn.close()
    logger.info(f"Finished loading {csv_path}: {total_rows:,} rows")
    
    return total_rows


def get_database_stats(db_path: str):
    """Get statistics about the loaded data."""
    logger.info("Computing database statistics...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Total records
    cursor.execute("SELECT COUNT(*) FROM racing_data")
    total_records = cursor.fetchone()[0]
    
    # Date range
    cursor.execute("SELECT MIN(date), MAX(date) FROM racing_data")
    min_date, max_date = cursor.fetchone()
    
    # Unique horses
    cursor.execute("SELECT COUNT(DISTINCT horse) FROM racing_data")
    unique_horses = cursor.fetchone()[0]
    
    # Unique jockeys
    cursor.execute("SELECT COUNT(DISTINCT jockey) FROM racing_data")
    unique_jockeys = cursor.fetchone()[0]
    
    # Unique trainers
    cursor.execute("SELECT COUNT(DISTINCT trainer) FROM racing_data")
    unique_trainers = cursor.fetchone()[0]
    
    # Unique courses
    cursor.execute("SELECT COUNT(DISTINCT course) FROM racing_data")
    unique_courses = cursor.fetchone()[0]
    
    # Race types
    cursor.execute("SELECT type, COUNT(*) FROM racing_data GROUP BY type")
    race_types = cursor.fetchall()
    
    conn.close()
    
    stats = {
        'total_records': total_records,
        'date_range': (min_date, max_date),
        'unique_horses': unique_horses,
        'unique_jockeys': unique_jockeys,
        'unique_trainers': unique_trainers,
        'unique_courses': unique_courses,
        'race_types': race_types
    }
    
    return stats


def main():
    """Main data loading script."""
    logger.info("="*60)
    logger.info("VÉLØ v10.1 - DATA LOADER")
    logger.info("="*60)
    
    # Paths
    project_dir = Path("/home/ubuntu/velo-oracle")
    data_dir = project_dir / "data"
    db_path = project_dir / "velo_racing.db"
    
    raceform_csv = data_dir / "raceform.csv"
    recent_csv = data_dir / "recent.csv"
    
    # Check files exist
    if not raceform_csv.exists():
        logger.error(f"File not found: {raceform_csv}")
        sys.exit(1)
    
    if not recent_csv.exists():
        logger.error(f"File not found: {recent_csv}")
        sys.exit(1)
    
    # Create database
    start_time = datetime.now()
    create_database(str(db_path))
    
    # Load historical data (2015-2023)
    logger.info("\n[1/2] Loading historical data (raceform.csv)...")
    rows_historical = load_csv_to_db(str(raceform_csv), str(db_path))
    
    # Load recent data (2024)
    logger.info("\n[2/2] Loading recent data (recent.csv)...")
    rows_recent = load_csv_to_db(str(recent_csv), str(db_path))
    
    # Get statistics
    logger.info("\n" + "="*60)
    logger.info("DATABASE STATISTICS")
    logger.info("="*60)
    
    stats = get_database_stats(str(db_path))
    
    print(f"\n📊 Total Records: {stats['total_records']:,}")
    print(f"📅 Date Range: {stats['date_range'][0]} to {stats['date_range'][1]}")
    print(f"🐴 Unique Horses: {stats['unique_horses']:,}")
    print(f"🏇 Unique Jockeys: {stats['unique_jockeys']:,}")
    print(f"👔 Unique Trainers: {stats['unique_trainers']:,}")
    print(f"🏟️  Unique Courses: {stats['unique_courses']:,}")
    print(f"\n📈 Race Types:")
    for race_type, count in stats['race_types']:
        print(f"  {race_type}: {count:,}")
    
    # Timing
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print(f"\n⏱️  Load Time: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    print(f"💾 Database: {db_path}")
    print(f"📦 Size: {db_path.stat().st_size / (1024**3):.2f} GB")
    
    logger.info("\n" + "="*60)
    logger.info("✅ DATA LOAD COMPLETE")
    logger.info("="*60)


if __name__ == "__main__":
    main()
