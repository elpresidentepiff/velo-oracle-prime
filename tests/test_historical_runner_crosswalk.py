from __future__ import annotations

from datetime import UTC, datetime

from src.intelligence.challenger_research_cycle import propose_calibration_review, reflect
from src.intelligence.historical_runner_crosswalk import (
    SOURCE_VERDICT,
    STATUS_COMPLETE,
    SourceBundle,
    build_crosswalk,
    canonical_sha256,
    frozen_holdout,
    frozen_model_holdout,
)


def _scorecard(horse_id: str, horse: str, position: str, win: bool) -> dict:
    return {
        "run_date": "2026-06-20",
        "race_id": "921135",
        "course": "Ascot",
        "off_time": "2.30",
        "model_name": "velo_prime",
        "horse_id": horse_id,
        "horse": horse,
        "result_position": position,
        "win": win,
        "subject_is_non_runner": False,
        "result_source_hash": "a" * 64,
        "result_source_complete": True,
        "official_evaluation_eligible": True,
    }


def _bundle() -> SourceBundle:
    predictions = [
        {
            "race_id": "921135",
            "horse_id": "h1",
            "horse": "Winner",
            "velo_prime_prob": 0.55,
            "sqpe_v17_prob": 0.50,
            "sqpe_no_rpr_shadow_prob": 0.60,
            "sp_dec": 2.5,
        },
        {
            "race_id": "921135",
            "horse_id": "h2",
            "horse": "Second",
            "velo_prime_prob": 0.45,
            "sqpe_v17_prob": 0.50,
            "sqpe_no_rpr_shadow_prob": 0.40,
            "sp_dec": 4.0,
        },
    ]
    return SourceBundle(
        runner_prediction_snapshots=[],
        velo_verdicts=[
            {
                "id": 7,
                "race_id": "921135",
                "generated_at": "2026-06-20T11:03:31Z",
                "full_analysis": {"predictions": predictions},
            }
        ],
        canonical_model_scorecards=[
            _scorecard("h1", "Winner", "1", True),
            _scorecard("h2", "Second", "2", False),
        ],
        velo_race_truth=[
            {
                "race_id": "921135",
                "race_date": "2026-06-20",
                "course": "Ascot",
                "off_time": "2.30",
                "actual_winner_id": "h1",
                "reconciled_date": "2026-06-20",
            }
        ],
    )


def test_verdict_crosswalk_preserves_ordinal_without_inventing_rank() -> None:
    report = build_crosswalk(_bundle())

    assert len(report.records) == 2
    assert all(row.status == STATUS_COMPLETE for row in report.records)
    assert all(row.prediction_source == SOURCE_VERDICT for row in report.records)
    assert [row.rank for row in report.records] == [None, None]
    assert [row.source_ordinal for row in report.records] == [1, 2]
    assert report.counts_by_date["2026-06-20"]["complete_verified_runner_records"] == 2
    assert len(report.source_hashes["velo_verdicts"]) == 64


def test_unverified_result_and_late_prediction_fail_closed() -> None:
    bundle = _bundle()
    bundle.velo_verdicts[0]["generated_at"] = "2026-06-20T14:00:00Z"
    bundle.canonical_model_scorecards[0]["official_evaluation_eligible"] = False

    report = build_crosswalk(bundle)
    first = report.records[0]

    assert first.status != STATUS_COMPLETE
    assert "MISSING_PRE_RACE_TIMESTAMP_EVIDENCE" in first.evidence_issues
    assert "MISSING_OR_UNVERIFIED_OFFICIAL_RESULT" in first.evidence_issues


def test_missing_race_truth_winner_is_not_certified() -> None:
    bundle = _bundle()
    bundle.velo_race_truth[0]["actual_winner_id"] = None
    report = build_crosswalk(bundle)
    assert all(row.status != STATUS_COMPLETE for row in report.records)
    assert all("MISSING_OR_UNVERIFIED_OFFICIAL_RESULT" in row.evidence_issues for row in report.records)
    observations, manifest = frozen_holdout(report, holdout_start="2026-06-20")
    assert observations == []
    assert manifest["excluded_races"] == {"INCOMPLETE_STARTER_EVIDENCE": 1}


def test_frozen_holdout_uses_identical_paired_cohort_and_existing_cycle() -> None:
    report = build_crosswalk(_bundle())
    observations, manifest = frozen_holdout(report, holdout_start="2026-06-20")

    assert len(observations) == 2
    assert manifest["comparison_cohort"] == "IDENTICAL_PAIRED_RUNNERS"
    assert manifest["baseline_model"] == "velo_prime_prob"
    assert manifest["challenger_model"] == "sqpe_v17_prob"
    assert len(manifest["cohort_sha256"]) == 64
    proposal = propose_calibration_review(baseline_ref="git:test")
    replay = reflect(proposal, observations, min_runners=2)
    assert replay["production_authority"] is False
    assert replay["evaluation"]["promotion"] == "NOT_AUTHORISED"


def test_hash_is_order_stable_for_mapping_keys() -> None:
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})


def test_model_holdout_requires_complete_probability_and_price_cohorts() -> None:
    report = build_crosswalk(_bundle())
    observations, market, manifest = frozen_model_holdout(
        report,
        challenger_field="sqpe_no_rpr_shadow_prob",
        holdout_start="2026-06-20",
        require_market_price=True,
    )
    assert len(observations) == len(market) == 2
    assert manifest["challenger_model"] == "sqpe_no_rpr_shadow_prob"
    assert manifest["market_price_field"] == "sp_dec"
    assert all(row.decimal_price > 1 for row in market)


def test_model_holdout_fails_closed_when_one_runner_lacks_probability() -> None:
    bundle = _bundle()
    del bundle.velo_verdicts[0]["full_analysis"]["predictions"][1]["sqpe_no_rpr_shadow_prob"]
    observations, market, manifest = frozen_model_holdout(
        build_crosswalk(bundle),
        challenger_field="sqpe_no_rpr_shadow_prob",
        holdout_start="2026-06-20",
        require_market_price=True,
    )
    assert observations == market == []
    assert manifest["excluded_races"] == {"MISSING_CHALLENGER_PROBABILITY": 1}


def test_raw_snapshot_duplicate_is_counted_by_date_and_not_certified() -> None:
    row = {
        "run_id": "run",
        "created_at": "2026-06-20T11:00:00Z",
        "race_date": "2026-06-20",
        "race_id": "921135",
        "course": "Ascot",
        "off_time": "2.30",
        "rank": 0,
        "horse_id": "h1",
        "horse": "Winner",
        "velo_prime_prob": 0.5,
        "sqpe_v17_prob": 0.5,
    }
    bundle = SourceBundle([row, dict(row)], [], [], [])
    report = build_crosswalk(bundle)
    assert report.records == []
    assert report.duplicate_snapshot_entries == 1
    assert report.counts_by_date["2026-06-20"]["duplicate_or_contradictory_identities"] == 1


def test_legacy_non_mapping_full_analysis_is_ignored() -> None:
    bundle = _bundle()
    bundle.velo_verdicts.append({"race_id": "legacy", "full_analysis": [{"predictions": []}]})
    report = build_crosswalk(bundle)
    assert len(report.records) == 2
    assert report.source_counts[SOURCE_VERDICT] == 2


def test_timestamp_is_converted_from_bst_to_utc() -> None:
    report = build_crosswalk(_bundle())
    assert report.records[0].race_time == datetime(2026, 6, 20, 13, 30, tzinfo=UTC).isoformat().replace("+00:00", "Z")
