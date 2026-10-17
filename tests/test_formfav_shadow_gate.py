from __future__ import annotations

from scripts.ops.run_formfav_uk_enhanced_shadow import _count_primary_in_scope, coverage_gate


def test_full_and_threshold_coverage_pass() -> None:
    assert coverage_gate(40, 40, 0.8) == (True, 1.0)
    assert coverage_gate(32, 40, 0.8)[0] is True


def test_partial_enrichment_fails_closed() -> None:
    ok, ratio = coverage_gate(3, 40, 0.8)
    assert ok is False and ratio == 0.075
    assert coverage_gate(31, 40, 0.8)[0] is False


def test_zero_enrichment_or_zero_primary_never_passes() -> None:
    assert coverage_gate(0, 40, 0.8)[0] is False
    assert coverage_gate(0, 40, 0)[0] is False
    assert coverage_gate(5, 0, 0.8) == (False, 0.0)


def test_override_zero_accepts_any_nonzero_enrichment() -> None:
    assert coverage_gate(3, 40, 0)[0] is True


def test_primary_scope_accepts_country_or_rp_merged_region() -> None:
    races = [
        {"country": "GB"},
        {"region": "IRE"},
        {"country": "FR", "region": "FR"},
        {"country": "", "region": "GB"},
    ]

    assert _count_primary_in_scope(races, {"gb", "ie"}) == 3
