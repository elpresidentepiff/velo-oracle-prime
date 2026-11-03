from scripts.audit.learning_loop_closure_audit import canonical_result_race_ids


def test_modern_horse_runs_close_verdicts_without_legacy_runner_results():
    combined, canonical, legacy = canonical_result_race_ids(
        [{"race_id": "legacy-1"}],
        [{"race_id": "930447"}, {"race_id": "931179"}],
    )

    assert canonical == {"930447", "931179"}
    assert legacy == {"legacy-1"}
    assert combined == {"legacy-1", "930447", "931179"}
