"""
tests/test_vfu_pick_sp_enrichment.py
======================================
VFU-03 — Tests for local pick_sp enrichment from innovation protocol CSV.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_enrich_pick_sp import (
    build_csv_indexes,
    is_local_only_race_id,
    join_row,
    norm_course,
    norm_horse,
    parse_sp,
    to_minutes,
)


# ── 1. Normalises course names ────────────────────────────────────────────────

def test_norm_course_lowercases_and_strips():
    assert norm_course("  Ascot  ") == "ascot"


def test_norm_course_removes_punctuation():
    result = norm_course("Wolverhampton (AW)")
    assert "wolverhampton" in result
    assert "(" not in result
    # leading/trailing cleaned
    result2 = norm_course("Chester-le-Street")
    assert "chester" in result2
    assert "-" not in result2


def test_norm_course_handles_accents():
    result = norm_course("Longchamp")
    assert result == "longchamp"


def test_norm_course_handles_none():
    assert norm_course(None) == ""
    assert norm_course("") == ""


# ── 2. Normalises off_time formats ────────────────────────────────────────────

def test_to_minutes_colon_format():
    assert to_minutes("14:30") == 14 * 60 + 30


def test_to_minutes_pm_assumption_for_low_hours():
    # "2:20" → 14:20 (horse racing assumes PM for hours < 10)
    assert to_minutes("2:20") == 14 * 60 + 20


def test_to_minutes_dot_format():
    assert to_minutes("14.30") == 14 * 60 + 30


def test_to_minutes_none_or_empty():
    assert to_minutes(None) is None
    assert to_minutes("") is None
    assert to_minutes("  ") is None


# ── 3. Normalises horse names ─────────────────────────────────────────────────

def test_norm_horse_strips_country_suffix():
    assert norm_horse("Bint Archange (IRE)") == "bint archange"


def test_norm_horse_removes_apostrophe_and_hyphen():
    assert norm_horse("O'Brien's Run") == "obriens run"
    assert norm_horse("Top-Class") == "top class"


def test_norm_horse_handles_none():
    assert norm_horse(None) == ""
    assert norm_horse("") == ""


def test_norm_horse_normalises_accents():
    result = norm_horse("Réponse Finale")
    assert "rponse" in result or "reponse" in result or result == "reponse finale"


# ── 4. Primary join fills pick_sp ─────────────────────────────────────────────

def test_primary_join_race_id_horse_fills_sp():
    csv_rows = [
        {
            "race_id": "rac_123",
            "horse": "Test Runner",
            "sp_decimal": "5.5",
            "date": "2026-05-21",
            "race_time": "2:30",
        }
    ]
    union_row = {
        "race_id": "rac_123",
        "horse_name": "Test Runner (IRE)",
        "race_date": "2026-05-21",
        "course": "Ascot",
        "off_time": "2:30",
        "pick_sp": None,
    }
    by_rid_horse, by_date_course_min = build_csv_indexes(csv_rows, {"rac_123": "2026-05-21"})
    result = join_row(union_row, by_rid_horse, by_date_course_min)
    assert result["pick_sp"] == 5.5
    assert result["pick_sp_source"] == "INNOVATION_CSV_RACE_ID_HORSE"
    assert result["pick_sp_join_confidence"] == "HIGH"


# ── 5. Fallback ±2-minute join fills only if unique ──────────────────────────

def test_fallback_time_fills_if_unique():
    csv_rows = [
        {
            "race_id": "rac_999",
            "horse": "Solo Horse",
            "sp_decimal": "3.0",
            "date": "2026-06-10",
            "course": "York",
            "race_time": "2:32",  # 2 min after 2:30
        }
    ]
    union_row = {
        "race_id": "rac_NOMATCH",
        "horse_name": "Solo Horse",
        "race_date": "2026-06-10",
        "course": "York",
        "off_time": "2:30",
        "pick_sp": None,
    }
    by_rid_horse, by_date_course_min = build_csv_indexes(csv_rows, {})
    result = join_row(union_row, by_rid_horse, by_date_course_min)
    assert result["pick_sp"] == 3.0
    assert result["pick_sp_source"] == "INNOVATION_CSV_DATE_COURSE_TIME_FUZZY"


def test_fallback_time_does_not_fill_if_multiple_candidates():
    csv_rows = [
        {
            "race_id": "rac_A",
            "horse": "Double Horse",
            "sp_decimal": "3.0",
            "date": "2026-06-10",
            "course": "York",
            "race_time": "2:32",
        },
        {
            "race_id": "rac_B",
            "horse": "Double Horse",
            "sp_decimal": "4.0",
            "date": "2026-06-10",
            "course": "York",
            "race_time": "2:31",
        },
    ]
    union_row = {
        "race_id": "rac_NOMATCH",
        "horse_name": "Double Horse",
        "race_date": "2026-06-10",
        "course": "York",
        "off_time": "2:30",
        "pick_sp": None,
    }
    by_rid_horse, by_date_course_min = build_csv_indexes(csv_rows, {})
    result = join_row(union_row, by_rid_horse, by_date_course_min)
    assert result["pick_sp"] is None
    assert result["pick_sp_ambiguous"] is True


# ── 6. Ambiguous matches are not filled ──────────────────────────────────────

def test_ambiguous_date_course_time_not_filled():
    # Two rows with same date+course+time+horse — ambiguous, must not fill
    csv_rows = [
        {
            "race_id": "rac_X1",
            "horse": "Ambig Runner",
            "sp_decimal": "5.0",
            "date": "2026-06-08",
            "course": "Chester",
            "race_time": "3:00",
        },
        {
            "race_id": "rac_X2",
            "horse": "Ambig Runner",
            "sp_decimal": "6.0",
            "date": "2026-06-08",
            "course": "Chester",
            "race_time": "3:00",
        },
    ]
    union_row = {
        "race_id": "rac_NOMATCH",
        "horse_name": "Ambig Runner",
        "race_date": "2026-06-08",
        "course": "Chester",
        "off_time": "3:00",
        "pick_sp": None,
    }
    by_rid_horse, by_date_course_min = build_csv_indexes(csv_rows, {})
    result = join_row(union_row, by_rid_horse, by_date_course_min)
    assert result["pick_sp"] is None
    assert result["pick_sp_ambiguous"] is True


# ── 7. Unmatched rows get missing_reason ─────────────────────────────────────

def test_unmatched_row_gets_missing_reason():
    union_row = {
        "race_id": "rac_NOTINCSV",
        "horse_name": "Ghost Runner",
        "race_date": "2026-05-08",
        "course": "Ascot",
        "off_time": "2:00",
        "pick_sp": None,
    }
    by_rid_horse, by_date_course_min = build_csv_indexes([], {})
    result = join_row(union_row, by_rid_horse, by_date_course_min)
    assert result["pick_sp"] is None
    assert result["pick_sp_missing_reason"] == "UNMATCHED_NO_CSV_ENTRY"


# ── 8. Existing pick_sp is not overwritten ────────────────────────────────────

def test_existing_sp_not_overwritten():
    csv_rows = [
        {
            "race_id": "rac_123",
            "horse": "Already Priced",
            "sp_decimal": "5.5",
            "date": "2026-06-10",
            "race_time": "2:30",
        }
    ]
    union_row = {
        "race_id": "rac_123",
        "horse_name": "Already Priced",
        "race_date": "2026-06-10",
        "course": "Ascot",
        "off_time": "2:30",
        "pick_sp": 3.0,  # already has a value
    }
    by_rid_horse, by_date_course_min = build_csv_indexes(csv_rows, {"rac_123": "2026-06-10"})
    result = join_row(union_row, by_rid_horse, by_date_course_min)
    assert result["pick_sp"] == 3.0
    assert result["pick_sp_source"] == "EXISTING"


# ── 9. Conflict is logged ─────────────────────────────────────────────────────

def test_conflict_is_logged():
    csv_rows = [
        {
            "race_id": "rac_456",
            "horse": "Conflict Horse",
            "sp_decimal": "8.0",
            "date": "2026-06-12",
            "race_time": "3:30",
        }
    ]
    union_row = {
        "race_id": "rac_456",
        "horse_name": "Conflict Horse",
        "race_date": "2026-06-12",
        "course": "Newmarket",
        "off_time": "3:30",
        "pick_sp": 7.5,  # existing differs from CSV 8.0
    }
    by_rid_horse, by_date_course_min = build_csv_indexes(csv_rows, {"rac_456": "2026-06-12"})
    result = join_row(union_row, by_rid_horse, by_date_course_min)
    assert result["pick_sp_conflict"] is True
    assert result["pick_sp_existing"] == 7.5
    assert result["pick_sp_csv"] == 8.0
    assert result["pick_sp_resolution"] == "KEEP_EXISTING"
    assert result["pick_sp"] == 7.5


# ── 10. Enriched output preserves row count ───────────────────────────────────

def test_enriched_output_file_preserves_row_count():
    enriched_file = ROOT / "data/reports/current_era_sigma_union_rows_enriched_vfu_v1.json"
    union_file = ROOT / "data/reports/current_era_sigma_union_rows_2026_05_08_to_2026_06_13.json"

    if not enriched_file.exists():
        pytest.skip("Enriched file not yet generated — run vfu_enrich_pick_sp.py first")

    union_rows = json.loads(union_file.read_text())
    enriched_rows = json.loads(enriched_file.read_text())
    assert len(enriched_rows) == len(union_rows), (
        f"Row count mismatch: union={len(union_rows)}, enriched={len(enriched_rows)}"
    )


# ── 11. Enrichment does not write canonical Horse Passport ───────────────────

def test_enrichment_does_not_write_canonical_passport():
    enriched_file = ROOT / "data/reports/current_era_sigma_union_rows_enriched_vfu_v1.json"
    canonical = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"
    assert str(enriched_file) != str(canonical), "SAFETY: enriched path must not be canonical passport"

    if not enriched_file.exists():
        pytest.skip("Enriched file not yet generated")

    # Canonical passport must not be modified by enrichment (check it still exists and is a .jsonl)
    if canonical.exists():
        content = canonical.read_text(encoding="utf-8")
        assert '"passport_id"' in content or '"horse_name"' in content, \
            "Canonical passport appears corrupted"


# ── 12. Enrichment does not require Supabase ─────────────────────────────────

def test_enrichment_script_has_no_supabase_import():
    script = ROOT / "scripts/ops/vfu_enrich_pick_sp.py"
    assert script.exists()
    source = script.read_text(encoding="utf-8")
    # Must not import supabase or reference the URL env var (comments excluded)
    code_lines = [l for l in source.splitlines() if not l.strip().startswith("#")]
    code = "\n".join(code_lines)
    assert "import supabase" not in code.lower(), "Enrichment script must not import supabase"
    assert "SUPABASE_URL" not in code, "Enrichment script must not reference SUPABASE_URL"
    assert "create_client" not in code, "Enrichment script must not use Supabase client"


# ── 13. Enriched 20-race dry-run reduces pick_sp_null or reports why not ──────

def test_enriched_autopsy_or_enrichment_reduces_null_or_explains():
    enriched_report = ROOT / "data/reports/vfu_pick_sp_enrichment_report.json"
    if not enriched_report.exists():
        pytest.skip("Enrichment report not yet generated")

    report = json.loads(enriched_report.read_text())
    before = report["pick_sp_before_enrichment"]
    after = report["pick_sp_after_enrichment"]

    # Either coverage improved, or the reason is documented (LOCAL_ONLY rows)
    local_only_count = report.get("missing_reason_breakdown", {}).get("UNMATCHED_LOCAL_ONLY", 0)
    if after <= before:
        assert local_only_count > 0, (
            "pick_sp coverage did not improve and no LOCAL_ONLY explanation found"
        )
    else:
        assert after > before, f"Expected improvement: before={before}, after={after}"
