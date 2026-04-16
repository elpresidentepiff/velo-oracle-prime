from __future__ import annotations

import json
from pathlib import Path

from app.runtime.doctrine_sidecar_common import (
    dedupe_latest_sigma_rows,
    doctrine_status_for_type,
    rpdc_coverage_metrics,
    rpdc_for_sigma_row,
    rpdc_selection_lookup,
    truth_by_race,
    truth_for_sigma_row,
    truth_lookup,
)
from scripts import (
    generate_doctrine_evidence_board,
    run_contradiction_miner,
    run_longshot_regime_simulation,
)


def _cleanup(path: Path) -> None:
    path.unlink(missing_ok=True)
    json_path = path.with_suffix(".json")
    json_path.unlink(missing_ok=True)


def test_dedupe_latest_sigma_rows_keeps_newest_created_at():
    rows = [
        {"race_id": "race-1", "horse_id": "h1", "created_at": "2026-04-15T09:00:00+00:00", "outcome": "MISS"},
        {"race_id": "race-1", "horse_id": "h1", "created_at": "2026-04-15T10:00:00+00:00", "outcome": "WIN"},
        {"race_id": "race-2", "horse_id": "h2", "created_at": "2026-04-15T11:00:00+00:00", "outcome": "PLACED"},
    ]

    deduped = dedupe_latest_sigma_rows(rows)
    by_race = {row["race_id"]: row for row in deduped}

    assert len(deduped) == 2
    assert by_race["race-1"]["outcome"] == "WIN"
    assert by_race["race-2"]["outcome"] == "PLACED"


def test_truth_by_race_uses_latest_generated_at():
    rows = [
        {
            "race_id": "race-1",
            "generated_at": "2026-04-15T09:00:00+00:00",
            "blocker_fired": False,
            "blocker_type": None,
        },
        {
            "race_id": "race-1",
            "generated_at": "2026-04-15T10:00:00+00:00",
            "blocker_fired": True,
            "blocker_type": "longshot_block_allowed",
        },
    ]

    truth = truth_by_race(rows)

    assert truth["race-1"]["blocker_fired"] is True
    assert truth["race-1"]["blocker_type"] == "longshot_block_allowed"


def test_rpdc_for_sigma_row_requires_matching_horse():
    sigma_row = {"race_id": "race-1", "horse_id": "horse-a"}
    rpdc_rows = rpdc_selection_lookup(
        [
            {
                "race_id": "race-1",
                "horse_id": "horse-b",
                "generated_at": "2026-04-15T09:00:00+00:00",
                "rpdc_cash_window_flag": True,
                "rpdc_release_score": 4.2,
                "rpdc_tag_count": 2,
            }
        ]
    )

    rpdc = rpdc_for_sigma_row(sigma_row, rpdc_rows)

    assert rpdc["has_cash_window"] is False
    assert rpdc["max_rpdc_release_score"] == 0.0


def test_lineage_prefers_doctrine_event_id_before_fallback():
    sigma_row = {
        "race_id": "race-1",
        "horse_id": "horse-a",
        "doctrine_event_id": "11111111-1111-1111-1111-111111111111",
    }
    truth_rows = truth_lookup(
        [
            {
                "race_id": "race-1",
                "doctrine_event_id": "11111111-1111-1111-1111-111111111111",
                "generated_at": "2026-04-15T12:00:00+00:00",
                "blocker_type": "event_match",
            },
            {
                "race_id": "race-1",
                "doctrine_event_id": None,
                "generated_at": "2026-04-15T11:00:00+00:00",
                "blocker_type": "fallback_match",
            },
        ]
    )
    rpdc_rows = rpdc_selection_lookup(
        [
            {
                "race_id": "race-1",
                "doctrine_event_id": "11111111-1111-1111-1111-111111111111",
                "horse_id": "horse-a",
                "generated_at": "2026-04-15T12:00:00+00:00",
                "rpdc_cash_window_flag": True,
                "rpdc_release_score": 4.0,
                "rpdc_tag_count": 2,
            },
            {
                "race_id": "race-1",
                "doctrine_event_id": None,
                "horse_id": "horse-a",
                "generated_at": "2026-04-15T11:00:00+00:00",
                "rpdc_cash_window_flag": False,
                "rpdc_release_score": 1.0,
                "rpdc_tag_count": 1,
            },
        ]
    )
    stats: dict[str, int] = {}

    truth = truth_for_sigma_row(sigma_row, truth_rows, stats=stats)
    rpdc = rpdc_for_sigma_row(sigma_row, rpdc_rows, stats=stats)

    assert truth["blocker_type"] == "event_match"
    assert rpdc["has_cash_window"] is True
    assert stats["truth_event_matches"] == 1
    assert stats["rpdc_event_matches"] == 1


