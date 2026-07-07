import json

from scripts.ops.expand_confidence_flood_evidence import (
    BASELINE_FALSE_GREEN_SET,
    BASELINE_SIGMA_DATES_SCANNED,
    build_guard_flags,
    compute_guard_coverage,
    discover_sigma_result_paths,
    load_and_diagnose,
    market_outlier_band,
    run_evidence_expansion,
    sample_capture_quality_status,
)


def test_baseline_false_green_set_matches_vfu22():
    assert BASELINE_FALSE_GREEN_SET == {
        "2026-06-09",
        "2026-06-16",
        "2026-06-18",
        "2026-06-19",
        "2026-06-23",
        "2026-06-30",
    }


def test_discover_sigma_result_paths_finds_local_corpus():
    paths = discover_sigma_result_paths()
    assert len(paths) >= BASELINE_SIGMA_DATES_SCANNED


def test_discover_sigma_result_paths_dedupes_by_date(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "sigma_results_2026_01_01.json").write_text('{"date": "2026-01-01"}')
    (b / "sigma_results_2026_01_01.json").write_text('{"date": "2026-01-01", "duplicate": true}')
    (b / "sigma_results_2026_01_02.json").write_text('{"date": "2026-01-02"}')

    import scripts.ops.expand_confidence_flood_evidence as mod
    original_dir = mod.SIGMA_RESULTS_DIR
    mod.SIGMA_RESULTS_DIR = a
    try:
        paths = discover_sigma_result_paths(extra_dirs=[str(b)])
    finally:
        mod.SIGMA_RESULTS_DIR = original_dir

    dates = sorted(p.split("sigma_results_")[-1].replace(".json", "") for p in paths)
    assert dates == ["2026_01_01", "2026_01_02"]
    # The date present in both dirs should resolve to dir 'a' (first found), not be duplicated.
    assert len(paths) == 2


def test_load_and_diagnose_missing_vp_rows(tmp_path):
    f = tmp_path / "sigma_results_2026_01_01.json"
    f.write_text(json.dumps({"date": "2026-01-01", "sigma_status": "PASS", "sr": 0.2, "rows": []}))
    result = load_and_diagnose(str(f))
    assert result["vp_gate_class"] == "UNCLASSIFIED"
    assert result["gap_band"] == "UNKNOWN"
    assert result["false_green_confirmed"] is False


def test_load_and_diagnose_green_false_green_day(tmp_path):
    rows = [{"velo_prime_prob": 0.45} for _ in range(6)]
    payload = {
        "date": "2026-01-01",
        "sigma_status": "PASS",
        "sr": 0.15,
        "avg_hit_prob": 0.30,
        "avg_miss_prob": 0.32,
        "rows": rows,
    }
    f = tmp_path / "sigma_results_2026_01_01.json"
    f.write_text(json.dumps(payload))
    result = load_and_diagnose(str(f))
    assert result["vp_gate_class"] == "GREEN"
    assert result["false_green_confirmed"] is True
    assert result["gap_band"] == "INVERTED"


def test_sample_capture_quality_status_flagged_on_partial():
    row = {"sigma_status": "PARTIAL_RESULTS_DIAGNOSTIC_ONLY", "avg_hit_prob": 0.3, "avg_miss_prob": 0.3, "day_sr": 0.2, "n_races": 20}
    assert sample_capture_quality_status(row) == "FLAGGED"


def test_sample_capture_quality_status_clean():
    row = {"sigma_status": "PASS", "avg_hit_prob": 0.3, "avg_miss_prob": 0.3, "day_sr": 0.2, "n_races": 20}
    assert sample_capture_quality_status(row) == "CLEAN"


def test_market_outlier_band_outlier():
    true_green_rows = [{"winner_sp_median": 2.0}, {"winner_sp_median": 2.5}, {"winner_sp_median": 3.0}]
    row = {"winner_sp_median": 10.0}
    assert market_outlier_band(row, true_green_rows) == "OUTLIER"


def test_market_outlier_band_within_range():
    true_green_rows = [{"winner_sp_median": 2.0}, {"winner_sp_median": 2.5}, {"winner_sp_median": 3.0}]
    row = {"winner_sp_median": 2.4}
    assert market_outlier_band(row, true_green_rows) == "WITHIN_RANGE"


def test_market_outlier_band_insufficient_evidence():
    assert market_outlier_band({"winner_sp_median": None}, []) == "INSUFFICIENT_EVIDENCE"


def test_build_guard_flags_gap_collapse_only():
    row = {"gap_band": "COMPRESSED", "n_vp_ge_040_share": 0.3, "n_vp_ge_045_share": 0.2}
    true_green_rows = [
        {"n_vp_ge_040_share": 0.3, "n_vp_ge_045_share": 0.2},
        {"n_vp_ge_040_share": 0.35, "n_vp_ge_045_share": 0.25},
        {"n_vp_ge_040_share": 0.4, "n_vp_ge_045_share": 0.3},
    ]
    flags = build_guard_flags(row, true_green_rows)
    assert flags["gap_collapse_guard"] is True
    assert flags["combined_overlay"] is True


