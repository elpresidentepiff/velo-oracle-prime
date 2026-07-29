import json

from scripts.ops.build_confidence_flood_root_cause_split import (
    KNOWN_FALSE_GREEN_SET,
    _quartiles,
    assign_cohort,
    classify_subtypes,
    cohort_comparison,
    enrich_results,
    run_root_cause_split,
    threshold_pressure_band,
)


def test_known_false_green_set_matches_vfu22():
    assert KNOWN_FALSE_GREEN_SET == {
        "2026-06-09",
        "2026-06-16",
        "2026-06-18",
        "2026-06-19",
        "2026-06-23",
        "2026-06-30",
    }


def test_quartiles_basic():
    q = _quartiles([1, 2, 3, 4, 5, 6, 7, 8])
    assert q["min"] == 1
    assert q["max"] == 8
    assert q["median"] == 4.5


def test_quartiles_empty_returns_none():
    assert _quartiles([]) is None
    assert _quartiles([None, None]) is None


def test_threshold_pressure_band_above_p75():
    q = {"min": 0.1, "median": 0.4, "p75": 0.5, "max": 0.6}
    assert threshold_pressure_band(0.55, q) == "ABOVE_TRUE_GREEN_P75"


def test_threshold_pressure_band_above_median():
    q = {"min": 0.1, "median": 0.4, "p75": 0.5, "max": 0.6}
    assert threshold_pressure_band(0.45, q) == "ABOVE_TRUE_GREEN_MEDIAN"


def test_threshold_pressure_band_within_range():
    q = {"min": 0.1, "median": 0.4, "p75": 0.5, "max": 0.6}
    assert threshold_pressure_band(0.2, q) == "WITHIN_TRUE_GREEN_RANGE"


def test_threshold_pressure_band_below_median():
    q = {"min": 0.1, "median": 0.4, "p75": 0.5, "max": 0.6}
    assert threshold_pressure_band(0.05, q) == "BELOW_TRUE_GREEN_MEDIAN"


def test_threshold_pressure_band_insufficient_cohort():
    assert threshold_pressure_band(0.3, None) == "TRUE_GREEN_COHORT_INSUFFICIENT"
    assert threshold_pressure_band(None, {"min": 0, "median": 0, "p75": 0, "max": 0}) == "TRUE_GREEN_COHORT_INSUFFICIENT"


def test_assign_cohort_false_green():
    assert assign_cohort({"date": "2026-06-09", "vp_gate_class": "GREEN"}) == "FALSE_GREEN_DAYS"


def test_assign_cohort_true_green():
    assert assign_cohort({"date": "2026-06-05", "vp_gate_class": "GREEN"}) == "TRUE_GREEN_DAYS"


def test_assign_cohort_non_green():
    assert assign_cohort({"date": "2026-05-24", "vp_gate_class": "RED"}) == "NON_GREEN_DAYS"
    assert assign_cohort({"date": "2026-06-02", "vp_gate_class": "AMBER"}) == "NON_GREEN_DAYS"
    assert assign_cohort({"date": "2026-05-26", "vp_gate_class": "UNCLASSIFIED"}) == "NON_GREEN_DAYS"


def _row(date, gap_band, n40_share=0.3, n45_share=0.2, winner_sp=2.0, sigma_status="PASS",
         avg_hit_prob=0.3, avg_miss_prob=0.3, day_sr=0.2, n_races=30):
    return {
        "date": date,
        "gap_band": gap_band,
        "n_vp_ge_040_share": n40_share,
        "n_vp_ge_045_share": n45_share,
        "winner_sp_median": winner_sp,
        "sigma_status": sigma_status,
        "avg_hit_prob": avg_hit_prob,
        "avg_miss_prob": avg_miss_prob,
        "day_sr": day_sr,
        "n_races": n_races,
    }


def _true_green_cohort():
    # Small synthetic true-green cohort for isolated subtype-classification tests.
    return [
        _row("2026-06-a", "HEALTHY", n40_share=0.30, n45_share=0.20, winner_sp=2.0),
        _row("2026-06-b", "HEALTHY", n40_share=0.35, n45_share=0.22, winner_sp=2.2),
        _row("2026-06-c", "HEALTHY", n40_share=0.40, n45_share=0.25, winner_sp=2.5),
        _row("2026-06-d", "WEAK", n40_share=0.45, n45_share=0.28, winner_sp=2.8),
    ]


def test_classify_subtypes_gap_collapse_primary():
    row = _row("2026-06-09", "COMPRESSED")
    primary, secondary, notes = classify_subtypes(row, _true_green_cohort())
    assert primary == "GAP_COLLAPSE_FALSE_GREEN"


def test_classify_subtypes_healthy_gap_primary():
    row = _row("2026-06-18", "HEALTHY")
    primary, secondary, notes = classify_subtypes(row, _true_green_cohort())
    assert primary == "HEALTHY_GAP_FALSE_GREEN"


def test_classify_subtypes_inverted_is_gap_collapse():
    row = _row("2026-06-23", "INVERTED")
    primary, secondary, notes = classify_subtypes(row, _true_green_cohort())
    assert primary == "GAP_COLLAPSE_FALSE_GREEN"


