"""The Prime / FormFav comparison must be made on equal terms and on pre-race information only."""
from __future__ import annotations

from datetime import UTC, datetime

from src.velo import formfav_head_to_head as h2h

OFF = datetime(2026, 11, 14, 15, 30, tzinfo=UTC)


def _result(horse: str, pos: int, sp: float | None) -> dict:
    return {"race_id": "100", "horse": horse, "position_int": pos, "sp_dec": sp}


def _verdict(generated_at: str, probs: dict[str, float]) -> dict:
    return {"race_id": "100", "generated_at": generated_at,
            "full_analysis": {"predictions": [{"horse": h, "velo_prime_prob": p} for h, p in probs.items()]}}


def _prediction(predicted_at: str | None, probs: dict[str, float]) -> dict:
    return {"provider_race_key": "ff-1", "predictions_payload": {
        "predictedAt": predicted_at, "predictions": [{"name": h, "winProb": p} for h, p in probs.items()]}}


VELO_RACES = [{"race_id": "100", "course": "Cheltenham", "date": "2026-11-14", "time": "15:30:00"}]
FF_RACES = [{"provider_race_key": "ff-1", "race_date": "2026-11-14", "track": "Cheltenham",
             "start_time": "2026-11-14T15:30:00Z"}]
RESULTS = [_result("Alpha (IRE)", 1, 3.0), _result("Bravo", 2, 2.5), _result("Charlie's Boy", 3, 9.0)]
PRIME = {"Alpha": 0.2, "Bravo": 0.5, "Charlies Boy": 0.3}
FORMFAV = {"Alpha (IRE)": 0.45, "Bravo": 0.35, "Charlie's Boy": 0.2}


# ── identity ─────────────────────────────────────────────────────────────────


def test_names_match_across_suffixes_and_punctuation() -> None:
    assert h2h.horse_key("Alpha (IRE)") == h2h.horse_key("alpha") == "alpha"
    assert h2h.horse_key("Charlie's Boy") == h2h.horse_key("Charlies Boy")


def test_course_names_that_differ_between_formfav_and_racing_post_pair() -> None:
    """52 of 1,263 FormFav GB/IE races (2026-10-12 to 11-14) failed to pair on these four names."""
    for formfav, racing_post in (
        ("Catterick Bridge", "Catterick"), ("Chelmsford City", "Chelmsford (AW)"), ("Great Yarmouth", "Yarmouth"),
        ("Stratford Avon", "Stratford"), ("Kempton Park", "Kempton (AW)"), ("Newcastle AW", "Newcastle (AW)"),
        ("Southwell AW", "Southwell (AW)"),
    ):
        assert h2h.track_key(formfav) == h2h.track_key(racing_post), formfav
    assert h2h.track_key("Newbury") != h2h.track_key("Newcastle")


def test_pairing_uses_london_clock_time_and_reports_why_a_race_did_not_pair() -> None:
    summer = [{"provider_race_key": "s", "race_date": "2026-10-20", "track": "Stratford Avon", "start_time": "2026-10-20T13:10:00Z"}]
    velo = [{"race_id": "7", "course": "Stratford", "date": "2026-10-20", "time": "14:10:00"}]  # BST: 13:10Z is 14:10
    paired, unmatched = h2h.pair_races(velo, summer)
    assert list(paired) == ["7"] and unmatched == []

    _, unmatched = h2h.pair_races(velo, [
        {"provider_race_key": "a", "race_date": "2026-10-21", "track": "Stratford Avon", "start_time": "2026-10-21T13:10:00Z"},
        {"provider_race_key": "b", "race_date": "2026-10-20", "track": "Newbury", "start_time": "2026-10-20T13:10:00Z"},
        {"provider_race_key": "c", "race_date": "2026-10-20", "track": "Stratford Avon", "start_time": "2026-10-20T15:00:00Z"},
    ])
    assert [u["reason"] for u in unmatched] == ["NO_VELO_CARD_THAT_DAY", "COURSE_NOT_ON_VELO_CARD", "OFF_TIME_NOT_FOUND"]


# ── nothing known after the off is used ──────────────────────────────────────


def test_a_prime_verdict_written_after_the_off_is_never_used() -> None:
    before = _verdict("2026-11-14T07:25:00Z", {"Alpha": 0.2, "Bravo": 0.8})
    rescore_after = _verdict("2026-11-14T16:00:00Z", {"Alpha": 0.9, "Bravo": 0.1})
    assert h2h.pre_off_verdict([rescore_after, before], OFF) is before
    assert h2h.pre_off_verdict([rescore_after], OFF) is None
    assert h2h.pre_off_verdict([_verdict("2026-11-14T15:30:00Z", {})], OFF) is None  # at the off is not before it


def test_a_formfav_prediction_made_at_or_after_the_off_or_undated_is_dropped() -> None:
    assert h2h.formfav_probabilities(_prediction("2026-11-14T09:46:07Z", FORMFAV), OFF)
    assert h2h.formfav_probabilities(_prediction("2026-11-14T15:30:00Z", FORMFAV), OFF) == {}
    assert h2h.formfav_probabilities(_prediction("2026-11-14T18:00:00Z", FORMFAV), OFF) == {}
    assert h2h.formfav_probabilities(_prediction(None, FORMFAV), OFF) == {}


# ── both sources are scored on the same field ────────────────────────────────


def _probs(mapping: dict[str, float]) -> dict[str, float]:
    return {h2h.horse_key(k): v for k, v in mapping.items()}


