import os
import json
from datetime import date
from dotenv import load_dotenv
from supabase import create_client

def fetch_verdicts():
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("Missing Supabase credentials")
        return

    db = create_client(url, key)
    target_date = "2026-06-06"
    
    print(f"Fetching verdicts for {target_date} via race_id pattern...")
    res = db.table("velo_verdicts").select("*").ilike("race_id", f"%_20260606_%").execute()
    
    if res.data:
        print(f"Found {len(res.data)} verdicts.")
        # Check jockeys in the first few
        for r in res.data[:5]:
            top = r.get("top", {})
            print(f"Race: {r['race_id']} | Horse: {top.get('horse')} | Jockey: {top.get('jockey')}")
            
        # Write to local file to restore truth
        output_path = "data/velo_prime_verdicts_2026_06_06.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(res.data, f, indent=2)
        print(f"Saved verdicts to {output_path}")
    else:
        print("No verdicts found in Supabase for this date.")

if __name__ == "__main__":
    fetch_verdicts()
