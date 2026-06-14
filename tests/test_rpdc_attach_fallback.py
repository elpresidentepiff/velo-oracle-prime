"""RPDC attach fallback — deterministic resolution across race-ID mismatch.

Regression guard for the June 9 failure: PDF-bypass cards used synthetic
rp_{VENUE}_* IDs while runner_release_candidates carried real RP IDs, so
the exact race_id join silently attached no_data for every race.

Contract (operator command 2026-06-10):
  - exact race_id + horse_id attach works
  - race_id mismatch but date+unique-name fallback works
  - ambiguous fallback blocks (no_data, never invented data)
  - missing candidate returns no_data
  - attach_method is recorded
  - pure functions only — no Supabase, no network
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.velo.rpdc_attach import (  # noqa: E402
    AMBIGUOUS,
    build_name_map,
    normalize_horse_name,
    resolve_runner_rpdc,
)

_BANKSMAN = {"race_id": "920127", "horse_id": "6350106", "horse": "Banksman", "rpdc_tags": ["PLACE_FORM"]}
_PLEASURE = {"race_id": "919911", "horse_id": "2910556", "horse": "Pleasure Garden", "rpdc_tags": ["CYCLE_RUN_2"]}


def test_normalize_horse_name():
    assert normalize_horse_name("Banksman") == "banksman"
    assert normalize_horse_name("Mister Sandman (IRE)") == "mistersandman"
    assert normalize_horse_name("Far And Above") == "farandabove"
    assert normalize_horse_name("") == ""


def test_exact_race_id_attach_works():
    race_rpdc = {"6350106": _BANKSMAN}
    row, method = resolve_runner_rpdc(race_rpdc, None, "6350106", "Banksman")
    assert row is _BANKSMAN
    assert method == "race_id_exact"


def test_race_id_mismatch_name_fallback_works():
    # June 9 pattern: scoring has synthetic IDs, exact map is empty,
    # day name map (built from real-ID candidates) resolves by unique name.
    name_map = build_name_map([_BANKSMAN, _PLEASURE])
    row, method = resolve_runner_rpdc({}, name_map, "rp_BRIGHTON_banksman", "Banksman")
    assert row is _BANKSMAN
    assert method == "date_name_fallback"


def test_ambiguous_fallback_blocks():
    twin_a = dict(_BANKSMAN)
    twin_b = dict(_BANKSMAN, race_id="999999", horse_id="7777777")
    name_map = build_name_map([twin_a, twin_b])
    assert name_map[normalize_horse_name("Banksman")] is AMBIGUOUS
    row, method = resolve_runner_rpdc({}, name_map, "rp_X_banksman", "Banksman")
    assert row is None
    assert method == "ambiguous_blocked"


def test_missing_candidate_returns_no_data():
    name_map = build_name_map([_PLEASURE])
    row, method = resolve_runner_rpdc({}, name_map, "rp_X_ghost", "Ghost Horse")
    assert row is None
    assert method == "no_candidate"


def test_no_name_map_returns_no_candidate():
    row, method = resolve_runner_rpdc({}, None, "rp_X_banksman", "Banksman")
    assert row is None
    assert method == "no_candidate"


def test_attach_method_always_returned():
    cases = [
        ({"1": {"horse": "A"}}, None, "1", "A"),
        ({}, build_name_map([_BANKSMAN]), "x", "Banksman"),
        ({}, build_name_map([]), "x", "Nobody"),
    ]
    for race_rpdc, name_map, hid, name in cases:
        _, method = resolve_runner_rpdc(race_rpdc, name_map, hid, name)
        assert method in ("race_id_exact", "date_name_fallback", "ambiguous_blocked", "no_candidate")


def test_module_is_pure_no_network_imports():
    src = (ROOT / "src" / "velo" / "rpdc_attach.py").read_text()
    for forbidden in ("urllib", "requests", "supabase", "http", "sb_get"):
        assert forbidden not in src
