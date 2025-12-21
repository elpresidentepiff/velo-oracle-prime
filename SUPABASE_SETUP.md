# Supabase Integration Setup Guide

## Overview

This guide walks through integrating Supabase as the database backend for VELO v12.

---

## Prerequisites

- Supabase project: `ltbsxbvfsxtnharjvqcm`
- Project URL: `https://ltbsxbvfsxtnharjvqcm.supabase.co`
- Access to Supabase dashboard: https://supabase.com/dashboard

---

## Step 1: Get API Keys

1. Go to: https://supabase.com/dashboard/project/ltbsxbvfsxtnharjvqcm/settings/api-keys/legacy
2. Copy the **anon** key (public)
3. Click **Reveal** and copy the **service_role** key (secret)

---

## Step 2: Update Configuration

Edit `app/config/supabase_config.py`:

```python
SUPABASE_URL = "https://ltbsxbvfsxtnharjvqcm.supabase.co"
SUPABASE_ANON_KEY = "<paste_anon_key_here>"
SUPABASE_SERVICE_KEY = "<paste_service_role_key_here>"
```

---

## Step 3: Deploy Database Schema

Run the schema deployment script:

```bash
cd /home/ubuntu/velo-oracle-prime
python3 scripts/deploy_supabase_schema.py
```

This will create the following tables:
- `races` - Race metadata
- `runners` - Runner details
- `market_snapshots` - Market state at decision time
- `engine_runs` - Full engine execution records
- `verdicts` - Decision outputs
- `learning_events` - Post-race learning data

---

## Step 4: Test Connection

```bash
python3 -c "
from app.db.supabase_client import get_client

client = get_client()
if client.health_check():
    print('✅ Supabase connected successfully')
else:
    print('❌ Connection failed')
"
```

---

## Step 5: Wire into V12 Pipeline

The Supabase client is already integrated into:
- `app/logging/csv_logger.py` - Logs to CSV and Supabase
- `app/v10_entrypoint.py` - Stores engine runs
- `app/learning/post_race_critique.py` - Stores learning events

No additional wiring needed once keys are configured.

---

## Troubleshooting

### 401 Unauthorized Error

**Cause**: Invalid or expired API key

**Fix**:
1. Regenerate keys in Supabase dashboard
2. Update `app/config/supabase_config.py`
3. Restart application

### Connection Timeout

**Cause**: Network restrictions or firewall

**Fix**:
1. Check Network Restrictions in Database Settings
2. Add your IP to allowlist if needed
3. Ensure SSL is enabled

### Table Not Found

**Cause**: Schema not deployed

**Fix**:
1. Run `scripts/deploy_supabase_schema.py`
2. Verify tables exist in Table Editor

---

## Schema Deployment Script

Create `scripts/deploy_supabase_schema.py`:

```python
#!/usr/bin/env python3
"""Deploy VELO database schema to Supabase"""

from app.db.supabase_client import get_client

def deploy_schema():
    client = get_client()
    
    # Create races table
    client.execute_sql("""
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
    """)
    
    # Create runners table
    client.execute_sql("""
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
    """)
    
    # Create market_snapshots table
    client.execute_sql("""
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
    """)
    
    # Create engine_runs table
    client.execute_sql("""
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
    """)
    
    # Create verdicts table
    client.execute_sql("""
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
    """)
    
    # Create learning_events table
    client.execute_sql("""
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
    """)
    
    print("✅ Schema deployed successfully")

if __name__ == "__main__":
    deploy_schema()
```

---

## Next Steps

1. Configure API keys
2. Deploy schema
3. Test connection
4. Run V12 integration test
5. Monitor logs in Supabase dashboard

---

## Support

If you encounter issues:
1. Check Supabase project logs: https://supabase.com/dashboard/project/ltbsxbvfsxtnharjvqcm/logs
2. Verify API keys are valid
3. Ensure schema is deployed
4. Check network restrictions

