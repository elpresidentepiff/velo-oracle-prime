"""
Tests for J30-FOR forensic pack builder.
Verifies hard constraints: no side effects, no profit claims without dividends,
missing data → UNKNOWN, contradictions recorded.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "ops"))
from build_j30_forensic_pack import (  # type: ignore[import]
    _HARD_CONSTRAINTS,
    _FINAL_CLASSIFICATIONS,
    _section1,
    _section2,
    _section3,
    _section4,
    _section5,
    _section6,
    _section7,
    _section8,
    _section9,
    _exacta_hit,
    _trifecta_hit,
    _box_hit,
    _sp_to_dec,
    _odds_band,
    _render_rpr,
    _render_nb,
    _render_ew,
    _render_mp,
    _render_exotics,
    _render_brief,
)

_MINIMAL_RACE = {
    "race_id": "999001",
    "course": "TestCourse",
    "off": "2.00",
    "race_name": "Test Race",
    "tier": "A",
    "field_size": 8,
    "race_class": "3",
    "going": "Good",
    "distance_f": 8.0,
    "old_pick": "HorseA",
    "old_vp": 0.42,
    "old_sqpe": 0.25,
    "old_sqpe_norpr": 0.20,
    "rpr_gap": 0.05,
    "rpr_missing": False,
    "or_missing": False,
    "mds": 0.30,
    "improvement": 0.08,
    "old_outcome": "WIN",
    "miss_class": "",
    "assigned_product": "WIN_ONLY",
    "ew_outcome": "",
    "norpr_pick": "HorseA",
    "norpr_outcome": "WIN",
    "nb_pick": "HorseB",
    "nb_prob": 0.18,
    "nb_outcome": "PLACE",
    "winner": "HorseA",
    "winner_sp_str": "3/1",
    "winner_sp_dec": 4.0,
    "horse_2nd": "HorseB",
    "sp_2nd": 6.0,
    "horse_3rd": "HorseC",
    "sp_3rd": 8.0,
    "top3": ["HorseA", "HorseB", "HorseC"],
    "finish_order": [
        {"horse": "HorseA", "horse_id": "1", "pos": "1", "sp_str": "3/1", "sp_dec": 4.0},
        {"horse": "HorseB", "horse_id": "2", "pos": "2", "sp_str": "5/1", "sp_dec": 6.0},
        {"horse": "HorseC", "horse_id": "3", "pos": "3", "sp_str": "7/1", "sp_dec": 8.0},
        {"horse": "HorseD", "horse_id": "4", "pos": "4", "sp_str": "10/1", "sp_dec": 11.0},
    ],
    "old_win": True,
    "old_place": True,
    "nb_win": False,
    "nb_place": True,
    "norpr_win": True,
    "norpr_place": True,
}

_MISS_RACE = {
    **_MINIMAL_RACE,
    "race_id": "999002",
    "off": "3.00",
    "old_pick": "LoserA",
    "old_outcome": "MISS",
    "miss_class": "mid_priced_won",
    "old_win": False,
    "old_place": False,
    "norpr_win": False,
    "norpr_place": False,
    "nb_win": False,
    "nb_place": False,
    "winner": "HorseA",
    "winner_sp_str": "7/1",
    "winner_sp_dec": 8.0,
}

_MINIMAL_DATA = {
    "races": [_MINIMAL_RACE, _MISS_RACE],
    "sigma_summary": {
        "rows": [], "identity_failures": 0, "ew_tracking": {},
        "miss_class_breakdown": {}, "wins": 1,
    },
    "nr_raw": {"decisions": []},
    "artifacts": {
        "verdicts": "data/test.json", "results": "data/test.json",
        "sigma": "data/test.json", "nr": "data/test.json", "ledger": "data/test.csv",
    },
}


# ── T-01: No banned imports in builder ───────────────────────────────────────

def test_no_supabase_import() -> None:
    src = (Path(__file__).parent.parent / "scripts" / "ops" / "build_j30_forensic_pack.py").read_text()
    for banned in ["import supabase", "from supabase"]:
        assert banned not in src, f"Banned import: {banned}"


def test_no_telegram_import() -> None:
    src = (Path(__file__).parent.parent / "scripts" / "ops" / "build_j30_forensic_pack.py").read_text()
    for banned in ["import telegram", "from telegram"]:
        assert banned not in src, f"Banned import: {banned}"


def test_no_model_mutation_calls() -> None:
    src = (Path(__file__).parent.parent / "scripts" / "ops" / "build_j30_forensic_pack.py").read_text()
    for banned in ["promote_model(", "place_order(", "place_bet(", "score_race("]:
        assert banned not in src, f"Banned call: {banned}"


# ── T-02: Hard constraints present ───────────────────────────────────────────

def test_hard_constraints_present() -> None:
    required = {"REPORT_ONLY", "NO_LIVE_SCORING_CHANGE", "NO_MODEL_PROMOTION",
                 "NO_SUPABASE_WRITES", "NO_TELEGRAM_SEND", "NO_VFU_21_START"}
    assert required.issubset(set(_HARD_CONSTRAINTS))


def test_final_classifications_complete() -> None:
    required = {
        "J30_FORENSIC_FULL_PACK_COMPLETE",
        "EXOTICS_PROFIT_NOT_CLAIMED_WITHOUT_DIVIDENDS",
        "SP_PROXY_LABELLED_NOT_DIVIDEND_PROOF",
        "CONTRADICTION_C01_RECORDED_NOT_SUPPRESSED",
        "REPORT_ONLY",
    }
    assert required.issubset(set(_FINAL_CLASSIFICATIONS))


# ── T-03: Section 1 — loop integrity ─────────────────────────────────────────

def test_s1_race_count() -> None:
    s1 = _section1(_MINIMAL_DATA)
    assert s1["races_total"] == 2
    assert s1["races_matched"] == 2


def test_s1_ranked_list_note_present() -> None:
    s1 = _section1(_MINIMAL_DATA)
    assert "SINGLE_TOP_PICK_ONLY" in s1["ranked_list_note"]


def test_s1_partial_order_note() -> None:
    s1 = _section1(_MINIMAL_DATA)
    assert "PARTIAL_ORDER_EVIDENCE" in s1["exotics_coverage_note"]


# ── T-04: Section 2 — RPR dependency ─────────────────────────────────────────

def test_s2_verdict_present() -> None:
    s2 = _section2(_MINIMAL_DATA)
    assert s2["verdict"] in {
        "RPR_HELPED", "RPR_NEUTRAL", "RPR_MISLED", "NO_RPR_BETTER",
        "RPR_PUBLIC_MARKET_ANCHOR", "INSUFFICIENT_RPR_EVIDENCE",
    }


def test_s2_limitation_note() -> None:
    s2 = _section2(_MINIMAL_DATA)
    assert "SINGLE_TOP_PICK_ONLY" in s2["limitation"]


# ── T-05: Section 3 — New Build ───────────────────────────────────────────────

def test_s3_verdict_present() -> None:
    s3 = _section3(_MINIMAL_DATA)
    assert s3["verdict_primary"] in {
        "NEW_BUILD_BAD_TOP_PICK_ONLY", "NEW_BUILD_VALUE_SCOUT",
        "NEW_BUILD_TOP3_CONTAINMENT_SIGNAL", "NEW_BUILD_NO_EVIDENCE",
        "NEEDS_PROSPECTIVE_VALIDATION",
    }


def test_s3_limitation_note() -> None:
    s3 = _section3(_MINIMAL_DATA)
    assert "SINGLE_TOP_PICK_ONLY" in s3["limitation"]


# ── T-06: Section 4 — EW reality, no profit claim ────────────────────────────

def test_s4_no_ew_profit_claim_without_data() -> None:
    s4 = _section4(_MINIMAL_DATA)
    assert "PARTIAL" in s4["profitability_status"] or "SIGNAL_ONLY" in s4["profitability_status"]
    assert "EW_PROFIT_PROOF" not in s4["verdict"]


def test_s4_pick_sp_coverage_note() -> None:
    s4 = _section4(_MINIMAL_DATA)
    assert "PRICE_UNKNOWN" in s4["pick_sp_coverage"] or "VFU_21" in s4["pick_sp_coverage"]


# ── T-07: Section 5 — mid-price miss ─────────────────────────────────────────

def test_s5_miss_count() -> None:
    s5 = _section5(_MINIMAL_DATA)
    # _MISS_RACE has miss_class=mid_priced_won
    assert s5["total_midprice_misses"] == 1


def test_s5_recovery_labels_valid() -> None:
    s5 = _section5(_MINIMAL_DATA)
    valid = {
        "OLD_MISSED_NEW_BUILD_CAUGHT", "OLD_MISSED_EW_CAUGHT",
        "OLD_MISSED_NO_RPR_CAUGHT", "RPR_ANCHOR_MISS", "INTENT_VALUE_MISS",
        "MIDPRICE_UNRECOVERED", "EXOTIC_ONLY_RECOVERY",
    }
    for d in s5["detail"]:
        assert d["recovery"] in valid, f"Invalid recovery label: {d['recovery']}"


# ── T-08: Section 6 — exotics, no profit claim ───────────────────────────────

def test_s6_no_profit_claim() -> None:
    s6 = _section6(_MINIMAL_DATA)
    assert s6["containment_is_not_profit"] is True
    assert s6["box_hit_is_not_profit"] is True
    assert "DIVIDEND_UNKNOWN" in s6["exotics_proof_status"] or "SP_PROXY" in s6["exotics_proof_status"]


def test_s6_sp_proxy_labelled() -> None:
    s6 = _section6(_MINIMAL_DATA)
    assert "SIMULATED_SP_PROXY_NOT_DIVIDEND" in s6["sp_proxy_labelled"]


def test_s6_exacta_verdict_valid() -> None:
    s6 = _section6(_MINIMAL_DATA)
    assert "EXACTA" in s6["exacta_verdict"] or "EXOTICS" in s6["exacta_verdict"]


# ── T-09: Exacta / trifecta helpers ──────────────────────────────────────────

def test_exacta_hit_ordered() -> None:
    assert _exacta_hit(["A", "B"], "A", "B", ordered=True) is True
    assert _exacta_hit(["A", "B"], "B", "A", ordered=True) is False


def test_exacta_hit_unordered() -> None:
    assert _exacta_hit(["A", "B"], "B", "A", ordered=False) is True
    assert _exacta_hit(["A", "B"], "A", "C", ordered=False) is False


def test_trifecta_hit_ordered() -> None:
    assert _trifecta_hit(["A", "B", "C"], "A", "B", "C", ordered=True) is True
    assert _trifecta_hit(["A", "B", "C"], "A", "C", "B", ordered=True) is False


def test_trifecta_hit_unordered() -> None:
    assert _trifecta_hit(["C", "A", "B"], "A", "B", "C", ordered=False) is True
    assert _trifecta_hit(["A", "B", "D"], "A", "B", "C", ordered=False) is False


def test_box_hit_subset() -> None:
    assert _box_hit(["A", "B", "C"], ["A", "B"]) is True
    assert _box_hit(["A", "B"], ["A", "C"]) is False


# ── T-10: SP conversion ───────────────────────────────────────────────────────

def test_sp_to_dec_fractional() -> None:
    assert abs(_sp_to_dec("3/1") - 4.0) < 0.001
    assert abs(_sp_to_dec("7/4F") - 2.75) < 0.001
    assert abs(_sp_to_dec("11/10") - 2.1) < 0.01


def test_sp_to_dec_decimal() -> None:
    assert abs(_sp_to_dec("5.0") - 5.0) < 0.001


def test_sp_to_dec_none() -> None:
    assert _sp_to_dec("") is None
    assert _sp_to_dec(None) is None


def test_odds_band() -> None:
    assert _odds_band(1.5) == "<2.5"
    assert _odds_band(3.0) == "2.5-4"
    assert _odds_band(5.0) == "4-6"
    assert _odds_band(8.0) == "6-10"
    assert _odds_band(12.0) == "10-16"
    assert _odds_band(20.0) == "16+"
    assert _odds_band(None) == "UNKNOWN"


# ── T-11: Missing finish order → PARTIAL_ORDER_EVIDENCE ──────────────────────

def test_partial_order_when_finish_missing() -> None:
    sparse = {
        **_MINIMAL_RACE,
        "finish_order": [{"horse": "HorseA", "horse_id": "1", "pos": "1", "sp_str": "3/1", "sp_dec": 4.0}],
        "horse_2nd": None,
        "horse_3rd": None,
    }
    data = {**_MINIMAL_DATA, "races": [sparse]}
    s6 = _section6(data)
    # With < 2 runners in finish_order, exacta_eligible should be 0 or note present
    assert s6["n_exacta_eligible"] == 0 or "SINGLE_TOP_PICK_ONLY" in s6["limitation"]


# ── T-12: Missing field_size → flagged in EW ─────────────────────────────────

def test_ew_field_size_gap_noted() -> None:
    ew_race = {
        **_MINIMAL_RACE,
        "assigned_product": "EW_CANDIDATE",
        "field_size": None,
        "ew_outcome": "EW_WIN",
    }
    data = {**_MINIMAL_DATA, "races": [ew_race, _MISS_RACE]}
    s4 = _section4(data)
    assert s4["ew_known_field_size"] < s4["ew_n"]


# ── T-13: Contradiction C-01 not suppressed ──────────────────────────────────

def test_contradiction_c01_in_brief() -> None:
    s1 = _section1(_MINIMAL_DATA)
    s2 = _section2(_MINIMAL_DATA)
    s3 = _section3(_MINIMAL_DATA)
    s4 = _section4(_MINIMAL_DATA)
    s5 = _section5(_MINIMAL_DATA)
    s6 = _section6(_MINIMAL_DATA)
    s7 = _section7(_MINIMAL_DATA)
    s8 = _section8(s1, s2, s3, s4, s5, s6)
    s9 = _section9()
    brief = _render_brief(s1, s2, s3, s4, s5, s6, s7, s8, s9)
    assert "C-01" in brief
    assert "NOT SUPPRESSED" in brief


def test_final_classifications_in_brief() -> None:
    s1 = _section1(_MINIMAL_DATA)
    s2 = _section2(_MINIMAL_DATA)
    s3 = _section3(_MINIMAL_DATA)
    s4 = _section4(_MINIMAL_DATA)
    s5 = _section5(_MINIMAL_DATA)
    s6 = _section6(_MINIMAL_DATA)
    s7 = _section7(_MINIMAL_DATA)
    s8 = _section8(s1, s2, s3, s4, s5, s6)
    s9 = _section9()
    brief = _render_brief(s1, s2, s3, s4, s5, s6, s7, s8, s9)
    assert "REPORT_ONLY" in brief
    assert "J30_FORENSIC_FULL_PACK_COMPLETE" in brief


# ── T-14: Section 9 — no auto-promotion in next actions ──────────────────────

def test_s9_no_auto_promotion() -> None:
    s9 = _section9()
    blocked = s9["do_not_start"]
    assert "MODEL_PROMOTION" in blocked or any("PROMO" in b for b in blocked)
    assert "VFU-21" in blocked
    assert "VCP-04" in blocked


# ── T-15: Race table completeness ────────────────────────────────────────────

def test_s7_race_table_fields() -> None:
    s7 = _section7(_MINIMAL_DATA)
    required = {"race_id", "course", "off", "winner", "old_top1", "old_hit",
                "exacta_top3_box", "trifecta_top3_box", "miss_class"}
    for row in s7["rows"]:
        missing = required - set(row.keys())
        assert not missing, f"Race table row missing fields: {missing}"