def test_classify_subtypes_threshold_flood_detected_above_p75():
    # true-green n40_share cohort: [0.30, 0.35, 0.40, 0.45] -> p75 ~ 0.40-0.45
    row = _row("2026-06-18", "HEALTHY", n40_share=0.90, n45_share=0.90)
    primary, secondary, notes = classify_subtypes(row, _true_green_cohort())
    assert "THRESHOLD_FLOOD_FALSE_GREEN" in secondary


def test_classify_subtypes_no_threshold_flood_when_within_range():
    row = _row("2026-06-18", "HEALTHY", n40_share=0.32, n45_share=0.21)
    primary, secondary, notes = classify_subtypes(row, _true_green_cohort())
    assert "THRESHOLD_FLOOD_FALSE_GREEN" not in secondary


def test_classify_subtypes_market_environment_flagged_on_true_outlier():
    # true-green winner_sp cohort range [2.0, 2.8]; 10.0 is a genuine outlier
    row = _row("2026-06-16", "COMPRESSED", winner_sp=10.0)
    primary, secondary, notes = classify_subtypes(row, _true_green_cohort())
    assert "MARKET_ENVIRONMENT_FALSE_GREEN" in secondary


def test_classify_subtypes_market_environment_insufficient_when_not_outlier():
    row = _row("2026-06-16", "COMPRESSED", winner_sp=2.3)
    primary, secondary, notes = classify_subtypes(row, _true_green_cohort())
    assert "MARKET_ENVIRONMENT_INSUFFICIENT_EVIDENCE" in secondary
    assert "MARKET_ENVIRONMENT_FALSE_GREEN" not in secondary


def test_classify_subtypes_sample_capture_quality_flagged_on_partial_status():
    row = _row("2026-06-09", "COMPRESSED", sigma_status="PARTIAL_RESULTS_DIAGNOSTIC_ONLY")
    primary, secondary, notes = classify_subtypes(row, _true_green_cohort())
    assert "SAMPLE_CAPTURE_QUALITY_FALSE_GREEN" in secondary


def test_classify_subtypes_sample_capture_quality_not_flagged_when_clean():
    row = _row("2026-06-09", "COMPRESSED", sigma_status="PASS")
    primary, secondary, notes = classify_subtypes(row, _true_green_cohort())
    assert "SAMPLE_CAPTURE_QUALITY_FALSE_GREEN" not in secondary


def test_classify_subtypes_unresolved_when_healthy_gap_and_no_positive_secondary():
    # HEALTHY gap, within-range threshold, non-outlier SP, clean sample -> nothing explains it
    row = _row("2026-06-18", "HEALTHY", n40_share=0.32, n45_share=0.21, winner_sp=2.3)
    primary, secondary, notes = classify_subtypes(row, _true_green_cohort())
    assert primary == "HEALTHY_GAP_FALSE_GREEN"
    assert "UNRESOLVED_FALSE_GREEN" in secondary


def test_classify_subtypes_not_unresolved_when_positive_secondary_found():
    row = _row("2026-06-18", "HEALTHY", n40_share=0.95, n45_share=0.95)
    primary, secondary, notes = classify_subtypes(row, _true_green_cohort())
    assert "UNRESOLVED_FALSE_GREEN" not in secondary


def test_enrich_results_returns_shares_and_row_level_fields():
    results = enrich_results()
    by_date = {r["date"]: r for r in results}
    r = by_date["2026-06-09"]
    assert r["n_vp_ge_040_share"] is not None
    assert 0 <= r["n_vp_ge_040_share"] <= 1
    assert "miss_class_breakdown" in r


def test_cohort_comparison_produces_three_cohorts():
    results = enrich_results()
    summary, cohorts = cohort_comparison(results)
    assert set(summary.keys()) == {"FALSE_GREEN_DAYS", "TRUE_GREEN_DAYS", "NON_GREEN_DAYS"}
    assert summary["FALSE_GREEN_DAYS"]["count"] == 6


def test_run_root_cause_split_classifies_all_six_known_dates():
    output = run_root_cause_split()
    check = output["reproduction_check"]
    assert check["known_false_green_set_loaded"] is True
    assert check["known_false_green_set_size"] == 6
    assert check["all_six_classified"] is True
    assert check["missing_from_classification"] == []


def test_run_root_cause_split_gap_collapse_days_match_expected():
    output = run_root_cause_split()
    by_date = {r["date"]: r for r in output["classified_false_green_days"]}
    for d in ("2026-06-09", "2026-06-16", "2026-06-23", "2026-06-30"):
        assert by_date[d]["primary_subtype"] == "GAP_COLLAPSE_FALSE_GREEN"


def test_run_root_cause_split_healthy_gap_days_match_expected():
    output = run_root_cause_split()
    by_date = {r["date"]: r for r in output["classified_false_green_days"]}
    for d in ("2026-06-18", "2026-06-19"):
        assert by_date[d]["primary_subtype"] == "HEALTHY_GAP_FALSE_GREEN"


def test_run_root_cause_split_output_is_json_serializable():
    output = run_root_cause_split()
    json.dumps(output)


def test_run_root_cause_split_no_secondary_subtype_is_a_cure_or_gate_change():
    # Guard against scope creep: subtype labels must never imply a gate/criteria change.
    output = run_root_cause_split()
    forbidden_terms = ("GATE_CHANGE", "THRESHOLD_CHANGE", "PROMOTE", "CURE")
    for row in output["classified_false_green_days"]:
        for term in forbidden_terms:
            assert term not in row["primary_subtype"]
            for s in row["secondary_subtypes"]:
                assert term not in s
