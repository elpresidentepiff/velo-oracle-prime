from __future__ import annotations

import json

from new_build_velo.spine import RPR_POLICY, TRUST_POLICY, ingest_date, learn, process_date, run_all


def test_ingest_process_real_archive_date_is_archive_only() -> None:
    ingest = ingest_date("2026-05-25", execute=False)
    process = process_date("2026-05-25", execute=False)

    assert ingest["status"] == "PASS"
    assert ingest["runner_count"] == 59
    assert ingest["velo_scoring_allowed"] is False
    assert ingest["rpr_policy"] == RPR_POLICY
    assert process["status"] == "PASS"
    assert process["velo_scoring_allowed"] is False
    assert "HUMAN_CONTEXT_AVAILABLE" in process["flag_counts"]


def test_learning_uses_sandbox_only_when_outcomes_missing() -> None:
    report = learn(from_date="2026-05-25", to_date="2026-05-29", execute=False)

    assert report["status"] in {"OUTCOME_REQUIRED_BEFORE_LEARNING", "PASS"}
    assert report["live_velo_touched"] is False
    assert report["shadow_velo_touched"] is False
    assert report["state"]["learning_target"] == "new_build_sandbox_only"
    assert report["state"]["trust_policy"] == TRUST_POLICY


def test_run_all_replica_loop_has_no_live_shadow_side_effects() -> None:
    report = run_all(from_date="2026-05-25", to_date="2026-05-25", execute=False)
    encoded = json.dumps(report).lower()

    assert report["classification"] == "NEW_BUILD_REPLICA_LOOP_READY"
    assert report["live_velo_touched"] is False
    assert report["shadow_velo_touched"] is False
    assert "sentient_state_shadow_full_train_v1" not in encoded
    assert "run_prime_today" not in encoded
    assert "telegram" not in encoded

