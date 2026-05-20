import os
import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv(Path(__file__).parent.parent / '.env')

def get_conn():
    dsn = os.getenv('DATABASE_URL') or os.getenv('SUPABASE_DB_URL')
    if not dsn:
        pytest.skip("No database connection string found")
    return psycopg2.connect(dsn)

REQUIRED_CONTRACT = {
    'market_deception_score': 'double precision',
    'improvement_score': 'double precision',
    'trainer_score': 'double precision',
    'jockey_score': 'double precision',
    'course_score': 'double precision',
    'distance_score': 'double precision',
    'pace_profile': 'jsonb',
    'field_strength': 'double precision',
    'market_pressure': 'double precision',
    'pre_race_odds_dec': 'double precision',
    'odds_timestamp': 'timestamp with time zone',
    'odds_source': 'text',
    'prediction_timestamp': 'timestamp with time zone',
    'feature_status': 'text',
    'feature_quality': 'text',
    'feature_provenance': 'jsonb',
    'training_safe': 'boolean',
    'leakage_status': 'text',
    'batch_id': 'text',
    'audit_id': 'text',
    'reconstruction_version': 'text'
}

REQUIRED_INDEXES = [
    'ix_hfs_batch_id',
    'ix_hfs_audit_id',
    'ix_hfs_reconstruction_version',
    'ix_hfs_training_safe',
    'ix_hfs_leakage_status'
]

def test_hfs_schema_contract():
    """
    Verifies that the historical_feature_store table contains all 
    required doctrine and provenance columns with the correct data types.
    Filters specifically for the 'public' schema to avoid false positives.
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Verify Columns and Types
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'public'
                  AND table_name = 'historical_feature_store'
            """)
            actual_schema = {row['column_name']: row['data_type'] for row in cur.fetchall()}
            
            if not actual_schema:
                pytest.fail("historical_feature_store table not found in public schema")

            for col, expected_type in REQUIRED_CONTRACT.items():
                assert col in actual_schema, f"Missing required column: {col}"
                assert actual_schema[col] == expected_type, f"Type mismatch for {col}: expected {expected_type}, got {actual_schema[col]}"
            
            # 2. Verify Indexes
            cur.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE schemaname = 'public'
                  AND tablename = 'historical_feature_store'
            """)
            actual_indexes = {row['indexname'] for row in cur.fetchall()}
            
            for idx in REQUIRED_INDEXES:
                assert idx in actual_indexes, f"Missing required index: {idx}"
            
            print("✅ HFS Schema Contract Verified: 21 columns and 5 indexes match live contract in 'public' schema.")
    finally:
        conn.close()

if __name__ == "__main__":
    test_hfs_schema_contract()
