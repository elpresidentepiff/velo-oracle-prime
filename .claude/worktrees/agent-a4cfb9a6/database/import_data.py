#!/usr/bin/env python3.11
"""
VÉLØ Data Import Script
Imports UK racing data from CSV files into PostgreSQL
"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
import sys
from datetime import datetime

# Database connection
DB_CONFIG = {
    'dbname': 'velo_racing',
    'user': 'postgres'
}

def connect_db():
    """Connect to PostgreSQL database"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

def import_csv_batch(csv_file, conn, batch_size=10000):
    """Import CSV file in batches"""
    print(f"\n{'='*60}")
    print(f"Importing: {csv_file}")
    print(f"{'='*60}")
    
    # Read CSV in chunks
    chunk_iter = pd.read_csv(csv_file, chunksize=batch_size, low_memory=False)
    
    total_rows = 0
    batch_num = 0
    
    cursor = conn.cursor()
    
    for chunk in chunk_iter:
        batch_num += 1
        rows_in_batch = len(chunk)
        
        # Prepare data for insertion
        data = []
        for _, row in chunk.iterrows():
            # Helper function to convert to numeric or None
            def to_num(val):
                if pd.isna(val) or val == '-' or val == '–' or val == '':
                    return None
                try:
                    return float(val)
                except:
                    return None
            
            # Helper function to convert to int or None
            def to_int(val):
                if pd.isna(val) or val == '-' or val == '–' or val == '':
                    return None
                try:
                    return int(float(val))
                except:
                    return None
            
            data.append((
                row['date'],
                row['course'],
                row['race_id'],
                row['off'],
                row['race_name'],
                row['type'],
                row['class'],
                row['pattern'],
                row['rating_band'],
                row['age_band'],
                row['sex_rest'],
                row['dist'],
                row['going'],
                to_int(row['ran']),
                to_num(row['num']),
                str(row['pos']) if pd.notna(row['pos']) and row['pos'] != '-' else None,
                to_int(row['draw']),
                to_num(row['ovr_btn']),
                to_num(row['btn']),
                row['horse'],
                to_int(row['age']),
                row['sex'] if pd.notna(row['sex']) and row['sex'] != '-' else None,
                row['wgt'],
                row['hg'],
                row['time'],
                row['sp'],
                row['jockey'],
                row['trainer'],
                str(row['prize']) if pd.notna(row['prize']) else None,
                str(row['or']) if pd.notna(row['or']) and row['or'] != '–' else None,
                str(row['rpr']) if pd.notna(row['rpr']) and row['rpr'] != '–' else None,
                str(row['ts']) if pd.notna(row['ts']) and row['ts'] != '–' else None,
                row['sire'],
                row['dam'],
                row['damsire'],
                row['owner'],
                row['comment']
            ))
        
        # Insert batch
        insert_query = """
            INSERT INTO racing_data (
                date, course, race_id, off_time, race_name, type, class, pattern,
                rating_band, age_band, sex_rest, dist, going, ran, num, pos, draw,
                ovr_btn, btn, horse, age, sex, wgt, hg, time, sp, jockey, trainer,
                prize, official_rating, rpr, ts, sire, dam, damsire, owner, comment
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s
            )
        """
        
        try:
            execute_batch(cursor, insert_query, data, page_size=1000)
            conn.commit()
            total_rows += rows_in_batch
            print(f"Batch {batch_num}: {rows_in_batch:,} rows | Total: {total_rows:,} rows")
        except Exception as e:
            print(f"Error in batch {batch_num}: {e}")
            conn.rollback()
            continue
    
    cursor.close()
    print(f"\n✅ Import complete: {total_rows:,} total rows imported")
    return total_rows

def get_table_stats(conn):
    """Get statistics about imported data"""
    cursor = conn.cursor()
    
    print(f"\n{'='*60}")
    print("DATABASE STATISTICS")
    print(f"{'='*60}")
    
    # Total rows
    cursor.execute("SELECT COUNT(*) FROM racing_data")
    total = cursor.fetchone()[0]
    print(f"Total rows: {total:,}")
    
    # Date range
    cursor.execute("SELECT MIN(date), MAX(date) FROM racing_data")
    min_date, max_date = cursor.fetchone()
    print(f"Date range: {min_date} to {max_date}")
    
    # Unique counts
    cursor.execute("SELECT COUNT(DISTINCT race_id) FROM racing_data")
    races = cursor.fetchone()[0]
    print(f"Unique races: {races:,}")
    
    cursor.execute("SELECT COUNT(DISTINCT horse) FROM racing_data")
    horses = cursor.fetchone()[0]
    print(f"Unique horses: {horses:,}")
    
    cursor.execute("SELECT COUNT(DISTINCT jockey) FROM racing_data WHERE jockey IS NOT NULL")
    jockeys = cursor.fetchone()[0]
    print(f"Unique jockeys: {jockeys:,}")
    
    cursor.execute("SELECT COUNT(DISTINCT trainer) FROM racing_data WHERE trainer IS NOT NULL")
    trainers = cursor.fetchone()[0]
    print(f"Unique trainers: {trainers:,}")
    
    cursor.execute("SELECT COUNT(DISTINCT course) FROM racing_data")
    courses = cursor.fetchone()[0]
    print(f"Unique courses: {courses:,}")
    
    # Type breakdown
    print(f"\n{'='*60}")
    print("RACE TYPE BREAKDOWN")
    print(f"{'='*60}")
    cursor.execute("""
        SELECT type, COUNT(*) as count 
        FROM racing_data 
        WHERE type IS NOT NULL 
        GROUP BY type 
        ORDER BY count DESC
    """)
    for row in cursor.fetchall():
        print(f"{row[0]}: {row[1]:,}")
    
    cursor.close()

def main():
    """Main import function"""
    print("\n🔮 VÉLØ DATA IMPORT SYSTEM")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Connect to database
    conn = connect_db()
    print("✅ Connected to database")
    
    # Import files
    csv_files = [
        '/home/ubuntu/upload/raceform.csv',
        '/home/ubuntu/upload/recent.csv'
    ]
    
    total_imported = 0
    for csv_file in csv_files:
        try:
            rows = import_csv_batch(csv_file, conn, batch_size=10000)
            total_imported += rows
        except Exception as e:
            print(f"Error importing {csv_file}: {e}")
            continue
    
    # Get statistics
    get_table_stats(conn)
    
    # Close connection
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"✅ IMPORT COMPLETE")
    print(f"Total rows imported: {total_imported:,}")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()

