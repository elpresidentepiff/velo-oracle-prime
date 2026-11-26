from src.velo.formfav_factual_ablation import build_factual_ablation_report


def _packet(*, eligible=True, raw=None, pace=None, klass=None, bias=None):
    return {
        "race_id": "race-1",
        "horse_id": "horse-1",
        "eligible_for_future_fit": eligible,
        "feature_families": {
            "formfav_raw_facts": raw if raw is not None else {"barrier": 3},
            "formfav_pace_context": pace if pace is not None else {"speedMap": {"earlySpeedIndex": 6}},
            "formfav_class_context": klass if klass is not None else {"raceClassFit": {"classDifference": 1}},
            "formfav_track_bias_context": bias if bias is not None else {"trackBias": {"biasStrength": 0.2}},
        },
    }


def test_factual_report_collects_families_without_scoring_or_fitting():
    report = build_factual_ablation_report(date="2026-11-26", packets=[_packet()])

    assert report["provider_predictions_consumed"] is False
    assert report["model_fit_performed"] is False
    assert report["summary"]["eligible_pre_off_packets"] == 1
    assert all(lane["state"] == "FORWARD_EVIDENCE_COLLECTING" for lane in report["lanes"])
    assert all(lane["active_shadow_use"] == "NOT_FITTED_SEPARATE_ABLATION" for lane in report["lanes"])


def test_factual_report_rejects_provider_prediction_fields():
    report = build_factual_ablation_report(
        date="2026-11-26", packets=[_packet(raw={"barrier": 3, "winProbability": 0.7})]
    )

    raw_lane = report["lanes"][0]
    assert raw_lane["state"] == "REJECTED_PROVIDER_OUTPUT_PRESENT"
    assert raw_lane["eligible_runners"] == 0
    assert report["summary"]["banned_provider_field_paths"]
