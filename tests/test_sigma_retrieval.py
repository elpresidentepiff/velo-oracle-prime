import json
from pathlib import Path

from new_build_velo.sigma_retrieval import (
    BuildPaths,
    bayesian_posterior_from_knn,
    build_evidence_explanation,
    build_sigma_retrieval_corpus,
    mine_doctrine_candidates,
    render_doctrine_miner_md,
    retrieve_sigma_neighbors,
)


def test_retrieval_entrypoint_exposes_freshness_gate():
    from scripts.ops.build_sigma_retrieval_corpus import parse_args
    import sys
    from unittest.mock import patch

    with patch.object(sys, "argv", ["build_sigma_retrieval_corpus.py", "--require-through-date", "2026-06-08"]):
        args = parse_args()

    assert args.require_through_date == "2026-06-08"


def test_sigma_retrieval_corpus_is_shadow_only_and_regime_aware(tmp_path: Path):
    root = tmp_path
    data = root / "data"
    data.mkdir()
    (data / "sigma_memory").mkdir()

    sigma_dump = data / "sigma_audits_dump.json"
    sigma_dump.write_text(
        json.dumps(
            [
                {
                    "race_id": "R1",
                    "date": "2026-06-01",
                    "track": "Lingfield (AW)",
                    "top_strike_correct": True,
                    "decision_tier": "A",
                    "verdict_score": 0.34,
                },
                {
                    "race_id": "R2",
                    "date": "2026-06-01",
                    "track": "Bath",
                    "outcome": "MISS",
                    "miss_reason": "market_decoy_followed",
                    "decision_tier": "B",
                    "verdict_score": 0.19,
                },
            ]
        ),
        encoding="utf-8",
    )

    (data / "velo_prime_verdicts_2026_06_01.json").write_text(
        json.dumps(
            [
                {
                    "race_id": "R1",
                    "course": "Lingfield (AW)",
                    "tier": "A",
                    "top": {
                        "horse": "Test Horse",
                        "horse_id": "123",
                        "velo_prime_prob": 0.34,
                        "market_deception_score": 0.24,
                        "improvement_score": 0.31,
                        "release_day_prob": 0.42,
                        "longshot_prob": 0.12,
                        "place_prob": 0.72,
                        "g_base_prob": 0.27,
                        "ensemble_version": "velo_prime_v1",
                        "signal_contract_version": "hfs_signal_contract_v1",
                        "verdict_flags": ["g_threshold:0.60"],
                        "doctrines_fired": ["SHADOW_TRACKING"],
                    },
                }
            ]
        ),
        encoding="utf-8",
    )

    (data / "velo_run_observability_2026_06_01_abcd.json").write_text(
        json.dumps(
            {
                "date": "2026-06-01",
                "timestamp": "2026-06-01T09:00:00+00:00",
                "git_commit_sha": "abc123",
                "source_truth": "CACHE",
                "feature_health": "PASS",
                "active_formula": "sqpe_v17",
                "learning_gate": "OPEN",
            }
        ),
        encoding="utf-8",
    )

    report = build_sigma_retrieval_corpus(BuildPaths(root=root, sigma_dump=sigma_dump))

    assert report["total_records"] == 2
    assert report["retrieval_eligible_records"] == 2
    assert report["rpr_violations"] == 0

    rows = [
        json.loads(line)
        for line in (data / "sigma_memory" / "sigma_retrieval_corpus_v1.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert all(row["shadow_only"] is True for row in rows)
    assert all(row["live_velo_impact"] is False for row in rows)
    assert all(row["rpr_policy"] == "RPR_NOT_INCLUDED" for row in rows)
    assert rows[0]["doctrine_version"] == "hfs_signal_contract_v1"
    assert rows[0]["threshold_at_race_time"] == "G_THRESHOLD_0.60"
    assert rows[0]["regime_confidence"] == "HIGH"
    assert rows[0]["retrieval_state_vector"]["course_type"] == "AW"
    assert rows[0]["retrieval_state_vector"]["improvement_band"] == "P30_40"
    assert rows[0]["retrieval_state_vector"]["release_band"] == "P40_50"
    assert rows[0]["retrieval_state_vector"]["place_band"] == "P50_PLUS"
    assert rows[0]["retrieval_state_vector"]["g_adjustment_applied"] == "True"
    assert rows[1]["miss_type_outcome"] == "MARKET_DECOY_FOLLOWED"


def test_sigma_retrieval_blocks_rows_without_date_or_outcome(tmp_path: Path):
    root = tmp_path
    data = root / "data"
    data.mkdir()
    (data / "sigma_memory").mkdir()
    sigma_dump = data / "sigma_audits_dump.json"
    sigma_dump.write_text(json.dumps([{"race_id": "R3"}]), encoding="utf-8")

    report = build_sigma_retrieval_corpus(BuildPaths(root=root, sigma_dump=sigma_dump))

    assert report["total_records"] == 1
    assert report["retrieval_eligible_records"] == 0
    assert report["retrieval_blocker_counts"]["OUTCOME_OR_DATE_MISSING"] == 1


def test_sigma_knn_retrieval_returns_weighted_outcome_summary():
    corpus = [
        {
            "retrieval_eligible": True,
            "race_id": "A",
            "race_date": "2026-06-01",
            "course": "Bath",
            "horse": "Winner",
            "outcome": "WIN",
            "miss_type_outcome": "NONE",
            "regime_id": "r1",
            "regime_confidence": "HIGH",
            "retrieval_state_vector": {
                "mds_band": "P30_40",
                "vp_band": "P30_40",
                "improvement_band": "P20_30",
                "release_band": "P40_50",
                "sp_band": "SP_4_8",
            },
        },
        {
            "retrieval_eligible": True,
            "race_id": "B",
            "race_date": "2026-05-01",
            "course": "Bath",
            "horse": "Miss",
            "outcome": "MISS",
            "miss_type_outcome": "MARKET_DECOY_FOLLOWED",
            "regime_id": "r1",
            "regime_confidence": "HIGH",
            "retrieval_state_vector": {
                "mds_band": "P00_10",
                "vp_band": "P00_10",
                "improvement_band": "P00_10",
                "release_band": "P00_10",
                "sp_band": "SP_16_PLUS",
            },
        },
    ]

    result = retrieve_sigma_neighbors(
        {
            "mds_band": "P30_40",
            "vp_band": "P30_40",
            "improvement_band": "P20_30",
            "release_band": "P40_50",
            "sp_band": "SP_4_8",
        },
        corpus,
        query_date="2026-06-02",
        k=1,
    )

    assert result["shadow_only"] is True
    assert result["live_velo_impact"] is False
    assert result["neighbors_returned"] == 1
    assert result["win_rate"] == 1.0
    assert result["neighbors"][0]["race_id"] == "A"
    assert result["bayesian_posterior"]["shadow_only"] is True
    assert result["bayesian_posterior"]["posterior_win_prob"] > result["bayesian_posterior"]["prior_win_prob"]


def test_sigma_knn_rejects_low_coverage_matches():
    corpus = [
        {
            "retrieval_eligible": True,
            "race_id": "LOW",
            "race_date": "2026-06-01",
            "outcome": "WIN",
            "miss_type_outcome": "NONE",
            "retrieval_state_vector": {
                "mds_band": "UNKNOWN",
                "vp_band": "UNKNOWN",
                "improvement_band": "UNKNOWN",
                "release_band": "UNKNOWN",
                "sidecar_tier": "A",
            },
        }
    ]

    result = retrieve_sigma_neighbors(
        {
            "mds_band": "P30_40",
            "vp_band": "P30_40",
            "improvement_band": "P20_30",
            "release_band": "P40_50",
            "sidecar_tier": "A",
        },
        corpus,
        min_weight_coverage=0.25,
    )

    assert result["neighbors_returned"] == 0


def test_bayesian_posterior_uses_weighted_coverage_and_quality_gate():
    knn = {
        "neighbors": [
            {"outcome": "WIN", "evidence_coverage": 0.5},
            {"outcome": "FRAME", "evidence_coverage": 0.5},
            {"outcome": "MISS", "evidence_coverage": 0.5},
            {"outcome": "WIN", "evidence_coverage": 0.5},
            {"outcome": "MISS", "evidence_coverage": 0.5},
            {"outcome": "WIN", "evidence_coverage": 0.5},
            {"outcome": "FRAME", "evidence_coverage": 0.5},
            {"outcome": "MISS", "evidence_coverage": 0.5},
            {"outcome": "WIN", "evidence_coverage": 0.5},
            {"outcome": "FRAME", "evidence_coverage": 0.5},
        ]
    }

    posterior = bayesian_posterior_from_knn(knn)

    assert posterior["schema_version"] == "sigma_bayesian_posterior_v1"
    assert posterior["live_velo_impact"] is False
    assert posterior["analogues_n"] == 10
    assert posterior["weighted_n"] == 5.0
    assert posterior["evidence_quality"] == "HIGH"
    assert posterior["posterior_win_prob"] > posterior["prior_win_prob"]
    assert posterior["posterior_frame_prob"] > posterior["prior_frame_prob"]


def test_evidence_explanation_surfaces_matching_dims_and_miss_pattern():
    knn_result = {
        "query_vector": {
            "mds_band": "P30_40",
            "vp_band": "P30_40",
            "improvement_band": "P20_30",
            "release_band": "P40_50",
            "sp_band": "SP_4_8",
        },
        "win_rate": 0.4,
        "frame_rate": 0.7,
        "outcome_counts": {"WIN": 4, "FRAME": 3, "MISS": 3},
        "neighbors": [
            {
                "race_date": "2026-03-01", "outcome": "WIN", "miss_type_outcome": "NONE",
                "evidence_coverage": 0.8, "regime_confidence": "LOW_REGIME_INFERRED",
                "state_vector": {"mds_band": "P30_40", "vp_band": "P30_40", "improvement_band": "P20_30"},
            },
            {
                "race_date": "2026-04-01", "outcome": "MISS", "miss_type_outcome": "MARKET_DECOY_FOLLOWED",
                "evidence_coverage": 0.7, "regime_confidence": "LOW_REGIME_INFERRED",
                "state_vector": {"mds_band": "P30_40", "vp_band": "P30_40", "improvement_band": "P20_30"},
            },
            {
                "race_date": "2026-04-15", "outcome": "MISS", "miss_type_outcome": "MARKET_DECOY_FOLLOWED",
                "evidence_coverage": 0.6, "regime_confidence": "LOW_REGIME_INFERRED",
                "state_vector": {"mds_band": "P30_40", "vp_band": "P20_30", "improvement_band": "P20_30"},
            },
        ],
        "bayesian_posterior": {
            "posterior_win_prob": 0.2932,
            "posterior_frame_prob": 0.5777,
            "prior_win_prob": 0.2,
            "prior_frame_prob": 0.48,
            "evidence_quality": "LOW",
            "median_evidence_coverage": 0.7,
        },
    }

    explanation = build_evidence_explanation(
        knn_result,
        race_context={"course": "Bath", "date": "2026-06-04"},
    )

    assert explanation["schema_version"] == "sigma_evidence_explanation_v1"
    assert explanation["shadow_only"] is True
    assert explanation["live_velo_impact"] is False
    assert explanation["rpr_policy"] == "RPR_NOT_INCLUDED"
    assert explanation["analogues_n"] == 3
    assert explanation["posterior_win_prob"] == 0.2932
    assert "MARKET_DECOY_FOLLOWED" in (explanation["dominant_miss_type"] or "")
    assert explanation["regime_warning"] is not None  # all LOW_REGIME_INFERRED
    assert len(explanation["top_matching_dims"]) > 0
    top_dim = explanation["top_matching_dims"][0]
    assert "dim" in top_dim and "match_count" in top_dim and "match_rate" in top_dim
    assert "## Evidence Report" in explanation["narrative_md"]
    assert "Bath" in explanation["narrative_md"]
    assert "Boundaries" in explanation["narrative_md"]


def test_doctrine_miner_outputs_candidate_only_patterns():
    def record(idx: int, outcome: str, mds: str = "P30_40", vp: str = "P40_50") -> dict:
        return {
            "retrieval_eligible": True,
            "race_id": f"R{idx}",
            "race_date": "2026-04-01",
            "outcome": outcome,
            "miss_type_outcome": "MID_PRICED_WON" if outcome == "MISS" else "NONE",
            "regime_confidence": "LOW_REGIME_INFERRED",
            "retrieval_state_vector": {
                "mds_band": mds,
                "vp_band": vp,
                "improvement_band": "P20_30",
                "release_band": "P00_10",
                "sp_band": "SP_4_8",
                "place_band": "P50_PLUS",
                "sidecar_tier": "A",
                "course_type": "AW",
            },
        }

    corpus = [record(i, "WIN" if i < 12 else "FRAME" if i < 24 else "MISS") for i in range(30)]
    corpus.append({**record(99, "WIN"), "retrieval_eligible": False})

    report = mine_doctrine_candidates(corpus, min_support=30, max_dims=2)

    assert report["schema_version"] == "sigma_doctrine_miner_v1"
    assert report["candidate_only"] is True
    assert report["shadow_only"] is True
    assert report["live_velo_impact"] is False
    assert report["rpr_policy"] == "RPR_NOT_INCLUDED"
    assert report["eligible_records"] == 30
    assert report["candidate_count"] > 0
    assert report["dedupe_policy"] == "PARSIMONIOUS_IDENTICAL_STATS"
    assert report["deduped_candidate_count"] >= 0

    top = report["candidates"][0]
    assert top["candidate_only"] is True
    assert top["promotion_status"] == "NOT_PROMOTED"
    assert top["classification"] == "DOCTRINE_CANDIDATE_ONLY"
    assert top["support_n"] == 30
    assert top["rpr_policy"] == "RPR_NOT_INCLUDED"

    md = render_doctrine_miner_md(report)
    assert "Sigma Doctrine Miner V1" in md
    assert "Dedupe policy" in md
    assert "Doctrine candidates require human review" in md


def test_doctrine_miner_dedupes_identical_stat_supersets():
    def record(idx: int) -> dict:
        return {
            "retrieval_eligible": True,
            "race_id": f"R{idx}",
            "race_date": "2026-04-01",
            "outcome": "WIN" if idx < 12 else "FRAME" if idx < 24 else "MISS",
            "miss_type_outcome": "MID_PRICED_WON" if idx >= 24 else "NONE",
            "regime_confidence": "LOW_REGIME_INFERRED",
            "retrieval_state_vector": {
                "vp_band": "P40_50",
                "place_band": "P50_PLUS",
                "release_band": "P00_10",
                "sidecar_tier": "A",
            },
        }

    corpus = [record(i) for i in range(30)]
    raw = mine_doctrine_candidates(corpus, min_support=30, max_dims=3, dedupe_parsimonious=False)
    deduped = mine_doctrine_candidates(corpus, min_support=30, max_dims=3, dedupe_parsimonious=True)

    assert raw["candidate_count"] > deduped["candidate_count"]
    assert deduped["deduped_candidate_count"] == raw["candidate_count"] - deduped["candidate_count"]
    labels = [candidate["pattern_label"] for candidate in deduped["candidates"]]
    assert "vp_band=P40_50 | place_band=P50_PLUS | release_band=P00_10" not in labels
