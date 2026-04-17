"""
Add RPD-C columns to public.runner_race_facts.

Adds four columns:
    rpdc_tag_base   TEXT         — T / H / S / P / E
    rpdc_confidence TEXT         — high / medium / low
    rpdc_evidence   JSONB        — array of evidence codes that fired
    rpdc_blockers   JSONB        — array of blocker codes that triggered

Safe to run multiple times (uses ADD COLUMN IF NOT EXISTS).
No data written here — just schema migration.

Run: python scripts/add_rpdc_columns.py
"""
import os
import requests
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


print("Adding RPD-C columns to public.runner_race_facts...")

for stmt in [
    "ALTER TABLE public.runner_race_facts ADD COLUMN IF NOT EXISTS rpdc_tag_base TEXT;",
    "ALTER TABLE public.runner_race_facts ADD COLUMN IF NOT EXISTS rpdc_confidence TEXT;",
    "ALTER TABLE public.runner_race_facts ADD COLUMN IF NOT EXISTS rpdc_evidence JSONB;",
    "ALTER TABLE public.runner_race_facts ADD COLUMN IF NOT EXISTS rpdc_blockers JSONB;",
]:
    print(f"  {stmt[:60]}...", end=" ")
    try:
        sql(stmt)
        print("OK")
    except Exception as e:
        print(f"ERROR: {e}")

# Add indexes
print("\nAdding indexes...")
for idx in [
    "CREATE INDEX IF NOT EXISTS idx_rrf_rpdc_tag ON public.runner_race_facts (rpdc_tag_base);",
    "CREATE INDEX IF NOT EXISTS idx_rrf_rpdc_conf ON public.runner_race_facts (rpdc_confidence);",
]:
    print(f"  {idx[:70]}...", end=" ")
    try:
        sql(idx, timeout=30)
        print("OK")
    except Exception as e:
        print(f"ERROR: {e}")

# Verify
print("\nVerifying columns exist:")
r = sql("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'runner_race_facts'
      AND column_name LIKE 'rpdc%'
    ORDER BY ordinal_position
""")
for row in r:
    print(f"  {row['column_name']} — {row['data_type']}")

print("\nDone.")
