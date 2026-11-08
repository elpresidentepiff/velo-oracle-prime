"""Train/serve parity and fail-closed behaviour for the Rich Context challenger scorer."""

from __future__ import annotations

from src.velo.rich_context_challenger_features import (
    FEATURE_NAMES,
    extract_feature_vector,
    vector_from_packet_families,
)
from src.velo.rich_context_challenger_scorer import (
    load_artifact,
    rank_scored_packets,
    score_packet,
    score_row,
)


class _FakeModel:
    """A deterministic stand-in: probability = how "live" the horse's history is."""

    def predict_proba(self, X):
        return [
            [1 - row[FEATURE_NAMES.index("has_history")] * 0.3, row[FEATURE_NAMES.index("has_history")] * 0.3 + 0.1]
            for row in X
        ]


_ARTIFACT = {"model": _FakeModel(), "metadata": {"model_version": "test_v0"}}


def _packet(**families) -> dict:
    return {"families": families}


def test_missing_prime_baseline_is_ineligible_not_guessed() -> None:
    assert extract_feature_vector(prime_baseline=None, history_eligible=False, history_features=None) is None
    assert extract_feature_vector(prime_baseline={}, history_eligible=True, history_features={"win_rate": 0.2}) is None


def test_missing_history_sets_explicit_flags_not_a_favourable_default() -> None:
    v = extract_feature_vector(
        prime_baseline={"velo_prime_prob": 0.3, "sp_dec": 4.0}, history_eligible=False, history_features=None
    )
    assert v is not None
    by_name = dict(zip(FEATURE_NAMES, v, strict=True))
    assert by_name["has_history"] == 0.0
    assert by_name["win_rate_missing"] == 1.0 and by_name["win_rate"] == 0.0
    assert by_name["average_position_missing"] == 1.0 and by_name["average_position"] == 10.0  # neutral, flagged


def test_present_history_is_carried_through_unflagged() -> None:
    v = extract_feature_vector(
        prime_baseline={"velo_prime_prob": 0.25, "sp_dec": 5.0},
        history_eligible=True,
        history_features={
            "win_rate": 0.4,
            "place_rate": 0.6,
            "average_position": 2.5,
            "days_since_last_run": 21,
            "runs_90d": 3,
        },
    )
    by_name = dict(zip(FEATURE_NAMES, v, strict=True))
    assert by_name["has_history"] == 1.0
    assert by_name["win_rate"] == 0.4 and by_name["win_rate_missing"] == 0.0
    assert by_name["average_position"] == 2.5 and by_name["average_position_missing"] == 0.0
    assert by_name["days_since_last_run"] == 21.0 and by_name["runs_90d"] == 3.0


def test_no_leakage_field_name_is_post_off_or_a_provider_prediction() -> None:
    # "win_rate"/"place_rate"/"average_position" are legitimate prior-form aggregates about runs
    # that already finished before this race, not this race's own outcome or a provider's prediction
    # of it, so they are excluded from the banned exact-name set below.
    banned = {
        "result",
        "position_int",
        "sp_dec_result",
        "bsp",
        "fairprobability",
        "edge",
        "modelrank",
        "recommendation",
        "is_win",
    }
    for name in FEATURE_NAMES:
        assert name.lower() not in banned, name


def test_vector_from_packet_families_reads_the_exact_stored_shape() -> None:
    packet = _packet(
        prime_baseline_snapshot={"velo_prime_prob": 0.3, "sp_dec": 3.0},
        canonical_history={"win_rate": 0.1, "average_position": 4.0},
    )
    assert vector_from_packet_families(packet["families"]) is not None
    assert vector_from_packet_families({}) is None  # no prime_baseline_snapshot at all


def test_score_packet_returns_none_without_an_artifact() -> None:
    # artifact={} (not None) forces "no model loaded", regardless of whether a real fitted artifact
    # exists on this machine's disk: artifact=None would fall through to the real global loader.
    packet = _packet(prime_baseline_snapshot={"velo_prime_prob": 0.3, "sp_dec": 3.0})
    assert score_packet(packet, artifact={}) is None


def test_score_packet_returns_none_for_an_ineligible_packet_even_with_a_real_artifact() -> None:
    assert score_packet(_packet(), artifact=_ARTIFACT) is None


def test_score_packet_scores_an_eligible_packet_and_never_mutates_it() -> None:
    packet = _packet(
        prime_baseline_snapshot={"velo_prime_prob": 0.3, "sp_dec": 3.0},
        canonical_history={"win_rate": 0.2},
    )
    before = {k: dict(v) for k, v in packet["families"].items()}
    result = score_packet(packet, artifact=_ARTIFACT)
    assert result is not None
    assert 0.0 <= result["challenger_probability"] <= 1.0
    assert result["model_version"] == "test_v0"
    assert packet["families"] == before  # the scorer never writes into the packet itself


def test_rank_scored_packets_ranks_only_what_was_scored() -> None:
    scored_high = {"challenger_probability": 0.8}
    scored_low = {"challenger_probability": 0.2}
    p1, p2, p3 = object(), object(), object()
    rank_scored_packets([(p1, scored_low), (p2, scored_high), (p3, None)])
    assert scored_high["challenger_rank"] == 1
    assert scored_low["challenger_rank"] == 2  # the packets themselves (p1/p2/p3) are never mutated


def test_score_row_never_touches_the_packet_only_reads_its_identity() -> None:
    packet = {"race_date": "2026-11-07", "race_id": "930514", "horse_id": "5601165", "input_hash": "abc123"}
    before = dict(packet)
    result = {"model_version": "test_v0", "challenger_probability": 0.4, "challenger_rank": 2}
    row = score_row(packet, result, code_sha="deadbeef")
    assert packet == before  # evidence row never mutated
    assert row == {
        "race_date": "2026-11-07",
        "race_id": "930514",
        "horse_id": "5601165",
        "packet_input_sha256": "abc123",
        "model_version": "test_v0",
        "challenger_probability": 0.4,
        "challenger_rank": 2,
        "production_influence": False,
        "paper_sim_only": True,
        "code_sha": "deadbeef",
    }


def test_the_real_fitted_artifact_loads_and_scores_a_real_shaped_packet() -> None:
    # Integration smoke test for the actual model.joblib + metadata.json shipped in this repo, not the
    # fake model above. If no artifact has been fitted yet this is a no-op (status quo), never a failure.
    artifact = load_artifact()
    if artifact is None:
        return
    assert artifact["metadata"].get("model_version")
    packet = _packet(
        prime_baseline_snapshot={"velo_prime_prob": 0.22, "sp_dec": 6.0},
        canonical_history={"win_rate": 0.15, "place_rate": 0.4, "average_position": 3.5, "runs_90d": 2},
    )
    result = score_packet(packet, artifact=artifact)
    assert result is not None and 0.0 <= result["challenger_probability"] <= 1.0
    assert result["model_version"] == artifact["metadata"]["model_version"]


def test_rank_scored_packets_is_per_race_not_global() -> None:
    # Caller passes only one race's packets at a time; a second race starts its own rank 1.
    race_a = [(object(), {"challenger_probability": 0.9})]
    race_b = [(object(), {"challenger_probability": 0.1})]
    rank_scored_packets(race_a)
    rank_scored_packets(race_b)
    assert race_a[0][1]["challenger_rank"] == 1
    assert race_b[0][1]["challenger_rank"] == 1
