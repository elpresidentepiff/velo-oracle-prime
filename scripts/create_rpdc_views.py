"""
Create convenience views for intelligence.rpdc_tags_2025 and _2024.
Exposes rpdc_evidence and rpdc_blockers as JSONB alongside the native TEXT[] columns.
Safe to re-run (CREATE OR REPLACE).
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
    print(f"\n── Creating intelligence.rpdc_tags_{year}_view ───────────────")
    try:
        sql(f"""
            CREATE OR REPLACE VIEW intelligence.rpdc_tags_{year}_view AS
            SELECT
                tag_id,
                run_id,
                entity_id,
                horse_name_raw,
                trainer,
                date,
                rpdc_tag_base,
                rpdc_confidence,
                rpdc_evidence,
                rpdc_blockers,
                rpdc_explanation,
                rpdc_override_tag,
                rpdc_override_reason,
                array_to_json(rpdc_evidence)::jsonb  AS rpdc_evidence_json,
                array_to_json(rpdc_blockers)::jsonb  AS rpdc_blockers_json
            FROM intelligence.rpdc_tags_{year};
        """)
        print("  OK")
    except Exception as e:
        print(f"  ERROR: {e}")

# Verify views exist and return rows
print("\n── Verification ────────────────────────────────────────────────")
for year in [2025, 2024]:
    try:
        rows = sql(f"SELECT COUNT(*) AS n FROM intelligence.rpdc_tags_{year}_view")
        n = rows[0]["n"]
        sample = sql(f"""
            SELECT horse_name_raw, rpdc_tag_base, rpdc_confidence,
                   rpdc_evidence_json, rpdc_blockers_json, rpdc_override_tag
            FROM intelligence.rpdc_tags_{year}_view
            WHERE rpdc_tag_base = 'T'
            LIMIT 1
        """)
        print(f"\n  rpdc_tags_{year}_view: {n:,} rows")
        if sample:
            r = sample[0]
            print(f"    Sample T-tag: {r['horse_name_raw']} | {r['rpdc_tag_base']} {r['rpdc_confidence']}")
            print(f"    evidence_json: {r['rpdc_evidence_json']}")
            print(f"    override_tag: {r['rpdc_override_tag']} (should be null)")
    except Exception as e:
        print(f"  rpdc_tags_{year}_view: ERROR — {e}")

print("\nDone.")
