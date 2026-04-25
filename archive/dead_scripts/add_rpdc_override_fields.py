"""
Add rpdc_override_tag and rpdc_override_reason to intelligence.rpdc_tags_2025 and _2024.
Safe to re-run (ADD COLUMN IF NOT EXISTS).
"""
import os, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

TOKEN = os.getenv("SUPABASE_ACCESS_TOKEN")
REF   = os.getenv("SUPABASE_URL", "").split("//")[-1].split(".")[0]


def sql(q, timeout=60):
    r = requests.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"query": q}, timeout=timeout,
    )
    result = r.json()
    if isinstance(result, dict) and "message" in result:
        raise ValueError(result["message"])
    return result


for year in [2025, 2024]:
    print(f"\n── intelligence.rpdc_tags_{year} ──────────────────────────")
    for stmt in [
        f"ALTER TABLE intelligence.rpdc_tags_{year} ADD COLUMN IF NOT EXISTS rpdc_override_tag TEXT;",
        f"ALTER TABLE intelligence.rpdc_tags_{year} ADD COLUMN IF NOT EXISTS rpdc_override_reason TEXT;",
    ]:
        print(f"  {stmt[:80]}", end=" ")
        try:
            sql(stmt)
            print("OK")
        except Exception as e:
            print(f"ERROR: {e}")

# Verify
print("\n── Verification ───────────────────────────────────────────────")
for year in [2025, 2024]:
    rows = sql(f"""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'intelligence'
          AND table_name   = 'rpdc_tags_{year}'
          AND column_name LIKE 'rpdc%'
        ORDER BY ordinal_position
    """)
    print(f"\n  rpdc_tags_{year}:")
    for r in rows:
        print(f"    {r['column_name']} ({r['data_type']}) nullable={r['is_nullable']}")

print("\nDone.")
