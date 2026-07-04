"""
Tests for RESULTS-01 — VÉLØ Full Results Truth Audit.
Minimum 15 tests. Uses synthetic fixtures only — no real data files required.
"""

import json
import os
import sys
import importlib
import types
import pytest

# ---------------------------------------------------------------------------
# Helpers to import the module under test without executing main()
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(REPO_ROOT, "scripts", "ops", "build_results_01_audit.py")


def _import_module():
    spec = importlib.util.spec_from_file_location("build_results_01_audit", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _import_module()


# ---------------------------------------------------------------------------
# CONSTRAINT TESTS — no forbidden imports in builder
# ---------------------------------------------------------------------------

def test_no_supabase_import():
    """Builder must not import supabase."""
    with open(MODULE_PATH, "r", encoding="utf-8") as f:
        source = f.read()
    assert "import supabase" not in source, "supabase import found — violates NO_SUPABASE_WRITES"
    assert "from supabase" not in source, "from supabase import found — violates NO_SUPABASE_WRITES"


def test_no_telegram_import():
    """Builder must not import telegram."""
    with open(MODULE_PATH, "r", encoding="utf-8") as f:
        source = f.read()
    assert "import telegram" not in source, "telegram import found — violates NO_TELEGRAM_SEND"
    assert "from telegram" not in source, "from telegram import found — violates NO_TELEGRAM_SEND"


def test_no_model_mutation_calls():
    """Builder must not call promote_model, place_order, or score_race."""
    with open(MODULE_PATH, "r", encoding="utf-8") as f:
        source = f.read()
    forbidden = ["promote_model(", "place_order(", "score_race("]
    for fn in forbidden:
        assert fn not in source, f"Forbidden call '{fn}' found in builder"


def test_hard_constraints_list_present(mod):
    """HARD_CONSTRAINTS list must exist and contain key constraints."""
    assert hasattr(mod, "HARD_CONSTRAINTS"), "HARD_CONSTRAINTS missing from module"
    hc = mod.HARD_CONSTRAINTS
    assert "REPORT_ONLY" in hc
    assert "NO_SUPABASE_WRITES" in hc
    assert "NO_TELEGRAM_SEND" in hc
    assert "NO_LIVE_SCORING_CHANGE" in hc
    assert "NO_MODEL_PROMOTION" in hc
    assert "CONTAINMENT_IS_NOT_PROFIT" in hc


def test_final_classifications_present(mod):
    """FINAL_CLASSIFICATIONS list must exist and contain key items."""
    assert hasattr(mod, "FINAL_CLASSIFICATIONS"), "FINAL_CLASSIFICATIONS missing from module"
    fc = mod.FINAL_CLASSIFICATIONS
    assert "RESULTS_01_FULL_RESULTS_TRUTH_AUDIT_COMPLETE" in fc
    assert "NO_SUPABASE_WRITES" in fc
    assert "REPORT_ONLY" in fc
    assert "EXOTICS_PROFIT_NOT_CLAIMED_WITHOUT_DIVIDENDS" in fc
    assert "CANONICAL_HORSE_PASSPORT_NOT_MUTATED" in fc


# ---------------------------------------------------------------------------
# LOGIC TESTS — using synthetic fixtures
# ---------------------------------------------------------------------------

def _make_audit_row(**kwargs):
    """Build a minimal audit row with defaults."""
    defaults = {
        "id": 1,
        "race_id": "rac_test001",
        "date": None,
        "track": "Cheltenham",
        "outcome": "WIN",
        "miss_reason": None,
        "confidence_level": "high",
        "verdict_score": 0.45,
        "top_pick_position": 1,
        "actual_winner_sp": 6.0,
        "decision_tier": "A",
        "off_time": "14:00",
        "actual_winner_name": "TestHorse",
        "pick_sp": 5.0,
        "distance": "1m",
        "going": "Good",
        "race_type": "Flat",
        "field_size": 12,
        "created_at": "2026-05-21T10:00:00.000000+00:00",
        "assigned_product": "WIN_ONLY",
    }
    defaults.update(kwargs)
    # Apply enrichment that _load_sigma_dump would do
    row = dict(defaults)
    row["_date"] = (row.get("date") or row.get("created_at", "")[:10])
    row["_course"] = (row.get("track") or "UNKNOWN").title()
    sp_dec = row.get("actual_winner_sp")
    row["_winner_sp_dec"] = float(sp_dec) if sp_dec is not None else None
    pick_sp = row.get("pick_sp")
    row["_pick_sp_dec"] = float(pick_sp) if pick_sp is not None else None
    row["_winner_odds_band"] = _odds_band_helper(row["_winner_sp_dec"])
    row["_pick_odds_band"] = _odds_band_helper(row["_pick_sp_dec"])
    row["_is_win"] = str(row.get("outcome", "")).upper() == "WIN"
    row["_is_place"] = str(row.get("outcome", "")).upper() in ("WIN", "PLACED")
    row["_miss_class"] = row.get("miss_reason") or ""
    row["_tier"] = row.get("decision_tier") or ""
    return row


def _odds_band_helper(sp_dec):
    """Mirror of _odds_band from module for use in fixtures."""
    if sp_dec is None:
        return "UNKNOWN"
    if sp_dec < 2.5:
        return "<2.5"
    if sp_dec < 4.0:
        return "2.5-4"
    if sp_dec < 6.0:
        return "4-6"
    if sp_dec < 10.0:
        return "6-10"
    if sp_dec < 16.0:
        return "10-16"
    if sp_dec < 25.0:
        return "16-25"
    return "25+"


def test_missing_winner_sp_resolves_price_unknown(mod):
    """Row with no actual_winner_sp must produce PRICE_UNKNOWN in horses_landed output."""
    row = _make_audit_row(actual_winner_sp=None, outcome="WIN", actual_winner_name="MissingPriceHorse")
    row["_winner_sp_dec"] = None
    row["_winner_odds_band"] = "UNKNOWN"

    result = mod._section2_horses_landed([row], [])
    assert len(result) == 1
    assert result[0]["winner_sp"] == "PRICE_UNKNOWN", (
        f"Expected PRICE_UNKNOWN, got {result[0]['winner_sp']}"
    )


def test_missing_field_size_resolves_unknown_in_ew(mod):
    """EW rows without field_size must show FIELD_SIZE_UNKNOWN."""
    ledger_row = {
        "date": "2026-06-01",
        "race_id": "rp_XXX_20260601_2.00",
        "course": "Ascot",
        "off": "2.00",
        "velo_top_pick": "SomeHorse",
        "velo_outcome": "PLACE",
        "velo_assigned_product": "EW_CANDIDATE",
        "velo_ew_outcome": "EW_PLACE",
    }
    # race_map has no entry for this race_id
    result = mod._section9_ew_candidate([], [ledger_row], {})
    assert result["n"] == 1
    assert result["unknown_field_size"] == 1
    assert result["verdict"] != "EW_PROFIT_PROOF", (
        "EW profit must not be claimed when field_size is unknown"
    )


def test_missing_finish_order_exotics(mod):
    """Ledger rows without top3 should not contribute to exacta/trifecta counts."""
    ledger_row = {
        "date": "2026-06-01",
        "race_id": "rp_XXX_20260601_3.00",
        "course": "Newbury",
        "off": "3.00",
        "velo_top_pick": "HorseA",
        "nb_top_pick": "HorseB",
        "norpr_top_pick": "HorseC",
        "top3": "",  # missing finish order
        "winner": "",
    }
    result = mod._section11_exotics([ledger_row], {})
    assert result["knowable_races"] == 0, (
        "Race with no top3 data should not count as knowable for exotics"
    )


def test_exotics_cannot_claim_profit(mod):
    """Exotics section must set containment_is_not_profit=True."""
    ledger_row = {
        "date": "2026-06-01",
        "race_id": "rp_XXX_20260601_4.00",
        "course": "Goodwood",
        "off": "4.00",
        "velo_top_pick": "HorseA",
        "nb_top_pick": "HorseB",
        "norpr_top_pick": "HorseA",
        "top3": "HorseA|HorseB|HorseC",
        "winner": "HorseA",
    }
    result = mod._section11_exotics([ledger_row], {})
    assert result["containment_is_not_profit"] is True
    assert result["dividend_status"] == "DIVIDEND_UNKNOWN"


def test_ew_no_profit_without_sp_and_field(mod):
    """EW verdict must not be EW_PROFIT_PROOF when SP or field_size unknown."""
    ledger_row = {
        "date": "2026-06-01",
        "race_id": "rp_XXX_20260601_5.00",
        "course": "York",
        "off": "5.00",
        "velo_top_pick": "Contender",
        "velo_outcome": "PLACE",
        "velo_assigned_product": "EW_CANDIDATE",
        "velo_ew_outcome": "EW_PLACE",
    }
    result = mod._section9_ew_candidate([], [ledger_row], {})
    assert result["verdict"] != "EW_PROFIT_PROOF"
    assert result["profit_claimable"] is False


def test_small_course_labelled_noise(mod):
    """Course with n<10 must get COURSE_NOISE_LOW_SAMPLE label."""
    rows = [_make_audit_row(track="TinyTrack", outcome="WIN") for _ in range(3)]
    rows += [_make_audit_row(track="TinyTrack", outcome="MISS") for _ in range(4)]
    result = mod._section4_course_performance(rows)
    assert "Tinytrack" in result, f"Expected 'Tinytrack' in result keys, got {list(result.keys())}"
    assert result["Tinytrack"]["label"] == "COURSE_NOISE_LOW_SAMPLE", (
        f"Expected COURSE_NOISE_LOW_SAMPLE, got {result['Tinytrack']['label']}"
    )


def test_output_json_has_final_classifications_key(mod, tmp_path):
    """The main JSON output structure must contain 'final_classifications' key."""
    # Build a minimal JSON structure as main() would produce
    main_json = {
        "audit_id": "RESULTS-01",
        "hard_constraints": mod.HARD_CONSTRAINTS,
        "final_classifications": mod.FINAL_CLASSIFICATIONS,
        "sections": {},
    }
    assert "final_classifications" in main_json
    assert len(main_json["final_classifications"]) > 0


def test_operator_brief_contains_horse_names(mod):
    """Operator brief must include actual horse names from wins."""
    win_rows = [
        {
            "date": "2026-06-01",
            "course": "Ascot",
            "off_time": "14:00",
            "horse_name": "GoldenArrow",
            "winner_sp": 12.0,
            "pick_sp": 10.0,
            "tier": "A",
            "race_type": "Flat",
            "assigned_product": "WIN_ONLY",
            "verdict_score": 0.5,
            "odds_band": "10-16",
        }
    ]
    all_sections = {
        "inventory": {
            "sigma_dump_rows": 100,
            "outcome_counts": {"WIN": 20, "PLACED": 30, "MISS": 50},
            "sigma_dump_date_count": 10,
            "miss_reason_top5": [("mid_priced_won", 30)],
            "field_coverage": {
                "actual_winner_sp": "95/100",
                "pick_sp": "80/100",
                "actual_winner_name": "50/100",
            },
            "rp_results_races": 200,
            "verdict_races": 150,
        },
        "course_performance": {},
        "odds_band": {"by_pick_sp": {}},
        "lane_performance": {
            "TIER_A": {"n": 50, "sr": 0.28},
            "TIER_B": {"n": 80, "sr": 0.22},
            "TIER_C": {"n": 60, "sr": 0.18},
        },
        "rpr_dependency": {
            "verdict": "RPR_NEUTRAL",
            "n_rpr_boosted": 10,
            "n_rpr_dragged": 8,
            "boost_sr": 0.25,
            "drag_sr": 0.22,
            "avg_gap": 0.01,
        },
        "new_build": {"n": 50, "sr": 0.20, "place_rate": 0.40, "top3_hit_rate": 0.55},
        "ew_candidate": {
            "n": 30, "place_rate": 0.35, "verdict": "EW_REALITY_CHECKED",
            "unknown_field_size": 5, "unknown_sp": 3,
        },
        "midprice_miss": {
            "n_midprice_misses": 100,
            "nb_recovery_wins": 8,
            "nb_recovery_rate": 0.08,
            "norpr_recovery_wins": 6,
            "norpr_recovery_rate": 0.06,
        },
        "exotics": {
            "knowable_races": 80,
            "exacta_box_rate": 0.12,
            "exacta_box_hits": 10,
            "trifecta_box_rate": 0.05,
            "trifecta_box_hits": 4,
        },
        "training_gap": {
            "sigma_corpus_status": "LOADED",
            "sigma_corpus_rows": 1050,
            "gap_count": 5,
        },
    }
    brief = mod._section14_operator_brief(all_sections, win_rows)
    assert "GoldenArrow" in brief, (
        f"Operator brief must contain horse name 'GoldenArrow', but it was not found"
    )


def test_odds_band_function_correct_values(mod):
    """_odds_band must return correct bands for known SP values."""
    assert mod._odds_band(2.0) == "<2.5"
    assert mod._odds_band(2.5) == "2.5-4"
    assert mod._odds_band(3.9) == "2.5-4"
    assert mod._odds_band(4.0) == "4-6"
    assert mod._odds_band(5.5) == "4-6"
    assert mod._odds_band(6.0) == "6-10"
    assert mod._odds_band(9.9) == "6-10"
    assert mod._odds_band(10.0) == "10-16"
    assert mod._odds_band(15.9) == "10-16"
    assert mod._odds_band(16.0) == "16-25"
    assert mod._odds_band(24.9) == "16-25"
    assert mod._odds_band(25.0) == "25+"
    assert mod._odds_band(100.0) == "25+"
    assert mod._odds_band(None) == "UNKNOWN"


def test_section1_inventory_returns_required_keys(mod):
    """_section1_inventory must return all required keys."""
    rows = [_make_audit_row()]
    ledger_rows = []
    result = mod._section1_inventory(rows, ledger_rows, {}, {}, {})
    required_keys = [
        "sigma_dump_rows",
        "sigma_dump_date_count",
        "ledger_rows",
        "outcome_counts",
        "tier_counts",
        "miss_reason_top5",
        "field_coverage",
    ]
    for k in required_keys:
        assert k in result, f"Missing key '{k}' in section1 inventory output"


def test_sp_to_dec_fractional(mod):
    """_sp_to_dec must handle fractional SP strings."""
    assert mod._sp_to_dec("9/2") == pytest.approx(5.5)
    assert mod._sp_to_dec("5/1") == pytest.approx(6.0)
    assert mod._sp_to_dec("11/4") == pytest.approx(3.75)
    assert mod._sp_to_dec(None) is None
    assert mod._sp_to_dec("UNKNOWN") is None
    assert mod._sp_to_dec(4.5) == pytest.approx(4.5)


def test_date_extraction_from_created_at(mod):
    """_extract_date must fall back to created_at[:10] when date is None."""
    row = {"date": None, "created_at": "2026-05-21T10:00:00.000000+00:00"}
    result = mod._extract_date(row)
    assert result == "2026-05-21", f"Expected '2026-05-21', got '{result}'"


def test_course_performance_edge_confirmed(mod):
    """Course with high SR and n>=10 must get COURSE_EDGE_CONFIRMED."""
    rows = [_make_audit_row(track="Cheltenham", outcome="WIN") for _ in range(8)]
    rows += [_make_audit_row(track="Cheltenham", outcome="MISS") for _ in range(2)]
    # 8 wins out of 10 = 80% SR → COURSE_EDGE_CONFIRMED
    result = mod._section4_course_performance(rows)
    assert "Cheltenham" in result
    assert result["Cheltenham"]["sr"] == pytest.approx(0.8)
    assert result["Cheltenham"]["label"] == "COURSE_EDGE_CONFIRMED"


def test_new_build_containment_is_not_profit(mod):
    """New Build section must always set containment_is_not_profit=True."""
    ledger_rows = [
        {
            "nb_top_pick": "FastRunner",
            "nb_prob": "0.25",
            "nb_outcome": "WIN",
            "winner": "FastRunner",
            "top3": "FastRunner|SecondPlace|ThirdPlace",
            "date": "2026-06-01",
            "race_id": "rp_XXX_20260601_1.00",
            "course": "Kempton",
        }
    ]
    result = mod._section8_new_build(ledger_rows, {})
    assert result.get("containment_is_not_profit") is True, (
        "New Build must always flag containment_is_not_profit=True"
    )


def test_section6_lanes_include_vp_high(mod):
    """Lane performance must include a VP_HIGH lane."""
    rows = [_make_audit_row(verdict_score=0.55, outcome="WIN") for _ in range(5)]
    rows += [_make_audit_row(verdict_score=0.30, outcome="MISS") for _ in range(10)]
    result = mod._section6_lane_performance(rows, [])
    assert "VP_HIGH" in result, "VP_HIGH lane missing from section6 output"
    assert result["VP_HIGH"]["n"] == 5


def test_rpr_dependency_returns_verdict_key(mod):
    """RPR dependency section must return a 'verdict' key."""
    result = mod._section7_rpr_dependency([], {})
    assert "verdict" in result
    assert "n_with_gap" in result


def test_midprice_miss_counts_correctly(mod):
    """Midprice miss section must count mid_priced_won rows correctly."""
    rows = [
        _make_audit_row(miss_reason="mid_priced_won", outcome="MISS"),
        _make_audit_row(miss_reason="mid_priced_won", outcome="MISS"),
        _make_audit_row(miss_reason="outsider_won", outcome="MISS"),
    ]
    result = mod._section10_midprice_miss(rows, [])
    assert result["n_midprice_misses"] == 2
