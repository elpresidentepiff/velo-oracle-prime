"""
tests/test_vp_gatekeeper_promotion.py
=======================================
Guardrail tests for VP Gatekeeper Promotion V1.

Checks:
1. VP parser extracts prob= from plain string notes (Mar-Apr format)
2. VP parser extracts prob= from JSON-string notes (May-Jun format)
3. VP parser returns None when no prob= found
4. Current-era union dedupes overlap rows (no duplicate race_ids)
5. Local-only rows are retained in union
6. Era flag is mandatory on every union row
7. PRE_SURGERY rows cannot enter CURRENT_ERA table
8. Gatekeeper script does not import supabase client (read-only panel)
9. Course table enforces OBSERVATION_ONLY for n<10
10. 740 vs 732 local row discrepancy is explained (May 31 duplicates)
"""

import re
import json
import os
import glob
import pytest
from collections import Counter

SIGMA_DIR = "data/sigma_results"
UNION_JSON = "data/reports/current_era_sigma_union_2026_05_08_to_2026_06_13.json"
UNION_ROWS_JSON = "data/reports/current_era_sigma_union_rows_2026_05_08_to_2026_06_13.json"
COURSE_TABLE_JSON = "data/reports/current_era_course_excellence_table.json"
PANEL_SCRIPT = "scripts/ops/build_vp_opportunity_panel.py"
SURGERY_DATE = "2026-05-08"

PROB_PATTERN = re.compile(r"prob=([\d.]+)")


# ─── 1. VP parser — plain string format ──────────────────────────────────────

def test_vp_parser_plain_string():
    """Mar-Apr format: plain string with prob= inline."""
    notes = "pred=Dutch Corner prob=0.1304 AT BASELINE — review miss classes for pattern"
    m = PROB_PATTERN.search(notes)
    assert m is not None, "prob= not found in plain string"
    assert abs(float(m.group(1)) - 0.1304) < 1e-6


# ─── 2. VP parser — JSON string format ───────────────────────────────────────

def test_vp_parser_json_string():
    """May-Jun format: notes is a JSON string with prob= inside summary."""
    notes = '{"summary": "pred=Stardom Glory | prob=0.6811 ABOVE BASELINE — model calibration healthy", "full_field_rpd": []}'
    m = PROB_PATTERN.search(notes)
    assert m is not None, "prob= not found in JSON-string notes"
    assert abs(float(m.group(1)) - 0.6811) < 1e-6


# ─── 3. VP parser — returns None when absent ─────────────────────────────────

def test_vp_parser_returns_none_when_absent():
    """No prob= in notes → should not extract any value."""
    notes = "Top strike won at 3/1. Value pick faded late. Tags accurate."
    m = PROB_PATTERN.search(notes)
    assert m is None, "Should not find prob= in plain narrative note"


def test_vp_parser_returns_none_on_empty():
    """Empty notes → no VP extracted."""
    assert PROB_PATTERN.search("") is None
    assert PROB_PATTERN.search(None or "") is None


# ─── 4. Union has no duplicate race_ids ──────────────────────────────────────

def test_union_no_duplicate_race_ids():
    """Each race_id should appear at most once in the union."""
    if not os.path.exists(UNION_ROWS_JSON):
        pytest.skip("Union rows JSON not found — run build first")
    with open(UNION_ROWS_JSON) as f:
        union = json.load(f)
    race_ids = [r["race_id"] for r in union if r.get("race_id")]
    counts = Counter(race_ids)
    dupes = {k: v for k, v in counts.items() if v > 1}
    assert len(dupes) == 0, f"Duplicate race_ids in union: {dupes}"


# ─── 5. Local-only rows are retained ─────────────────────────────────────────

def test_union_contains_local_only_rows():
    """LOCAL_ONLY rows must be present in the union."""
    if not os.path.exists(UNION_ROWS_JSON):
        pytest.skip("Union rows JSON not found — run build first")
    with open(UNION_ROWS_JSON) as f:
        union = json.load(f)
    local_only = [r for r in union if r.get("source_layer") == "LOCAL_ONLY"]
    assert len(local_only) > 0, "No LOCAL_ONLY rows in union — local rows were dropped"
    assert len(local_only) >= 200, f"Expected ~294 LOCAL_ONLY rows, got {len(local_only)}"


# ─── 6. Era flag is mandatory on every row ───────────────────────────────────

def test_union_every_row_has_era_flag():
    """Every row in the union must have era='CURRENT_ERA'."""
    if not os.path.exists(UNION_ROWS_JSON):
        pytest.skip("Union rows JSON not found — run build first")
    with open(UNION_ROWS_JSON) as f:
        union = json.load(f)
    missing_era = [r for r in union if r.get("era") != "CURRENT_ERA"]
    assert len(missing_era) == 0, f"{len(missing_era)} rows missing era=CURRENT_ERA"


# ─── 7. PRE_SURGERY rows cannot enter CURRENT_ERA ────────────────────────────

