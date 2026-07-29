"""
Regression test for PASSPORT-INTENT-01-JULY06-RECOVERY-AND-SHADOW-WIRING Part A.

Guards the missing-passport recovery/classification audit: every runner on
the July 06 card must be accounted for exactly once (recovered, or
classified with cause), and the target must never be silently overstated
as 405/405 when genuine debutants are present.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "data" / "reports" / "july06_passport_rebuild_audit.json"
CSV_PATH = ROOT / "data" / "reports" / "july06_missing_passport_recovery.csv"


def _audit():
    if not AUDIT_PATH.exists():
        return None
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def test_audit_file_exists():
    assert AUDIT_PATH.exists(), "Run the July 06 passport recovery mission first"


def test_total_runners_is_405():
    audit = _audit()
    assert audit is not None
    assert audit["total_runners"] == 405


def test_before_coverage_matches_known_baseline():
    audit = _audit()
    assert audit["before_coverage"]["found"] == 188
    assert audit["before_coverage"]["coverage_pct"] == 46.42


def test_after_coverage_improved_and_is_internally_consistent():
    audit = _audit()
    before = audit["before_coverage"]["found"]
    after = audit["after_coverage"]["found"]
    assert after > before, "Recovery run must not decrease coverage"
    assert after == before + audit["recovered_count"]
    assert audit["after_coverage"]["total"] == audit["total_runners"]


def test_classification_counts_are_mutually_exclusive_and_exhaustive():
    audit = _audit()
    missing_total = audit["unrecoverable_count"]
    classified = (
        audit["unraced_or_no_form_history_count"]
        + audit["recoverable_profile_not_captured_count"]
        + audit["recoverable_identity_match_gap_count"]
        + audit["rp_profile_not_found_count"]
        + audit["parser_gap_count"]
        + audit["unknown_needs_manual_review_count"]
    )
    assert classified == missing_total, (
        "Every missing runner must fall into exactly one classification bucket"
    )
    assert audit["unknown_needs_manual_review_count"] == 0, (
        "Unknown/manual-review runners must be resolved before this mission is considered done"
    )


def test_does_not_falsely_claim_full_405_405_coverage():
    audit = _audit()
    assert audit["not_claiming_405_405"] is True
    assert audit["unraced_or_no_form_history_count"] > 0, (
        "Debutants are expected on any real card; a 0 count here would be suspicious, not a win"
    )


def test_csv_row_count_matches_total_runners():
    assert CSV_PATH.exists()
    import csv
    with CSV_PATH.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    audit = _audit()
    assert len(rows) == audit["total_runners"]


def test_csv_classification_values_are_known_categories():
    import csv
    with CSV_PATH.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    known = {
        "PRE_EXISTING_PASSPORT",
        "RECOVERED_PASSPORT_CREATED",
        "UNRACED_OR_NO_FORM_HISTORY",
        "RECOVERABLE_PROFILE_NOT_CAPTURED",
    }
    seen = {r["classification"] for r in rows}
    assert seen <= known, f"Unexpected classification values: {seen - known}"