def test_a_race_counts_only_when_every_priced_runner_is_in_both_sources() -> None:
    assert h2h.build_race(RESULTS, _probs(PRIME), _probs(FORMFAV)) is not None
    missing_one = {k: v for k, v in _probs(FORMFAV).items() if k != "bravo"}
    assert h2h.build_race(RESULTS, _probs(PRIME), missing_one) is None
    assert h2h.build_race(RESULTS[:2], _probs(PRIME), _probs(FORMFAV)) is None  # fewer than three runners
    no_price = [*RESULTS[:2], _result("Charlie's Boy", 3, None)]
    assert h2h.build_race(no_price, _probs(PRIME), _probs(FORMFAV)) is None
    dead_heat = [_result("Alpha", 1, 3.0), _result("Bravo", 1, 2.5), _result("Charlies Boy", 3, 9.0)]
    assert h2h.build_race(dead_heat, _probs(PRIME), _probs(FORMFAV)) is None


def test_probabilities_are_normalised_within_the_race_and_the_blend_has_no_free_parameter() -> None:
    runners = h2h.build_race(RESULTS, _probs(PRIME), _probs(FORMFAV))
    assert runners is not None
    for model in h2h.MODELS:
        assert abs(sum(r[model] for r in runners) - 1.0) < 1e-9
    alpha = next(r for r in runners if r["horse"] == "alpha")
    raw = {r["horse"]: (r["PRIME"] * r["FORMFAV"]) ** 0.5 for r in runners}
    assert abs(alpha["PRIME_x_FORMFAV"] - raw["alpha"] / sum(raw.values())) < 1e-12
    assert abs(alpha["MARKET_SP"] - (1 / 3.0) / (1 / 3.0 + 1 / 2.5 + 1 / 9.0)) < 1e-12


# ── scoring ──────────────────────────────────────────────────────────────────


def test_metrics_on_one_race() -> None:
    report = h2h.evaluate(VELO_RACES, FF_RACES, [_verdict("2026-11-14T07:25:00Z", PRIME)],
                          [_prediction("2026-11-14T09:46:07Z", FORMFAV)], RESULTS)
    assert report["coverage"]["eligible"] == 1
    metrics = report["metrics"]
    assert metrics["PRIME"]["top1_pct"] == 0.0 and metrics["PRIME"]["roi_at_sp_pct"] == -100.0  # picked Bravo
    assert metrics["FORMFAV"]["top1_pct"] == 100.0 and metrics["FORMFAV"]["roi_at_sp_pct"] == 200.0  # Alpha at 3.0
    assert metrics["MARKET_SP"]["top1_pct"] == 0.0  # Bravo was favourite
    assert all(m["winner_in_top3_pct"] == 100.0 for m in metrics.values())
    assert report["prime_vs_formfav"] == {"only_PRIME": 0, "only_FORMFAV": 1, "sign_test_p": 1.0}


def test_a_race_with_only_a_post_off_verdict_is_excluded_and_counted() -> None:
    report = h2h.evaluate(VELO_RACES, FF_RACES, [_verdict("2026-11-14T16:00:00Z", PRIME)],
                          [_prediction("2026-11-14T09:46:07Z", FORMFAV)], RESULTS)
    assert report["coverage"]["eligible"] == 0
    assert report["coverage"]["excluded_after_pairing"] == {"NO_PRE_OFF_PRIME_VERDICT": 1}


def test_the_sign_test_matches_the_measured_result() -> None:
    """2026-10-12 to 11-14: blend alone right in 57 races, Prime alone in 28."""
    def race(prime_hit: bool, blend_hit: bool) -> list[dict]:
        def runner(name, won, p, b):
            return {"horse": name, "won": won, "sp": 4.0, "PRIME": p, "FORMFAV": 0.3, "PRIME_x_FORMFAV": b, "MARKET_SP": 0.3}
        return [runner("w", True, 0.6 if prime_hit else 0.1, 0.6 if blend_hit else 0.1),
                runner("x", False, 0.3, 0.3), runner("y", False, 0.2, 0.2)]

    races = [race(False, True)] * 57 + [race(True, False)] * 28 + [race(True, True)] * 10
    out = h2h.paired_top1(races, "PRIME", "PRIME_x_FORMFAV")
    assert (out["only_PRIME"], out["only_PRIME_x_FORMFAV"]) == (28, 57)
    assert 0.001 < out["sign_test_p"] < 0.005


def test_agreement_is_reported_against_the_favourite_in_the_same_races() -> None:
    runners = h2h.build_race(RESULTS, _probs({"Alpha": 0.5, "Bravo": 0.3, "Charlies Boy": 0.2}), _probs(FORMFAV))
    out = h2h.agreement([runners])
    assert out["agreed_pick"] == {"races": 1, "top1_pct": 100.0, "roi_at_sp_pct": 200.0}
    assert out["favourite_in_the_same_races"] == {"races": 1, "top1_pct": 0.0, "roi_at_sp_pct": -100.0}
    assert out["agreed_pick_when_it_is_not_the_favourite"]["races"] == 1


def test_provider_predictions_stay_banned_from_velo_feature_packets() -> None:
    """Measuring FormFav's picks must not become a way to feed them into a VELO model."""
    from src.velo.formfav_feature_contract import scan_banned_fields

    assert scan_banned_fields({"predictions": [{"winProb": 0.4, "modelRank": 1}]})