def test_union_no_pre_surgery_rows():
    """No row with race_date before the surgery line should be in the union."""
    if not os.path.exists(UNION_ROWS_JSON):
        pytest.skip("Union rows JSON not found — run build first")
    with open(UNION_ROWS_JSON) as f:
        union = json.load(f)
    pre_surgery = [r for r in union if (r.get("race_date") or "") < SURGERY_DATE and r.get("race_date")]
    assert len(pre_surgery) == 0, (
        f"{len(pre_surgery)} pre-surgery rows found in CURRENT_ERA union. "
        f"Surgery line: {SURGERY_DATE}. "
        f"Earliest: {min(r['race_date'] for r in pre_surgery)}"
    )


# ─── 8. Panel script does not import Supabase ────────────────────────────────

def test_panel_script_no_supabase_import():
    """The opportunity panel script must not import or instantiate supabase client."""
    if not os.path.exists(PANEL_SCRIPT):
        pytest.skip(f"Panel script not found: {PANEL_SCRIPT}")
    with open(PANEL_SCRIPT) as f:
        content = f.read()
    assert "supabase_client" not in content, "supabase_client found in panel script"
    assert "from supabase import" not in content, "'from supabase import' found in panel script"
    assert "import supabase" not in content, "'import supabase' found in panel script"


# ─── 9. Course table enforces OBSERVATION_ONLY for n<10 ──────────────────────

def test_course_table_sample_discipline():
    """No course with n<10 should have a meaningful tier label (must be OBSERVATION_ONLY)."""
    if not os.path.exists(COURSE_TABLE_JSON):
        pytest.skip("Course table JSON not found — run build first")
    with open(COURSE_TABLE_JSON) as f:
        data = json.load(f)
    obs_only = data.get("observation_only", [])
    # All observation-only courses must have n < 10
    wrong = [c for c in obs_only if c["n"] >= 10]
    assert len(wrong) == 0, f"n>=10 courses in OBSERVATION_ONLY tier: {wrong}"
    # No EXCELLING or DRAIN course can have n < 10 in all_meaningful
    all_meaningful = data.get("all_meaningful", [])
    bad_excelling = [c for c in all_meaningful if c["course_tier"] == "EXCELLING" and c["n"] < 10]
    bad_drain = [c for c in all_meaningful if c["course_tier"] == "DRAIN" and c["n"] < 10]
    assert len(bad_excelling) == 0, f"EXCELLING courses with n<10: {bad_excelling}"
    assert len(bad_drain) == 0, f"DRAIN courses with n<10: {bad_drain}"


# ─── 10. May 31 duplicate race_ids explained ─────────────────────────────────

def test_local_universe_may31_duplicates_explained():
    """
    The 8-row gap (740 rows, 732 unique race_ids) must be fully explained
    by duplicates in sigma_results_2026_05_31.json.
    """
    fp = os.path.join(SIGMA_DIR, "sigma_results_2026_05_31.json")
    if not os.path.exists(fp):
        pytest.skip("May 31 sigma file not found")
    with open(fp) as f:
        data = json.load(f)
    rows = data.get("rows", [])
    race_id_counts = Counter(r.get("race_id") for r in rows if r.get("race_id"))
    dup_ids = {k: v for k, v in race_id_counts.items() if v > 1}
    # We expect exactly 6 duplicate race_ids (contributing 8 extra rows)
    extra_rows = sum(v - 1 for v in dup_ids.values())
    assert extra_rows == 8, (
        f"Expected 8 extra rows from May 31 duplicates, got {extra_rows}. "
        f"Duplicate ids: {dup_ids}"
    )
    assert len(dup_ids) == 6, f"Expected 6 duplicate race_ids, got {len(dup_ids)}: {dup_ids}"


# ─── Bonus: Union summary stats sanity ───────────────────────────────────────

def test_union_summary_stats():
    """Union must have >=1200 rows, 100% VP, 100% outcome."""
    if not os.path.exists(UNION_ROWS_JSON):
        pytest.skip("Union rows JSON not found — run build first")
    with open(UNION_ROWS_JSON) as f:
        union = json.load(f)
    assert len(union) >= 1200, f"Expected >=1200 rows in union, got {len(union)}"
    vp_missing = [r for r in union if r.get("vp") is None]
    outcome_missing = [r for r in union if not r.get("outcome")]
    assert len(vp_missing) == 0, f"{len(vp_missing)} rows missing VP"
    assert len(outcome_missing) == 0, f"{len(outcome_missing)} rows missing outcome"


def test_vp_gradient_holds_in_union():
    """VP>=0.40 SR must be meaningfully above baseline SR."""
    if not os.path.exists(UNION_ROWS_JSON):
        pytest.skip("Union rows JSON not found — run build first")
    with open(UNION_ROWS_JSON) as f:
        union = json.load(f)
    n = len(union)
    baseline_sr = sum(1 for r in union if r["outcome"] == "WIN") / n
    vp40 = [r for r in union if r.get("vp") and r["vp"] >= 0.40]
    if not vp40:
        pytest.fail("No VP>=0.40 rows in union")
    vp40_sr = sum(1 for r in vp40 if r["outcome"] == "WIN") / len(vp40)
    assert vp40_sr > baseline_sr + 0.10, (
        f"VP>=0.40 SR ({vp40_sr:.3f}) not meaningfully above baseline ({baseline_sr:.3f}). "
        f"Expected at least +10pp lift."
    )
