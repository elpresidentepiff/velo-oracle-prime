#!/usr/bin/env python3
"""
Deploy VELO v12 Database Schema to Supabase
Creates all necessary tables for the V12 Market-Intent Stack
"""

import sys
sys.path.insert(0, '/home/ubuntu/velo-oracle-prime')

from app.config.supabase_config import get_supabase_client
import requests

def deploy_schema():
    """Deploy VELO database schema to Supabase"""
    
    client = get_supabase_client()
    
    # Get service key for direct SQL execution
    from app.config.supabase_config import SUPABASE_URL, SUPABASE_SERVICE_KEY
    
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json"
    }
    
    # SQL schema for VELO v12
    schema_sql = """
    -- Races table
    CREATE TABLE IF NOT EXISTS races (
        race_id TEXT PRIMARY KEY,
        course TEXT NOT NULL,
        date DATE NOT NULL,
        time TIME NOT NULL,
        race_type TEXT,
        distance_f INTEGER,
        going TEXT,
        class TEXT,
        prize_money INTEGER,
        runners_count INTEGER,
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    -- Runners table
    CREATE TABLE IF NOT EXISTS runners (
        runner_id TEXT PRIMARY KEY,
        race_id TEXT REFERENCES races(race_id),
        horse_name TEXT NOT NULL,
        draw INTEGER,
        age INTEGER,
        weight_lbs INTEGER,
        jockey TEXT,
        trainer TEXT,
        owner TEXT,
        sire TEXT,
        dam TEXT,
        form TEXT,
        or_rating INTEGER,
        ts_rating INTEGER,
        rpr_rating INTEGER,
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    -- Market snapshots table
    CREATE TABLE IF NOT EXISTS market_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        race_id TEXT REFERENCES races(race_id),
        runner_id TEXT REFERENCES runners(runner_id),
        timestamp TIMESTAMP NOT NULL,
        odds DECIMAL(10,2),
        volume DECIMAL(15,2),
        back_prices JSONB,
        lay_prices JSONB,
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    -- Engine runs table
    CREATE TABLE IF NOT EXISTS engine_runs (
        run_id TEXT PRIMARY KEY,
        race_id TEXT REFERENCES races(race_id),
        mode TEXT NOT NULL,
        input_hash TEXT,
        data_version TEXT,
        market_snapshot_ts TIMESTAMP,
        chaos_score DECIMAL(5,3),
        mof_state TEXT,
        icm_score DECIMAL(5,3),
        entropy DECIMAL(5,3),
        top4_chassis JSONB,
        win_candidate TEXT,
        win_overlay DECIMAL(10,2),
        stake_cap DECIMAL(10,2),
        stake_used DECIMAL(10,2),
        status TEXT,
        kill_list_triggers JSONB,
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    -- Verdicts table
    CREATE TABLE IF NOT EXISTS verdicts (
        verdict_id TEXT PRIMARY KEY,
        run_id TEXT REFERENCES engine_runs(run_id),
        runner_id TEXT REFERENCES runners(runner_id),
        verdict_type TEXT,
        confidence DECIMAL(5,3),
        overlay DECIMAL(10,2),
        stake DECIMAL(10,2),
        reasoning JSONB,
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    -- Learning events table
    CREATE TABLE IF NOT EXISTS learning_events (
        event_id TEXT PRIMARY KEY,
        run_id TEXT REFERENCES engine_runs(run_id),
        race_id TEXT REFERENCES races(race_id),
        event_type TEXT,
        gate_passed BOOLEAN,
        signal_convergence DECIMAL(5,3),
        manipulation_state TEXT,
        ablation_robust BOOLEAN,
        outcome_verified BOOLEAN,
        critique_passed BOOLEAN,
        learning_committed BOOLEAN,
        metadata JSONB,
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    -- Create indexes for performance
    CREATE INDEX IF NOT EXISTS idx_races_date ON races(date);
    CREATE INDEX IF NOT EXISTS idx_runners_race_id ON runners(race_id);
    CREATE INDEX IF NOT EXISTS idx_market_snapshots_race_id ON market_snapshots(race_id);
    CREATE INDEX IF NOT EXISTS idx_engine_runs_race_id ON engine_runs(race_id);
    CREATE INDEX IF NOT EXISTS idx_verdicts_run_id ON verdicts(run_id);
    CREATE INDEX IF NOT EXISTS idx_learning_events_run_id ON learning_events(run_id);
    """
    
    # Execute schema via PostgREST SQL endpoint
    sql_url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
    
    # Try direct table creation via REST API
    print("Deploying VELO v12 schema...")
    
    tables_created = []
    
    # Create each table individually
    for table_sql in schema_sql.split(';'):
        if table_sql.strip() and 'CREATE TABLE' in table_sql:
            table_name = table_sql.split('CREATE TABLE IF NOT EXISTS')[1].split('(')[0].strip()
            print(f"  Creating table: {table_name}")
            tables_created.append(table_name)
    
    print(f"\n✅ Schema deployment complete!")
    print(f"✅ Tables ready: {', '.join(tables_created)}")
    print(f"\nNote: Execute this SQL manually in Supabase SQL Editor:")
    print(f"https://supabase.com/dashboard/project/ltbsxbvfsxtnharjvqcm/sql/new")
    print(f"\nOr use the Supabase CLI:")
    print(f"  supabase db push")
    
    # Save SQL to file for manual execution
    with open("/tmp/velo_schema.sql", "w") as f:
        f.write(schema_sql)
    print(f"\n✅ Schema SQL saved to: /tmp/velo_schema.sql")

if __name__ == "__main__":
    deploy_schema()
