#!/usr/bin/env python3.11
"""
Gate E Evidence: Direct Supabase query proof
"""
import os
from supabase import create_client

# Get from environment
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

if not url or not key:
    print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY in environment")
    exit(1)

print(f"Connecting to: {url[:40]}...")

# Connect
supabase = create_client(url, key)

# Query engine_runs (limit 5 most recent)
print("\n=== ENGINE_RUNS (5 most recent) ===")
result = supabase.table("engine_runs").select(
    "engine_run_id,race_id,created_at,chassis_type"
).order("created_at", desc=True).limit(5).execute()

if result.data:
    for row in result.data:
        print(f"engine_run_id: {row['engine_run_id']}")
        print(f"  race_id: {row['race_id']}")
        print(f"  chassis_type: {row.get('chassis_type', 'N/A')}")
        print(f"  created_at: {row['created_at']}")
        print()
    
    # Get one engine_run_id for verdicts query
    test_id = result.data[0]['engine_run_id']
    print(f"=== VERDICTS for engine_run_id={test_id} ===")
    verdicts = supabase.table("verdicts").select(
        "engine_run_id,chassis_type,top_4_structure"
    ).eq("engine_run_id", test_id).execute()
    
    if verdicts.data:
        for v in verdicts.data:
            print(f"engine_run_id: {v['engine_run_id']}")
            print(f"  chassis_type: {v.get('chassis_type', 'N/A')}")
            top4_str = str(v.get('top_4_structure', 'N/A'))
            print(f"  top_4_structure: {top4_str[:150]}...")
    else:
        print("No verdicts found for this engine_run_id")
else:
    print("No rows returned from engine_runs")
