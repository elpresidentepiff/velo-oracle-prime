# Feature Mart Refresh Script

## Overview
This script refreshes materialized views for the hot window feature mart, keeping trainer/jockey statistics up to date.

## Usage

### Refresh All Views
```bash
python scripts/refresh_features.py
```

### Refresh Single View
```bash
python scripts/refresh_features.py --view trainer_stats_14d
```

## Setup for Production

### Option 1: Using asyncpg (Recommended)
Modify `workers/ingestion_spine/db.py` to support asyncpg connections for raw SQL:

```python
import asyncpg

async def execute_raw_sql(self, query: str):
    """Execute raw SQL for operations like REFRESH MATERIALIZED VIEW"""
    conn = await asyncpg.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    try:
        await conn.execute(query)
    finally:
        await conn.close()
```

### Option 2: Create Supabase PostgreSQL Function
Create a custom function in Supabase to execute raw SQL:

```sql
CREATE OR REPLACE FUNCTION exec_sql(sql text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    EXECUTE sql;
END;
$$;
```

Then grant permissions:
```sql
GRANT EXECUTE ON FUNCTION exec_sql TO service_role;
```

### Option 3: Direct PostgreSQL Connection
Use `psql` or database admin tools to run:
```sql
REFRESH MATERIALIZED VIEW trainer_stats_14d;
REFRESH MATERIALIZED VIEW trainer_stats_30d;
-- etc.
```

## Scheduling

### With Cron
Add to crontab for daily refresh at 2 AM:
```
0 2 * * * cd /path/to/velo-oracle-prime && python3 scripts/refresh_features.py >> logs/refresh_features.log 2>&1
```

### With Prefect (Recommended)
```python
from prefect import flow, task

@task
def refresh_features():
    subprocess.run(["python", "scripts/refresh_features.py"], check=True)

@flow(name="daily-feature-refresh")
def daily_refresh():
    refresh_features()

# Schedule for daily at 2 AM
daily_refresh.serve(
    name="feature-refresh",
    cron="0 2 * * *"
)
```

## Monitoring
The script logs to stdout/stderr. Monitor logs for:
- ✅ Success messages
- ❌ Error messages
- Refresh duration for each view

## Troubleshooting

### RPC exec_sql not available
If you see this error, the custom PostgreSQL function hasn't been created yet. Follow Option 2 above or use Option 3 to refresh manually.

### Timeout Issues
Large materialized views may take several minutes to refresh. Adjust timeout settings or run during off-peak hours.

### Performance Impact
Refreshing materialized views can impact database performance. Schedule refreshes during low-traffic periods (e.g., 2-4 AM).
