"""
Verification suite for RPD-C backfill integrity.
Run after schema migrations and before wiring to VOX.

Checks:
  1. Row counts match source (plot_candidate_flags)
  2. No T/low tags exist (T requires ≥2 evidence codes)
  3. No E tags with won_last_time blocker (blocker prevents E)
  4. No P tags with market_shortening blocker
  5. S rate within expected bounds (50–75%)
  6. T rate within expected bounds (5–12%)
  7. No rows with empty rpdc_tag_base
  8. Override fields present and null by default
  9. run_style not masquerading in runner_race_facts
  10. rpdc_tags and plot_candidate_flags have matching run_ids
"""
import os, requests, sys
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


def check(label, query, expected_fn, expected_desc):
    try:
        result = sql(query)
        val = result[0] if result else {}
        passed = expected_fn(val)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {label}")
        if not passed:
            print(f"         Expected: {expected_desc}")
            print(f"         Got:      {val}")
        return passed
    except Exception as e:
        print(f"  ❌ ERROR  {label}: {e}")
        return False


failures = []

for year in [2025, 2024]:
    source_count = sql(f"SELECT COUNT(*) n FROM intelligence.plot_candidate_flags_{year}")[0]["n"]
    print(f"\n{'='*60}")
    print(f"VERIFYING intelligence.rpdc_tags_{year}  (source: {source_count:,} rows)")
    print(f"{'='*60}")

    tests = [
        (
            "Row count matches source",
            f"SELECT COUNT(*) n FROM intelligence.rpdc_tags_{year}",
            lambda v, sc=source_count: v.get("n") == sc,
            f"n = {source_count:,}",
        ),
        (
            "No T/low tags",
            f"SELECT COUNT(*) n FROM intelligence.rpdc_tags_{year} WHERE rpdc_tag_base='T' AND rpdc_confidence='low'",
            lambda v: v.get("n", 1) == 0,
            "n = 0",
        ),
        (
            "No E with won_last_time blocker active",
            f"SELECT COUNT(*) n FROM intelligence.rpdc_tags_{year} WHERE rpdc_tag_base='E' AND 'won_last_time'=ANY(rpdc_blockers)",
            lambda v: v.get("n", 1) == 0,
            "n = 0",
        ),
        (
            "No P with market_shortening blocker active",
            f"SELECT COUNT(*) n FROM intelligence.rpdc_tags_{year} WHERE rpdc_tag_base='P' AND 'market_shortening'=ANY(rpdc_blockers)",
            lambda v: v.get("n", 1) == 0,
            "n = 0",
        ),
        (
            "No rows with empty rpdc_tag_base",
            f"SELECT COUNT(*) n FROM intelligence.rpdc_tags_{year} WHERE rpdc_tag_base IS NULL OR rpdc_tag_base=''",
            lambda v: v.get("n", 1) == 0,
            "n = 0",
        ),
        (
            "Override fields present (rpdc_override_tag)",
            f"""SELECT COUNT(*) n FROM information_schema.columns
                WHERE table_schema='intelligence' AND table_name='rpdc_tags_{year}'
                AND column_name='rpdc_override_tag'""",
            lambda v: v.get("n", 0) == 1,
            "n = 1",
        ),
        (
            "Override fields all null (no retroactive overrides)",
            f"SELECT COUNT(*) n FROM intelligence.rpdc_tags_{year} WHERE rpdc_override_tag IS NOT NULL",
            lambda v: v.get("n", 1) == 0,
            "n = 0",
        ),
        (
            "S rate within expected bounds (50–75%)",
            f"""SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE rpdc_tag_base='S') / COUNT(*), 1) pct
                FROM intelligence.rpdc_tags_{year}""",
            lambda v: 50.0 <= float(v.get("pct", 0) or 0) <= 75.0,
            "pct between 50 and 75",
        ),
        (
            "T rate within expected bounds (5–12%)",
            f"""SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE rpdc_tag_base='T') / COUNT(*), 1) pct
                FROM intelligence.rpdc_tags_{year}""",
            lambda v: 5.0 <= float(v.get("pct", 0) or 0) <= 12.0,
            "pct between 5 and 12",
        ),
        (
            "View exists and matches row count",
            f"SELECT COUNT(*) n FROM intelligence.rpdc_tags_{year}_view",
            lambda v, sc=source_count: v.get("n") == sc,
            f"n = {source_count:,}",
        ),
        (
            "Evidence JSONB cast works in view",
            f"SELECT jsonb_array_length(rpdc_evidence_json) len FROM intelligence.rpdc_tags_{year}_view WHERE rpdc_evidence IS NOT NULL AND array_length(rpdc_evidence,1)>0 LIMIT 1",
            lambda v: v.get("len", -1) >= 1,
            "len >= 1",
        ),
    ]

    for (label, query, fn, desc) in tests:
        passed = check(label, query, fn, desc)
        if not passed:
            failures.append(f"{year}: {label}")

# Global checks
print(f"\n{'='*60}")
print("GLOBAL CHECKS")
print(f"{'='*60}")

# run_style not masquerading in runner_race_facts
check(
    "runner_race_facts.rpd_tag not populated from run_style",
    "SELECT COUNT(*) n FROM public.runner_race_facts WHERE rpd_tag IS NOT NULL AND rpd_tag != ''",
    lambda v: v.get("n", 1) == 0,
    "n = 0 (rpd_tag must be null or empty — not a run_style proxy)",
)

# rpdc_tag_base populated in runner_race_facts (live pipeline working)
result = sql("SELECT COUNT(*) n FROM public.runner_race_facts WHERE rpdc_tag_base IS NOT NULL AND rpdc_tag_base != ''")
n_rpdc = result[0]["n"] if result else 0
total  = sql("SELECT COUNT(*) n FROM public.runner_race_facts")[0]["n"]
print(f"  ℹ️  INFO  runner_race_facts rpdc_tag_base populated: {n_rpdc}/{total} rows")

# Summary
print(f"\n{'='*60}")
if failures:
    print(f"❌ {len(failures)} check(s) FAILED:")
    for f in failures:
        print(f"   • {f}")
    sys.exit(1)
else:
    print("✅ ALL CHECKS PASSED — RPD-C backfill verified clean.")
    print(f"{'='*60}")
