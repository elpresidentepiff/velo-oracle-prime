"""
Supabase Configuration for VELO
Centralized configuration for Supabase database connection
"""
import os
from typing import Optional

# Supabase Project Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ltbsxbvfsxtnharjvqcm.supabase.co")
SUPABASE_PROJECT_ID = "ltbsxbvfsxtnharjvqcm"

# API Keys (use environment variables in production)
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
if not SUPABASE_ANON_KEY:
    raise ValueError("SUPABASE_ANON_KEY environment variable is required")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
if not SUPABASE_SERVICE_KEY:
    raise ValueError("SUPABASE_SERVICE_KEY environment variable is required")

# Access Token for Management API
SUPABASE_ACCESS_TOKEN = os.getenv("SUPABASE_ACCESS_TOKEN")  # Optional for management API

# Database Connection String (PostgreSQL)
# Format: postgresql://postgres:[YOUR-PASSWORD]@db.ltbsxbvfsxtnharjvqcm.supabase.co:5432/postgres
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL", "")

# REST API Endpoint
SUPABASE_REST_URL = f"{SUPABASE_URL}/rest/v1"

# Realtime Endpoint
SUPABASE_REALTIME_URL = f"{SUPABASE_URL}/realtime/v1"

# Storage Endpoint
SUPABASE_STORAGE_URL = f"{SUPABASE_URL}/storage/v1"


def get_supabase_client():
    """
    Get configured Supabase client
    Returns a client instance for database operations
    """
    try:
        from supabase import create_client, Client
        
        if not SUPABASE_SERVICE_KEY:
            raise ValueError("SUPABASE_SERVICE_KEY environment variable not set")
        
        client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return client
    except ImportError:
        raise ImportError("supabase-py not installed. Run: pip install supabase")
    except Exception as e:
        raise Exception(f"Failed to create Supabase client: {e}")


def get_database_url() -> str:
    """
    Get PostgreSQL connection URL for direct database access
    """
    if not SUPABASE_DB_URL:
        raise ValueError("SUPABASE_DB_URL environment variable not set")
    return SUPABASE_DB_URL


# Table Names
TABLES = {
    "races": "races",
    "runners": "runners",
    "market_snapshots": "market_snapshots",
    "engine_runs": "engine_runs",
    "engine_verdicts": "engine_verdicts",
    "learning_events": "learning_events",
    "stable_entries": "stable_entries",
    "race_conditions": "race_conditions",
    "racecards": "racecards",
    "racing_data": "racing_data",
    "betfair_markets": "betfair_markets",
    "betfair_odds": "betfair_odds",
    "predictions": "predictions",
    "race_analysis": "race_analysis",
    "model_versions": "model_versions",
    "learned_patterns": "learned_patterns",
    "betting_ledger": "betting_ledger",
    "sectional_data": "sectional_data",
    "manipulation_alerts": "manipulation_alerts",
}