def test_doctrine_status_mapping_defaults_to_review_for_unmapped_types():
    doctrine_rows = [
        {"doctrine_key": "a_tier_weak_place_watch", "status": "watch"},
        {"doctrine_key": "longshot_block_allowed_aw_watch", "status": "watch"},
    ]

    assert doctrine_status_for_type("a_tier_weak_place_support", doctrine_rows) == "watch"
    assert doctrine_status_for_type("blocker_fired_horse_won", doctrine_rows) == "review"


def test_rpdc_coverage_metrics_reflect_sparse_candidate_surface():
    sigma_rows = [
        {"race_id": "race-1", "doctrine_event_id": "event-1", "horse_id": "horse-a"},
        {"race_id": "race-2", "doctrine_event_id": "event-2", "horse_id": None},
        {"race_id": "race-3", "doctrine_event_id": "event-3", "horse_id": "horse-c"},
    ]
    rpdc_rows = [
        {
            "race_id": "race-1",
            "doctrine_event_id": "event-1",
            "horse_id": "horse-a",
            "generated_at": "2099-04-15T12:00:00+00:00",
        },
        {
            "race_id": "race-2",
            "doctrine_event_id": "event-2",
            "horse_id": "other-horse",
            "generated_at": "2099-04-15T12:00:00+00:00",
        },
    ]

    metrics = rpdc_coverage_metrics(sigma_rows, rpdc_rows)

    assert metrics == {
        "reviewed_sigma_rows": 3,
        "reviewed_sigma_rows_with_horse_id": 2,
        "reviewed_sigma_rows_in_rpdc_covered_events": 2,
        "reviewed_sigma_rows_with_exact_rpdc_match": 1,
    }


def test_board_and_miner_align_on_deduped_contradiction_counts(monkeypatch):
    target_date = "2099-04-15"
    sigma_rows = [
        {
            "race_id": "race-a",
            "doctrine_event_id": "event-a",
            "horse_id": "horse-a",
            "decision_tier": "A",
            "confidence_level": "normal",
            "verdict_score": 0.62,
            "outcome": "WIN",
            "top_pick_position": 3,
            "miss_reason": "late_head",
            "track": "Southwell (AW)",
            "created_at": "2099-04-15T09:00:00+00:00",
        },
        {
            "race_id": "race-a",
            "doctrine_event_id": "event-a",
            "horse_id": "horse-a",
            "decision_tier": "A",
            "confidence_level": "low",
            "verdict_score": 0.61,
            "outcome": "MISS",
            "top_pick_position": 4,
            "miss_reason": "older_duplicate",
            "track": "Southwell (AW)",
            "created_at": "2099-04-15T08:00:00+00:00",
        },
        {
            "race_id": "race-b",
            "doctrine_event_id": "event-b",
            "horse_id": "horse-b",
            "decision_tier": "C",
            "confidence_level": "normal",
            "verdict_score": 0.25,
            "outcome": "MISS",
            "top_pick_position": 1,
            "miss_reason": "wrong_horse_should_not_attach_rpdc",
            "track": "Kempton (AW)",
            "created_at": "2099-04-15T09:30:00+00:00",
        },
        {
            "race_id": "race-c",
            "doctrine_event_id": "event-c",
            "horse_id": "horse-c",
            "decision_tier": "C",
            "confidence_level": "normal",
            "verdict_score": 0.21,
            "outcome": "PLACED",
            "top_pick_position": 1,
            "miss_reason": "low_model_real_rpdc",
            "track": "Wolverhampton (AW)",
            "created_at": "2099-04-15T10:00:00+00:00",
        },
    ]
    truth_rows = [
        {"race_id": "race-a", "race_date": target_date, "generated_at": "2099-04-15T11:00:00+00:00", "blocker_fired": False},
        {"race_id": "race-b", "race_date": target_date, "generated_at": "2099-04-15T11:00:00+00:00", "blocker_fired": False},
        {"race_id": "race-c", "race_date": target_date, "generated_at": "2099-04-15T11:00:00+00:00", "blocker_fired": False},
    ]
    rpdc_rows = [
        {
            "race_id": "race-b",
            "doctrine_event_id": "event-b",
            "horse_id": "other-horse",
            "run_date": target_date,
            "generated_at": "2099-04-15T11:30:00+00:00",
            "rpdc_cash_window_flag": True,
            "rpdc_release_score": 3.5,
            "rpdc_tag_count": 1,
        },
        {
            "race_id": "race-c",
            "doctrine_event_id": "event-c",
            "horse_id": "horse-c",
            "run_date": target_date,
            "generated_at": "2099-04-15T11:30:00+00:00",
            "rpdc_cash_window_flag": True,
            "rpdc_release_score": 4.1,
            "rpdc_tag_count": 2,
        },
    ]
    doctrine_rows = [{"doctrine_key": "a_tier_weak_place_watch", "status": "watch"}]

    monkeypatch.setattr(generate_doctrine_evidence_board, "_fetch_sigma_audits", lambda _: list(sigma_rows))
    monkeypatch.setattr(generate_doctrine_evidence_board, "_fetch_race_truth_for_sigma_rows", lambda rows: list(truth_rows))
    monkeypatch.setattr(generate_doctrine_evidence_board, "_fetch_rpdc_tags_for_sigma_rows", lambda rows, review_date: [])
    monkeypatch.setattr(generate_doctrine_evidence_board, "_fetch_runner_release_for_sigma_rows", lambda rows: list(rpdc_rows))
    monkeypatch.setattr(generate_doctrine_evidence_board, "_fetch_doctrine_rows", lambda: list(doctrine_rows))
    monkeypatch.setattr(generate_doctrine_evidence_board, "_fetch_sigma_audits_window", lambda *_: list(sigma_rows))

    monkeypatch.setattr(run_contradiction_miner, "_require_doctrine_registry", lambda: None)
    monkeypatch.setattr(run_contradiction_miner, "_fetch_sigma_audits", lambda _: list(sigma_rows))
    monkeypatch.setattr(run_contradiction_miner, "_fetch_truth_for_sigma_rows", lambda rows: list(truth_rows))
    monkeypatch.setattr(run_contradiction_miner, "_fetch_rpdc_for_sigma_rows", lambda rows: list(rpdc_rows))

    board_path = generate_doctrine_evidence_board.generate(target_date)
    miner_path = run_contradiction_miner.generate(target_date)
    try:
        board_text = board_path.read_text(encoding="utf-8")
        miner_text = miner_path.read_text(encoding="utf-8")
    finally:
        _cleanup(board_path)
        _cleanup(miner_path)

    assert "| contradiction_count |" in board_text
    assert "| 2 |" in board_text
    assert "| reviewed_sigma_rows | reviewed_sigma_rows_with_horse_id | reviewed_sigma_rows_in_rpdc_covered_events | reviewed_sigma_rows_with_exact_event_horse_match |" in board_text
    assert "| 3 | 3 | 2 | 1 |" in board_text
    assert "| a_tier_weak_place_support | 1 |" in miner_text
    assert "| weak_model_strong_doctrine | 1 |" in miner_text
    assert "wrong_horse_should_not_attach_rpdc" not in miner_text
    assert "| 3 | 3 | 2 | 1 |" in miner_text
    assert "| 7d | a_tier_weak_place_support | 1 | 100.0 | 0.0 | 0.0 |" in board_text
    assert "| 7d | weak_model_strong_doctrine | 1 | 0.0 | 100.0 | 0.0 |" in board_text


