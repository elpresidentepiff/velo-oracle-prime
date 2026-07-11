"""
Tests for ROLE-EVAL-01 — dedicated evening evaluator for the Old VELO
WIN/PLACE/LONGSHOT card (scripts/ops/evaluate_old_velo_three_option_card.py).

Covers: venue code vs full-name resolution, exact race_id matching, 12h/24h/
ISO time parsing, unique +/-3 minute fallback, ambiguous-match blocking,
non-runner exclusion, horse name/suffix fallback identity matching, input
hashing, and the card-builder freeze/no-recompute behaviour.
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EVAL_MODULE_PATH = os.path.join(REPO_ROOT, "scripts", "ops", "evaluate_old_velo_three_option_card.py")
BUILD_MODULE_PATH = os.path.join(REPO_ROOT, "scripts", "ops", "build_old_velo_three_option_card.py")


def _import_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _import_module(EVAL_MODULE_PATH, "evaluate_old_velo_three_option_card")


@pytest.fixture(scope="module")
def build_mod():
    return _import_module(BUILD_MODULE_PATH, "build_old_velo_three_option_card")


# ---------------------------------------------------------------------------
# Course code resolution — venue code vs full-course-name mismatch
# ---------------------------------------------------------------------------


def test_course_code_full_name_resolves_to_known_code(mod):
    assert mod._course_code("Newmarket (July)") == "NMK"
    assert mod._course_code("Chester") == "CHS"
    assert mod._course_code("Ascot") == "ASC"


def test_course_code_already_a_code_passes_through(mod):
    # Falls back to first-3-letters-uppercase when not in the full-name table.
    assert mod._course_code("XYZ") == "XYZ"


def test_course_code_chelmsford_not_merged_into_chester(mod):
    # Chelmsford (CHE) and Chester (CHS) are different real venues -- no
    # global alias should merge them, even though some other script's
    # upstream feed had a specific CHE->CHS mislabeling to correct.
    assert mod._course_code("Chelmsford") == "CHE"
    assert mod._course_code("Chester") == "CHS"


# ---------------------------------------------------------------------------
# Time parsing — 12h dot-time, 24h, and ISO formats
# ---------------------------------------------------------------------------


def test_parse_time_racing_dot_time_pm(mod):
    # "1.35" is racing shorthand for 13:35 (no UK/IRE racing before 10am).
    assert mod._parse_time_to_minutes("1.35") == 13 * 60 + 35


def test_parse_time_24h_dot_time(mod):
    assert mod._parse_time_to_minutes("13.35") == 13 * 60 + 35


def test_parse_time_24h_colon_time(mod):
    assert mod._parse_time_to_minutes("20:50") == 20 * 60 + 50


def test_parse_time_iso_timestamp(mod):
    assert mod._parse_time_to_minutes("2026-07-10T13:40:00+01:00") == 13 * 60 + 40


def test_parse_time_empty_returns_none(mod):
    assert mod._parse_time_to_minutes("") is None
    assert mod._parse_time_to_minutes(None) is None


# ---------------------------------------------------------------------------
# ResultIndex — exact id, course/time, +/-3min fallback, ambiguity
# ---------------------------------------------------------------------------


def _result(race_id, course, off, runners):
    return {"race_id": race_id, "course": course, "off": off, "runners": runners}


def _runner(horse, position, sp_dec=5.0, horse_id="", non_runner=False):
    return {"horse": horse, "position": position, "sp_dec": sp_dec, "horse_id": horse_id, "non_runner": non_runner}


def test_exact_race_id_match(mod):
    results = {"results": [_result("922402", "Chester", "1.35", [])]}
    index = mod.ResultIndex(results)
    race, method = index.find({"race_id": "922402", "course": "Chester", "off_time": "1.35"})
    assert method == "EXACT_RACE_ID"
    assert race["race_id"] == "922402"


def test_course_time_exact_match_when_no_id_overlap(mod):
    results = {"results": [_result("922402", "Chester", "1.35", [])]}
    index = mod.ResultIndex(results)
    race, method = index.find({"race_id": "rp_CHS_20260710_1.35", "course": "CHS", "off_time": "1.35"})
    assert method == "COURSE_TIME_EXACT"
    assert race["race_id"] == "922402"


def test_unique_3min_fallback_match(mod):
    results = {"results": [_result("922402", "Chester", "1.33", [])]}
    index = mod.ResultIndex(results)
    race, method = index.find({"race_id": "rp_CHS_20260710_1.35", "course": "CHS", "off_time": "1.35"})
    assert method == "COURSE_TIME_FALLBACK_3MIN"
    assert race["race_id"] == "922402"


def test_beyond_3min_window_is_unresolved(mod):
    results = {"results": [_result("922402", "Chester", "1.20", [])]}
    index = mod.ResultIndex(results)
    race, method = index.find({"race_id": "rp_CHS_20260710_1.35", "course": "CHS", "off_time": "1.35"})
    assert race is None
    assert method == "UNRESOLVED_NO_MATCH"


def test_ambiguous_course_time_exact_is_blocked(mod):
    # Two results race objects share the identical (course, off_time) key --
    # must not silently pick one.
    results = {
        "results": [
            _result("922402", "Chester", "1.35", []),
            _result("922999", "Chester", "1.35", []),
        ]
    }
    index = mod.ResultIndex(results)
    race, method = index.find({"race_id": "rp_CHS_20260710_1.35", "course": "CHS", "off_time": "1.35"})
    assert race is None
    assert method == "AMBIGUOUS_COURSE_TIME"


def test_ambiguous_3min_fallback_is_blocked(mod):
    # Two candidates both fall within +/-3 minutes -- ambiguous, must block.
    results = {
        "results": [
            _result("922402", "Chester", "1.33", []),
            _result("922403", "Chester", "1.37", []),
        ]
    }
    index = mod.ResultIndex(results)
    race, method = index.find({"race_id": "rp_CHS_20260710_1.35", "course": "CHS", "off_time": "1.35"})
    assert race is None
    assert method == "AMBIGUOUS_FALLBACK_3MIN"


# ---------------------------------------------------------------------------
# Runner identity — horse ID first, normalised name fallback, suffix strip
# ---------------------------------------------------------------------------


def test_runner_identity_by_horse_id(mod):
    result_race = _result("1", "X", "1.00", [_runner("Some Horse", "1", horse_id="9153186")])
    pick = {"horse": "Different Name Entirely", "horse_id": "9153186"}
    runner, method = mod._find_runner(result_race, pick)
    assert method == "HORSE_ID"
    assert runner["horse"] == "Some Horse"


def test_runner_identity_synthetic_id_falls_back_to_name(mod):
    # Synthetic rp_{course}_{slug} ids (from the three-option card builder)
    # never match a real result's numeric horse_id -- must fall through to name.
    result_race = _result("1", "X", "1.00", [_runner("Best Rate", "1", horse_id="7654321")])
    pick = {"horse": "Best Rate", "horse_id": "rp_ASC_best_rate"}
    runner, method = mod._find_runner(result_race, pick)
    assert method == "HORSE_NAME"
    assert runner["horse"] == "Best Rate"


def test_runner_identity_country_suffix_stripped(mod):
    result_race = _result("1", "X", "1.00", [_runner("Some Horse (IRE)", "2")])
    pick = {"horse": "Some Horse", "horse_id": ""}
    runner, method = mod._find_runner(result_race, pick)
    assert method == "HORSE_NAME"
    assert runner["position"] == "2"


def test_runner_identity_miss_returns_none(mod):
    result_race = _result("1", "X", "1.00", [_runner("Totally Different", "1")])
    pick = {"horse": "Not In The Race", "horse_id": ""}
    runner, method = mod._find_runner(result_race, pick)
    assert runner is None
    assert method == "IDENTITY_MISS"


# ---------------------------------------------------------------------------
# evaluate() — non-runner exclusion, win/frame/profit accounting
# ---------------------------------------------------------------------------


def _card(races):
    return {"races": races}


def test_non_runner_excluded_from_evaluated_count(mod):
    result_race = _result("1", "Ascot", "1.35", [_runner("Pick Horse", "NR", non_runner=True)])
    results = {"results": [result_race]}
    card = _card(
        [
            {
                "race_id": "1",
                "course": "Ascot",
                "off_time": "1.35",
                "picks": [{"role": "WIN", "horse": "Pick Horse", "horse_id": ""}],
            }
        ]
    )
    out = mod.evaluate(card, results)
    assert out["role_metrics"]["WIN"]["non_runners"] == 1
    assert out["role_metrics"]["WIN"]["evaluated"] == 0


def test_win_accrues_profit_at_sp_minus_stake(mod):
    result_race = _result("1", "Ascot", "1.35", [_runner("Pick Horse", "1", sp_dec=4.0)])
    results = {"results": [result_race]}
    card = _card(
        [
            {
                "race_id": "1",
                "course": "Ascot",
                "off_time": "1.35",
                "picks": [{"role": "WIN", "horse": "Pick Horse", "horse_id": ""}],
            }
        ]
    )
    out = mod.evaluate(card, results)
    stats = out["role_metrics"]["WIN"]
    assert stats["evaluated"] == 1
    assert stats["wins"] == 1
    assert stats["profit_gbp"] == pytest.approx(3.0)  # sp_dec - 1 stake
    assert stats["roi"] == pytest.approx(3.0)


def test_loss_deducts_one_stake(mod):
    result_race = _result("1", "Ascot", "1.35", [_runner("Pick Horse", "4", sp_dec=4.0)])
    results = {"results": [result_race]}
    card = _card(
        [
            {
                "race_id": "1",
                "course": "Ascot",
                "off_time": "1.35",
                "picks": [{"role": "WIN", "horse": "Pick Horse", "horse_id": ""}],
            }
        ]
    )
    out = mod.evaluate(card, results)
    stats = out["role_metrics"]["WIN"]
    assert stats["wins"] == 0
    assert stats["profit_gbp"] == pytest.approx(-1.0)
    assert stats["roi"] == pytest.approx(-1.0)


def test_unresolved_race_tracked_separately(mod):
    results = {"results": []}
    card = _card([{"race_id": "1", "course": "Ascot", "off_time": "1.35", "picks": []}])
    out = mod.evaluate(card, results)
    assert len(out["unresolved_races"]) == 1
    assert out["unresolved_races"][0]["join_method"] == "UNRESOLVED_NO_MATCH"


# ---------------------------------------------------------------------------
# Input hashing
# ---------------------------------------------------------------------------


def test_sha256_file_matches_manual_hash(mod, tmp_path):
    p = tmp_path / "sample.json"
    p.write_text('{"a": 1}', encoding="utf-8")
    expected = hashlib.sha256(p.read_bytes()).hexdigest()
    assert mod._sha256_file(p) == expected


def test_load_card_and_results_and_write_outputs_round_trip(mod, tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "DATA", tmp_path / "data")
    (tmp_path / "data" / "reports").mkdir(parents=True)
    (tmp_path / "data" / "results").mkdir(parents=True)

    card = {
        "date": "2026-07-10",
        "races": [
            {
                "race_id": "1",
                "course": "Ascot",
                "off_time": "1.35",
                "picks": [{"role": "WIN", "horse": "Pick Horse", "horse_id": ""}],
            }
        ],
    }
    results_payload = {"results": [_result("1", "Ascot", "1.35", [_runner("Pick Horse", "1", sp_dec=3.0)])]}

    card_path = tmp_path / "data" / "reports" / "old_velo_three_option_card_2026_07_10.json"
    card_path.write_text(json.dumps(card), encoding="utf-8")
    results_path = tmp_path / "data" / "results" / "rp_results_2026_07_10.json"
    results_path.write_text(json.dumps(results_payload), encoding="utf-8")

    loaded_card, loaded_card_path = mod.load_card("2026-07-10")
    loaded_results, loaded_results_path = mod.load_results("2026-07-10")
    assert loaded_card_path == card_path
    assert loaded_results_path == results_path

    evaluation = mod.evaluate(loaded_card, loaded_results)
    json_path, md_path = mod.write_outputs("2026-07-10", loaded_card_path, loaded_results_path, evaluation)

    assert json_path.exists() and md_path.exists()
    written = json.loads(json_path.read_text(encoding="utf-8"))
    assert written["frozen_card_sha256"] == hashlib.sha256(card_path.read_bytes()).hexdigest()
    assert written["results_sha256"] == hashlib.sha256(results_path.read_bytes()).hexdigest()
    assert written["role_metrics"]["WIN"]["wins"] == 1
    assert written["no_scoring_change"] is True
    assert written["no_supabase_writes"] is True


# ---------------------------------------------------------------------------
# Card builder freeze / no-recompute behaviour
# ---------------------------------------------------------------------------


def test_build_card_freezes_and_does_not_recompute(build_mod, tmp_path, monkeypatch):
    monkeypatch.setattr(build_mod, "ROOT", tmp_path)
    monkeypatch.setattr(build_mod, "DATA", tmp_path / "data")
    (tmp_path / "data" / "reports").mkdir(parents=True)

    frozen_path = tmp_path / "data" / "reports" / "old_velo_three_option_card_2026_07_10.json"
    original_card = {
        "date": "2026-07-10",
        "races": [],
        "role_metrics": {
            "WIN": {"evaluated": 0, "wins": 0, "frames": 0},
            "PLACE": {"evaluated": 0, "wins": 0, "frames": 0},
            "LONGSHOT": {"evaluated": 0, "wins": 0, "frames": 0},
        },
        "source_snapshot": "original",
        "schema_version": "old_velo_three_option_card_v1",
        "rules": {},
    }
    frozen_path.write_text(json.dumps(original_card), encoding="utf-8")
    before_hash = hashlib.sha256(frozen_path.read_bytes()).hexdigest()

    monkeypatch.setattr(sys, "argv", ["build_old_velo_three_option_card.py", "--date", "2026-07-10"])
    build_mod.main()

    after_hash = hashlib.sha256(frozen_path.read_bytes()).hexdigest()
    assert before_hash == after_hash, "morning card must not be recomputed on a second invocation"


def test_frozen_card_path_helper(build_mod):
    p = build_mod._frozen_card_path("2026-07-10")
    assert p.name == "old_velo_three_option_card_2026_07_10.json"
