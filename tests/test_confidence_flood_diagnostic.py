import json

from scripts.ops.build_confidence_flood_diagnostic import (
    VFU_22_FALSE_GREEN_SET,
    check_vfu22_reproduction,
    classify_gap_band,
    classify_gate,
    diagnose_date,
    run_diagnostic,
)


def test_classify_gate_green():
    assert classify_gate(avg_vp=0.40, n_40=6, n_45=3) == "GREEN"


def test_classify_gate_amber():
    assert classify_gate(avg_vp=0.30, n_40=2, n_45=0) == "AMBER"


def test_classify_gate_red_low_avg_vp():
    assert classify_gate(avg_vp=0.10, n_40=0, n_45=0) == "RED"


def test_classify_gate_red_zero_n40():
    assert classify_gate(avg_vp=0.40, n_40=0, n_45=0) == "RED"


def test_classify_gate_unclassified():
    assert classify_gate(avg_vp=0.32, n_40=6, n_45=1) == "UNCLASSIFIED"


def test_classify_gap_band_inverted():
    assert classify_gap_band(-0.05) == "INVERTED"


def test_classify_gap_band_compressed():
    assert classify_gap_band(0.02) == "COMPRESSED"
    assert classify_gap_band(0.0) == "COMPRESSED"


def test_classify_gap_band_weak():
    assert classify_gap_band(0.06) == "WEAK"


def test_classify_gap_band_healthy():
    assert classify_gap_band(0.10) == "HEALTHY"


def test_classify_gap_band_unknown_when_none():
    assert classify_gap_band(None) == "UNKNOWN"


def _payload(sr, avg_hit, avg_miss, vps, sigma_status="PASS", date="2026-01-01"):
    rows = [{"velo_prime_prob": v} for v in vps]
    return {
        "date": date,
        "sigma_status": sigma_status,
        "sr": sr,
        "avg_hit_prob": avg_hit,
        "avg_miss_prob": avg_miss,
        "rows": rows,
    }


def test_diagnose_date_confidence_flood_confirmed_false_green():
    # avg_vp=0.40, n_40=6 (>=5), n_45=4 (>=2) -> GREEN. gap = 0.30-0.32 = -0.02 -> INVERTED.
    # sr below 0.243 baseline -> false_green_confirmed True.
    vps = [0.45, 0.45, 0.45, 0.45, 0.40, 0.40]
    payload = _payload(sr=0.15, avg_hit=0.30, avg_miss=0.32, vps=vps)
    result = diagnose_date(payload, "sigma_results_2026_01_01.json")
    assert result["vp_gate_class"] == "GREEN"
    assert result["gap_band"] == "INVERTED"
    assert result["confidence_flood_flag"] is True
    assert result["false_green_confirmed"] is True


def test_diagnose_date_true_green_healthy_gap_not_flagged():
    vps = [0.45, 0.45, 0.45, 0.45, 0.40, 0.40]
    payload = _payload(sr=0.35, avg_hit=0.55, avg_miss=0.35, vps=vps)
    result = diagnose_date(payload, "sigma_results_2026_01_01.json")
    assert result["vp_gate_class"] == "GREEN"
    assert result["gap_band"] == "HEALTHY"
    assert result["confidence_flood_flag"] is False
    assert result["false_green_confirmed"] is False


def test_diagnose_date_red_day_never_flood_flagged_even_with_bad_gap():
    vps = [0.10, 0.15, 0.05]
    payload = _payload(sr=0.10, avg_hit=0.10, avg_miss=0.20, vps=vps)
    result = diagnose_date(payload, "sigma_results_2026_01_01.json")
    assert result["vp_gate_class"] == "RED"
    assert result["gap_band"] == "INVERTED"
    # Not GREEN, so never flagged as confidence-flood or false-green regardless of gap.
    assert result["confidence_flood_flag"] is False
    assert result["false_green_confirmed"] is False


def test_diagnose_date_missing_vp_rows_returns_unclassified_unknown():
    payload = _payload(sr=0.20, avg_hit=None, avg_miss=None, vps=[])
    result = diagnose_date(payload, "sigma_results_2026_01_01.json")
    assert result["vp_gate_class"] == "UNCLASSIFIED"
    assert result["gap_band"] == "UNKNOWN"
    assert result["confidence_flood_flag"] is False
    assert result["false_green_confirmed"] is False


def test_diagnose_date_missing_hit_miss_prob_gap_unknown():
    vps = [0.45, 0.45, 0.45, 0.45, 0.40, 0.40]
    payload = _payload(sr=0.20, avg_hit=None, avg_miss=None, vps=vps)
    result = diagnose_date(payload, "sigma_results_2026_01_01.json")
    assert result["vp_gate_class"] == "GREEN"
    assert result["vp_discrimination_gap"] is None
    assert result["gap_band"] == "UNKNOWN"
    assert "gap band UNKNOWN" in result["notes"]


def test_diagnose_date_does_not_confirm_false_green_without_sr():
    vps = [0.45, 0.45, 0.45, 0.45, 0.40, 0.40]
    payload = _payload(sr=None, avg_hit=0.30, avg_miss=0.32, vps=vps)
    result = diagnose_date(payload, "sigma_results_2026_01_01.json")
    assert result["vp_gate_class"] == "GREEN"
    # sr is None -> false_green_confirmed must not be True (post-results-only rule)
    assert result["false_green_confirmed"] is False


def test_check_vfu22_reproduction_full_match():
    results = [
        {"date": d, "false_green_confirmed": True} for d in VFU_22_FALSE_GREEN_SET
    ]
    repro = check_vfu22_reproduction(results)
    assert repro["fully_reproduced"] is True
    assert repro["missing"] == []
    assert repro["extra_beyond_vfu22_set"] == []


def test_check_vfu22_reproduction_reports_missing():
    partial = sorted(VFU_22_FALSE_GREEN_SET)[:-1]
    results = [{"date": d, "false_green_confirmed": True} for d in partial]
    repro = check_vfu22_reproduction(results)
    assert repro["fully_reproduced"] is False
    assert len(repro["missing"]) == 1


def test_run_diagnostic_against_real_sigma_results_reproduces_vfu22_set():
    results = run_diagnostic()
    repro = check_vfu22_reproduction(results)
    assert repro["fully_reproduced"] is True, (
        f"VFU-23 diagnostic failed to reproduce VFU-22 false-green set: "
        f"missing={repro['missing']}"
    )


def test_run_diagnostic_never_sets_false_green_confirmed_on_non_green_day():
    results = run_diagnostic()
    for r in results:
        if r["vp_gate_class"] != "GREEN":
            assert r["false_green_confirmed"] is False


def test_run_diagnostic_output_is_json_serializable():
    results = run_diagnostic()
    json.dumps(results)
