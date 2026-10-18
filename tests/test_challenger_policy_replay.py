from __future__ import annotations

from dataclasses import replace

from src.intelligence.challenger_policy_replay import audit_midprice_actions, audit_new_build
from src.intelligence.historical_runner_crosswalk import CrosswalkRecord, CrosswalkReport, STATUS_COMPLETE


def _runner(horse_id: str, horse: str, prob: float, outcome: int) -> CrosswalkRecord:
    return CrosswalkRecord(
        race_date="2026-10-15",
        race_id="example-race",
        horse_id=horse_id,
        horse=horse,
        prediction_source="runner_prediction_snapshots.local_jsonl",
        prediction_time="2026-10-15T10:00:00Z",
        race_time="2026-10-15T14:00:00Z",
        rank=None,
        source_ordinal=None,
        velo_prime_prob=prob,
        sqpe_v17_prob=prob,
        model_probabilities={},
        market_decimal_price=3.5 if horse_id == "h1" else 5.0,
        market_price_field="sp_dec",
        result_position="1" if outcome else "2",
        outcome=outcome,
        non_runner=False,
        status=STATUS_COMPLETE,
        evidence_issues=[],
        evidence_hashes={"prediction": ["a"]},
    )


def _crosswalk() -> CrosswalkReport:
    return CrosswalkReport(
        records=[_runner("h1", "Prime Pick", 0.6, 0), _runner("h2", "Challenger", 0.4, 1)],
        counts_by_date={},
        source_counts={},
        source_hashes={},
        duplicate_snapshot_entries=0,
        duplicate_verdict_entries=0,
    )


def _readiness(when: str = "2026-10-15T09:00:00Z") -> dict:
    return {
        "target_date": "2026-10-15",
        "generated_at": when,
        "race_day_scorecards": [{
            "race_id": "example-race",
            "race_date": "2026-10-15",
            "lane_a_top3": [{"rank": 1, "horse": "Challenger", "prob": 0.55}],
            "lane_b_top3": [{"rank": 1, "horse": "Prime Pick", "prob": 0.60}],
        }],
    }


def _midprice(when: str = "2026-10-15T09:00:00Z") -> dict:
    return {
        "race_date": "2026-10-15", "race_id": "example-race",
        "created_at": when, "top_pick": "Prime Pick",
        "rule_version": "midprice_hunter_v2_2026_06_19",
        "shadow_action": "MIDPRICE_SUPPRESS_TOP",
        "live_scoring_changed": False, "execution_allowed": False,
    }


def test_new_build_top_pick_only_with_distinct_winner() -> None:
    result = audit_new_build([_readiness()], _crosswalk())
    assert result["lanes"]["lane_a"]["races"] == 1
    assert result["lanes"]["lane_a"]["wins"] == 1
    assert result["lanes"]["lane_a"]["prime_wins"] == 0
    assert result["lanes"]["lane_a"]["disagreements"] == 1
    assert result["lanes"]["lane_b"]["wins"] == 0
    assert result["exclusions"]["lane_c"]["TOP3_ABSENT"] == 1
    assert result["comparison"] == "TOP_PICK_ONLY_NOT_FULL_FIELD_PROBABILITY"
    assert result["promotion"] == "NOT_AUTHORISED"


def test_new_build_late_or_naive_timestamp_blocked() -> None:
    for timestamp in ("2026-10-15T15:00:00Z", "2026-10-15T09:00:00"):
        result = audit_new_build([_readiness(timestamp)], _crosswalk())
        assert result["lanes"]["lane_a"] == {}
        assert result["exclusions"]["lane_a"]["NOT_PROVED_PRE_RACE"] == 1


def test_new_build_duplicate_rank_and_unmapped_horse_blocked() -> None:
    duplicate = _readiness()
    duplicate["race_day_scorecards"][0]["lane_a_top3"].append(
        {"rank": 1, "horse": "Prime Pick", "prob": 0.8}
    )
    result = audit_new_build([duplicate], _crosswalk())
    assert result["exclusions"]["lane_a"]["AMBIGUOUS_RANK_ONE"] == 1

    missing = _readiness()
    missing["race_day_scorecards"][0]["lane_a_top3"][0]["horse"] = "Unknown"
    result = audit_new_build([missing], _crosswalk())
    assert result["exclusions"]["lane_a"]["UNMATCHED_OR_AMBIGUOUS_PICK"] == 1


def test_new_build_rejects_incomplete_race_and_duplicate_report() -> None:
    crosswalk = _crosswalk()
    crosswalk.records[1] = replace(crosswalk.records[1], status="INCOMPLETE")
    result = audit_new_build([_readiness()], crosswalk)
    assert result["exclusions"]["lane_a"]["NO_VERIFIED_MATCHING_RACE"] == 1
    result = audit_new_build([_readiness(), _readiness()], _crosswalk())
    assert result["exclusions"]["lane_a"]["DUPLICATE_READINESS_RACE"] == 1


def test_midprice_action_is_not_a_probability_and_abstention_is_hypothetical() -> None:
    result = audit_midprice_actions([_midprice()], _crosswalk())
    assert result["action_groups"]["MIDPRICE_SUPPRESS_TOP"]["races"] == 1
    assert result["action_groups"]["MIDPRICE_SUPPRESS_TOP"]["hypothetical_abstentions"] == 1
    assert result["action_groups"]["MIDPRICE_SUPPRESS_TOP"]["prime_wins"] == 0
    assert result["promotion"] == "NOT_AUTHORISED"
    assert result["metric_type"] == "SELECTION_CONDITIONAL_OUTCOMES_NOT_BRIER"


def test_midprice_rejects_late_timestamps_and_unsafe_contract() -> None:
    late = audit_midprice_actions([_midprice("2026-10-15T16:00:00Z")], _crosswalk())
    assert late["exclusions"]["ACTION_NOT_PROVED_PRE_RACE"] == 1
    unsafe = _midprice()
    unsafe["execution_allowed"] = True
    result = audit_midprice_actions([unsafe], _crosswalk())
    assert result["exclusions"]["VIOLATES_SHADOW_ONLY_CONTRACT"] == 1
    assert result["action_groups"] == {}


def test_midprice_wrong_top_pick_is_not_scored() -> None:
    entry = _midprice()
    entry["top_pick"] = "Challenger"
    result = audit_midprice_actions([entry], _crosswalk())
    assert result["exclusions"]["TOP_PICK_NOT_CANONICAL_PRIME"] == 1


def test_new_build_rejects_invalid_probability_and_inconsistent_horse_id() -> None:
    bad = _readiness()
    bad["race_day_scorecards"][0]["lane_a_top3"][0]["prob"] = float("nan")
    result = audit_new_build([bad], _crosswalk())
    assert result["exclusions"]["lane_a"]["INVALID_CAPTURED_PROBABILITY"] == 1
    bad = _readiness()
    bad["race_day_scorecards"][0]["lane_a_top3"][0]["horse_id"] = "wrong"
    result = audit_new_build([bad], _crosswalk())
    assert result["exclusions"]["lane_a"]["UNMATCHED_OR_AMBIGUOUS_PICK"] == 1