def test_build_guard_flags_threshold_flood_only():
    row = {"gap_band": "HEALTHY", "n_vp_ge_040_share": 0.9, "n_vp_ge_045_share": 0.9}
    true_green_rows = [
        {"n_vp_ge_040_share": 0.3, "n_vp_ge_045_share": 0.2},
        {"n_vp_ge_040_share": 0.35, "n_vp_ge_045_share": 0.25},
        {"n_vp_ge_040_share": 0.4, "n_vp_ge_045_share": 0.3},
    ]
    flags = build_guard_flags(row, true_green_rows)
    assert flags["gap_collapse_guard"] is False
    assert flags["threshold_flood_guard"] is True
    assert flags["combined_overlay"] is True


def test_build_guard_flags_neither():
    row = {"gap_band": "HEALTHY", "n_vp_ge_040_share": 0.32, "n_vp_ge_045_share": 0.21}
    true_green_rows = [
        {"n_vp_ge_040_share": 0.3, "n_vp_ge_045_share": 0.2},
        {"n_vp_ge_040_share": 0.35, "n_vp_ge_045_share": 0.25},
        {"n_vp_ge_040_share": 0.4, "n_vp_ge_045_share": 0.3},
    ]
    flags = build_guard_flags(row, true_green_rows)
    assert flags["gap_collapse_guard"] is False
    assert flags["threshold_flood_guard"] is False
    assert flags["combined_overlay"] is False


def test_compute_guard_coverage_perfect_combined_recall():
    diagnosed = [
        {"vp_gate_class": "GREEN", "date": "fg1", "false_green_confirmed": True, "guard_flags": {"gap_collapse_guard": True, "threshold_flood_guard": False, "combined_overlay": True}},
        {"vp_gate_class": "GREEN", "date": "tg1", "false_green_confirmed": False, "guard_flags": {"gap_collapse_guard": False, "threshold_flood_guard": False, "combined_overlay": False}},
    ]
    coverage = compute_guard_coverage(diagnosed, {"fg1"})
    assert coverage["Gap-Collapse Guard"]["true_positives"] == 1
    assert coverage["Gap-Collapse Guard"]["false_positives"] == 0
    assert coverage["Combined Green-Day Risk Overlay"]["coverage_rate"] == 1.0


def test_run_evidence_expansion_reproduces_baseline_exactly():
    output = run_evidence_expansion()
    check = output["reproduction_check"]
    assert check["removed_false_green_dates"] == []
    assert set(BASELINE_FALSE_GREEN_SET).issubset(set(check["unchanged_false_green_dates"]))
    assert check["baseline_fully_reproduced"] is True


def test_run_evidence_expansion_reports_expansion_status():
    output = run_evidence_expansion()
    assert isinstance(output["expansion_succeeded"], bool)
    assert output["sigma_dates_scanned"] >= BASELINE_SIGMA_DATES_SCANNED


def test_run_evidence_expansion_summary_has_required_metrics():
    output = run_evidence_expansion()
    summary = output["evidence_expansion_summary"]
    required_keys = {
        "sigma_dates_scanned", "green_days", "false_green_days", "false_green_rate",
        "true_green_days", "gap_collapse_false_green", "healthy_gap_false_green",
        "threshold_flood_false_green", "market_environment_false_green",
        "sample_capture_quality_false_green", "unresolved_false_green",
    }
    assert required_keys.issubset(summary.keys())


def test_run_evidence_expansion_guard_coverage_has_required_guards():
    output = run_evidence_expansion()
    assert set(output["guard_coverage"].keys()) == {
        "Gap-Collapse Guard", "Threshold-Flood Guard", "Combined Green-Day Risk Overlay",
    }


def test_run_evidence_expansion_output_is_json_serializable():
    output = run_evidence_expansion()
    json.dumps(output)


def test_run_evidence_expansion_never_confirms_false_green_on_non_green_day():
    output = run_evidence_expansion()
    for row in output["per_date_diagnostics"]:
        if row["vp_gate_class"] != "GREEN":
            assert row["false_green_confirmed"] is False


def test_run_evidence_expansion_combined_overlay_never_worse_recall_than_individual_guards():
    output = run_evidence_expansion()
    coverage = output["guard_coverage"]
    combined_tp = coverage["Combined Green-Day Risk Overlay"]["true_positives"]
    assert combined_tp >= coverage["Gap-Collapse Guard"]["true_positives"]
    assert combined_tp >= coverage["Threshold-Flood Guard"]["true_positives"]
