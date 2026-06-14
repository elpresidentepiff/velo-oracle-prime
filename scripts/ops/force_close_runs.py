from app.core.runtime_env import resolve_supabase_url, resolve_supabase_service_key
from supabase import create_client
import os

def force_close_active_runs():
    url = resolve_supabase_url()
    key = resolve_supabase_service_key()
    if not url or not key:
        print("Missing Supabase credentials")
        return

    db = create_client(url, key)
    
    # Close any 'running' daily_scoring runs
    try:
        resp = db.table("pipeline_runs") \
            .update({
                "run_state": "completed", 
                "status": "FAIL", 
                "error_message": "Force closed by operator"
            }) \
            .eq("run_state", "running") \
            .eq("service_name", "velo_prime_v1") \
            .execute()
        print(f"Force closed {len(resp.data)} runs.")
    except Exception as e:
        print(f"Failed to close runs: {e}")

if __name__ == "__main__":
    force_close_active_runs()
