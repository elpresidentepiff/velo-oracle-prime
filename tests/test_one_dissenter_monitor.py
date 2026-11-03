from scripts.audit.monitor_one_dissenter_cohort import COMPARATORS, PRIME, build_cohort


def _row(model, horse, *, win=False, frame=False, sp=3.0):
    return {
        "run_date": "2026-11-04",
        "race_id": "race-1",
        "model_name": model,
        "horse": horse,
        "result_position": 1 if win else 4,
        "win": win,
        "frame": frame,
        "settled_sp_dec": sp,
        "official_evaluation_eligible": True,
    }


def test_exactly_one_dissenter_is_admitted():
    rows = [_row(PRIME, "Alpha", win=True, frame=True, sp=4.0)]
    rows.extend(_row(model, "Alpha" if index < 4 else "Beta") for index, model in enumerate(COMPARATORS))

    report = build_cohort(rows)

    assert report["eligible_races"] == 1
    assert report["wins"] == 1
    assert report["profit_1u"] == 3.0
    assert report["roi_pct"] == 300.0
    assert report["rows"][0]["dissenting_model"] == COMPARATORS[-1]


def test_unanimity_and_incomplete_sets_are_not_admitted():
    unanimous = [_row(PRIME, "Alpha")] + [_row(model, "Alpha") for model in COMPARATORS]
    incomplete = unanimous[:-1]

    assert build_cohort(unanimous)["eligible_races"] == 0
    assert build_cohort(incomplete)["incomplete_model_sets"] == 1
