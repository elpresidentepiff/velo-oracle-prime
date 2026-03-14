"""
Phase 2 — Supabase connection test
Lists all existing tables and row counts
"""
import os
import sys
from pathlib import Path

# Load .env manually (no dotenv dependency needed)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")

if not url or not key:
    print("FAILED: SUPABASE_URL or SUPABASE_SERVICE_KEY missing from .env")
    sys.exit(1)

try:
    client = create_client(url, key)

    # Query information_schema for all user tables
    resp = client.rpc("get_tables", {}).execute() if False else None

    # Use REST to query pg_tables via SQL
    tables_resp = client.table("races").select("*", count="exact").limit(0).execute()

    # Actually let's just try each known table
    known_tables = [
        "import_batches", "racing_data", "betting_ledger", "races",
        "course_profitability", "betfair_odds", "model_comparison",
        "model_versions", "racecards", "manipulation_alerts",
        "manipulation_effectiveness", "permanent_principles", "rpd_tags",
        "results", "sectional_data", "runners", "betfair_markets",
        "system_performance", "race_analysis", "predictions", "selections",
        "sigma_audits", "daily_performance", "learned_patterns",
        "plot_memory_spine"
    ]

    print(f"\n{'='*50}")
    print("SUPABASE CONNECTION: OK")
    print(f"URL: {url}")
    print(f"{'='*50}")
    print(f"\nExisting tables:\n")

    existing = []
    for table in known_tables:
        try:
            r = client.table(table).select("*", count="exact").limit(0).execute()
            count = r.count if r.count is not None else "?"
            print(f"  [OK] {table:<35} ({count} rows)")
            existing.append(table)
        except Exception:
            print(f"  [--] {table:<35} (not found)")

    print(f"\nTotal: {len(existing)}/{len(known_tables)} tables exist")
    print("="*50)

except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