def test_longshot_regime_simulation_uses_latest_truth_and_aw_filter(monkeypatch):
    target_date = "2099-04-16"
    sigma_rows = [
        {
            "race_id": "race-1",
            "horse_id": "horse-1",
            "outcome": "WIN",
            "decision_tier": "A",
            "miss_reason": "n/a",
            "track": "Kempton (AW)",
            "created_at": "2099-04-16T10:00:00+00:00",
        },
        {
            "race_id": "race-2",
            "horse_id": "horse-2",
            "outcome": "WIN",
            "decision_tier": "A",
            "miss_reason": "n/a",
            "track": "Chepstow",
            "created_at": "2099-04-16T10:00:00+00:00",
        },
    ]
    truth_rows = [
        {
            "race_id": "race-1",
            "race_date": target_date,
            "generated_at": "2099-04-16T09:00:00+00:00",
            "blocker_fired": False,
            "blocker_type": "longshot_block_allowed",
            "actual_winner_sp": 2.8,
        },
        {
            "race_id": "race-1",
            "race_date": target_date,
            "generated_at": "2099-04-16T11:00:00+00:00",
            "blocker_fired": True,
            "blocker_type": "longshot_block_allowed",
            "actual_winner_sp": 2.8,
        },
        {
            "race_id": "race-2",
            "race_date": target_date,
            "generated_at": "2099-04-16T11:00:00+00:00",
            "blocker_fired": True,
            "blocker_type": "longshot_block_allowed",
            "actual_winner_sp": 2.4,
        },
    ]

    monkeypatch.setattr(run_longshot_regime_simulation, "_fetch_sigma_window", lambda *_: list(sigma_rows))
    monkeypatch.setattr(run_longshot_regime_simulation, "_fetch_truth_for_sigma_rows", lambda rows: list(truth_rows))

    out_path = run_longshot_regime_simulation.generate(target_date, 30)
    json_path = out_path.with_suffix(".json")
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    finally:
        _cleanup(out_path)

    assert payload["regime_count"] == 1
    assert payload["winner_recovery_count"] == 1
    assert payload["false_positive_increase"] == 0
