#!/usr/bin/env python3
"""
Tests for VFU-24: First Prospective EW Settlement.
Run with: source venv/bin/activate && python -m pytest tests/test_vfu_24_ew_settlement.py -v
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_24_ew_settlement import (
    _place_terms,
    _ew_calc,
    settle_entry,
    settle_watchlist,
    load_results_index,
    VFU24_VERSION,
    EW_STAKE,
)
import scripts.ops.vfu_24_ew_settlement as _mod


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _template(entries: list | None = None) -> dict:
    return {
        "vfu": "VFU-23",
        "race_date": "2026-06-17",
        "paper_only": True,
        "entries": entries or [],
    }


def _entry(
    race_id="race_001",
    horse_name="Test Horse",
    vp=0.45,
    runner_count=8,
    course="Ascot",
    off_time="14:30",
) -> dict:
    return {
        "race_id": race_id,
        "course": course,
        "off_time": off_time,
        "horse_name": horse_name,
        "VP": vp,
        "candidate_band": "PRIMARY_EW_WATCH",
        "runner_count": runner_count,
        "finish_position": None,
        "win_return": None,
        "place_return": None,
        "EW_return": None,
        "outcome": None,
        "settlement_status": "PENDING",
    }


def _results_index(
    race_id="race_001",
    horse_name="Test Horse",
    position=1,
    sp_dec=4.0,
    field_size=8,
) -> dict:
    return {
        race_id: {
            "race_id": race_id,
            "course": "Ascot",
            "off": "14:30",
            "field_size": field_size,
            "runners_by_name": {
                horse_name.lower(): {
                    "horse": horse_name,
                    "position": position,
                    "sp_fractional": "3/1",
                    "sp_decimal": sp_dec,
                    "non_runner": False,
                }
            },
        }
    }


def _settle_single(
    position=1, sp_dec=4.0, field_size=8, vp=0.45
) -> dict:
    entry = _entry(runner_count=field_size)
    idx = _results_index(position=position, sp_dec=sp_dec, field_size=field_size)
    return settle_entry(entry, idx)


# ── Tests 01–15 (governance + correctness) ───────────────────────────────────

def test_01_settled_entry_has_settlement_status_settled():
    """Successfully matched entry must have settlement_status=SETTLED."""
    result = _settle_single(position=3, sp_dec=5.0, field_size=8)
    assert result["settlement_status"] == "SETTLED"


def test_02_win_entry_has_correct_ew_return():
    """WIN entry: EW_return = win_leg + place_leg."""
    # field=8: 3 places, 1/4 odds; sp_dec=5.0
    # win_ret = 1.0 * 5.0 = 5.0
    # place_ret = 1.0 + 1.0*(5.0-1)/4 = 1.0 + 1.0 = 2.0
    # EW_return = 7.0
    result = _settle_single(position=1, sp_dec=5.0, field_size=8)
    assert result["outcome"] == "WIN"
    assert abs(result["EW_return"] - 7.0) < 0.01
    assert abs(result["EW_profit"] - 5.0) < 0.01  # 7.0 - 2.0 staked


def test_03_placed_entry_has_correct_ew_return():
    """PLACED entry (pos=2, field=8): only place leg pays."""
    # place_ret = 1.0 + 1.0*(5.0-1)/4 = 2.0
    result = _settle_single(position=2, sp_dec=5.0, field_size=8)
    assert result["outcome"] == "PLACED"
    assert result["win_return"] == 0.0
    assert abs(result["place_return"] - 2.0) < 0.01
    assert abs(result["EW_return"] - 2.0) < 0.01
    assert abs(result["EW_profit"] - 0.0) < 0.01  # 2.0 - 2.0 staked


def test_04_miss_entry_returns_zero():
    """MISS entry: both legs lose."""
    result = _settle_single(position=5, sp_dec=5.0, field_size=8)
    assert result["outcome"] == "MISS"
    assert result["win_return"] == 0.0
    assert result["place_return"] == 0.0
    assert result["EW_return"] == 0.0
    assert result["EW_profit"] == -2.0


def test_05_no_ew_terms_for_field_under_5():
    """Field size < 5: no EW place terms — PLACED_NO_TERMS outcome."""
    result = _settle_single(position=2, sp_dec=2.0, field_size=3)
    assert result["outcome"] == "PLACED_NO_TERMS"
    assert result["EW_return"] == 0.0
    assert result["EW_profit"] == -2.0
    assert result["ew_place_terms_apply"] is False


def test_06_field_under_5_win_still_pays_win_leg():
    """WIN in a <5 runner field: win leg still pays, place leg is 0."""
    calc = _ew_calc(3.0, 1, 3)  # field=3
    assert calc["outcome_label"] == "WIN"
    # win_ret = 1 * 3.0 = 3.0; place_ret = 0 (no terms); total = 3.0
    assert abs(calc["win_return"] - 3.0) < 0.01
    assert calc["place_return"] == 0.0
    assert abs(calc["ew_return"] - 3.0) < 0.01


def test_07_place_terms_thresholds():
    """_place_terms must return correct (n_places, divisor) at boundaries."""
    assert _place_terms(3) == (0, 4)   # < 5
    assert _place_terms(5) == (2, 4)   # 5-7
    assert _place_terms(7) == (2, 4)
    assert _place_terms(8) == (3, 4)   # 8-15
    assert _place_terms(15) == (3, 4)
    assert _place_terms(16) == (4, 5)  # 16+
    assert _place_terms(20) == (4, 5)


def test_08_paper_only_flag_on_all_entries():
    """Every settled entry must carry paper_only=True."""
    entry = _entry()
    idx = _results_index()
    result = settle_entry(entry, idx)
    assert result["paper_only"] is True


def test_09_blocked_from_live_use_on_all_entries():
    """Every settled entry must carry blocked_from_live_use=True."""
    entry = _entry()
    idx = _results_index()
    result = settle_entry(entry, idx)
    assert result["blocked_from_live_use"] is True


def test_10_full_report_paper_only_and_blocked():
    """Full settled report must have paper_only=True and blocked_from_live_use=True."""
    template = _template([_entry()])
    idx = _results_index()
    report = settle_watchlist("2026-06-17", template, idx)
    assert report["paper_only"] is True
    assert report["blocked_from_live_use"] is True


def test_11_full_report_total_staked_is_2_per_candidate():
    """Total staked = 2 units × n_candidates (1-unit EW each)."""
    entries = [_entry(race_id=f"r00{i}", horse_name=f"Horse {i}") for i in range(4)]
    template = _template(entries)
    idx = {}
    for e in entries:
        idx.update(
            _results_index(
                race_id=e["race_id"],
                horse_name=e["horse_name"],
                position=3, sp_dec=5.0, field_size=8,
            )
        )
    report = settle_watchlist("2026-06-17", template, idx)
    assert abs(report["total_staked_units"] - 8.0) < 0.01


def test_12_race_not_found_returns_graceful_error():
    """Missing race_id in results index returns RACE_NOT_FOUND status."""
    entry = _entry(race_id="race_999")
    result = settle_entry(entry, {})
    assert result["settlement_status"] == "RACE_NOT_FOUND"


def test_13_horse_not_found_returns_graceful_error():
    """Horse not in runners returns HORSE_NOT_FOUND status."""
    entry = _entry(race_id="race_001", horse_name="Unknown Horse")
    idx = _results_index(race_id="race_001", horse_name="Known Horse")
    result = settle_entry(entry, idx)
    assert result["settlement_status"] == "HORSE_NOT_FOUND"


def test_14_no_supabase_in_module():
    """VFU-24 module must not import or call Supabase."""
    src = pathlib.Path(_mod.__file__).read_text(encoding="utf-8")
    assert "create_client" not in src
    assert "from supabase" not in src
    assert "import supabase" not in src


def test_15_no_telegram_in_module():
    """VFU-24 module must not contain Telegram send logic."""
    src = pathlib.Path(_mod.__file__).read_text(encoding="utf-8")
    assert "bot.send" not in src
    assert "telegram.Bot" not in src
    assert "sendMessage" not in src


def test_16_no_live_scoring_in_module():
    """VFU-24 must not invoke the live scoring pipeline."""
    src = pathlib.Path(_mod.__file__).read_text(encoding="utf-8")
    assert "run_prime_today" not in src
    assert "SQPEEngine" not in src
    assert "VeloPrimeEnsemble" not in src


def test_17_non_runner_handled():
    """Non-runner entry returns NON_RUNNER settlement status."""
    entry = _entry()
    idx = {
        "race_001": {
            "race_id": "race_001",
            "course": "Ascot",
            "off": "14:30",
            "field_size": 8,
            "runners_by_name": {
                "test horse": {
                    "horse": "Test Horse",
                    "position": None,
                    "sp_fractional": None,
                    "sp_decimal": None,
                    "non_runner": True,
                }
            },
        }
    }
    result = settle_entry(entry, idx)
    assert result["settlement_status"] == "NON_RUNNER"
    assert result["EW_profit"] == 0.0


def test_18_governance_note_for_small_field():
    """Entry with field_size < 5 must include a governance_note."""
    result = _settle_single(position=2, sp_dec=2.0, field_size=4)
    assert "governance_note" in result
    assert "5" in result["governance_note"]


def test_19_classifications_present():
    """Settled report must include all required classification strings."""
    required = [
        "VFU_24_EW_SETTLEMENT_COMPLETE",
        "PAPER_ONLY_MODE_CONFIRMED",
        "NO_STAKING_EXECUTION",
        "NO_SUPABASE_WRITES",
        "NO_TELEGRAM_BETTING_OUTPUT",
        "NO_MODEL_PROMOTION",
        "NO_VP_THRESHOLD_CHANGE",
        "NO_LIVE_SCORING_CHANGE",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
    ]
    template = _template([_entry()])
    idx = _results_index()
    report = settle_watchlist("2026-06-17", template, idx)
    for cls in required:
        assert cls in report["classifications"], f"Missing: {cls}"


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = sorted(
        [(k, v) for k, v in globals().items() if k.startswith("test_")],
        key=lambda x: x[0],
    )
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {name}: {exc}")
            failed += 1
    print(f"\n{passed + failed} tests  |  {passed} passed  |  {failed} failed")
    sys.exit(1 if failed else 0)
