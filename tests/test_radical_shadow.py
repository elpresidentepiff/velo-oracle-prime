from src.velo.radical.regime_router import odds_band, route_regime
from src.velo.radical.passport_feed import normalize_name, passport_snapshot
from src.velo.radical.sigma_gate import build_sigma_feature_row


def test_odds_band_splits_longshots_from_midprice():
    assert odds_band(0.8) == "INVALID_ODDS_LT_1_01"
    assert odds_band(10.0) == "EIGHT_TO_FOURTEEN"
    assert odds_band(16.0) == "LONGSHOT_15_PLUS"


def test_route_regime_hard_pass_for_known_toxic_combo():
    decision = route_regime(
        sp_decimal=18.0,
        model_probability=0.2,
        field_size=10,
        class_num=5,
        win_gate_probability=0.7,
        frame_gate_probability=0.8,
    )
    assert decision["action"] == "PASS"
    assert "HARD_PASS:class_5_field_9_12" in decision["warnings"]
    assert "HARD_PASS:longshot_15_plus_field_9_12" in decision["warnings"]


def test_route_regime_cash_run_when_frame_high_and_win_not_high():
    decision = route_regime(
        sp_decimal=2.0,
        model_probability=0.36,
        field_size=7,
        class_num=4,
        win_gate_probability=0.4,
        frame_gate_probability=0.75,
    )
    assert decision["action"] == "CASH_RUN"
    assert "FRAME_GATE_HIGH_WIN_GATE_NOT_HIGH" in decision["reasons"]


def test_midprice_suppress_top_demotes_shadow_candidate():
    decision = route_regime(
        sp_decimal=4.0,
        model_probability=0.5,
        field_size=7,
        class_num=4,
        win_gate_probability=0.8,
        frame_gate_probability=0.7,
        passport_available=True,
        passport_strength_score=2.0,
        midprice_shadow_action="MIDPRICE_SUPPRESS_TOP",
        midprice_shadow_evidence={"top_mds": 0.02},
    )
    assert decision["action"] == "PASS"
    assert "HARD_PASS:midprice_suppress_top" in decision["warnings"]
    assert decision["midprice_shadow_evidence"]["top_mds"] == 0.02


def test_midprice_no_edge_cannot_be_win_candidate():
    decision = route_regime(
        sp_decimal=3.5,
        model_probability=0.5,
        field_size=7,
        class_num=4,
        win_gate_probability=0.8,
        frame_gate_probability=0.7,
        passport_available=True,
        passport_strength_score=2.0,
        midprice_shadow_action="MIDPRICE_NO_EDGE",
    )
    assert decision["action"] == "PASS_OR_WATCH"
    assert "MIDPRICE_NO_EDGE:top_pick_lacks_win_edge" in decision["warnings"]


def test_invalid_odds_hard_passes_before_shadow_candidate():
    decision = route_regime(
        sp_decimal=0.8,
        model_probability=0.7,
        field_size=7,
        class_num=4,
        win_gate_probability=0.9,
        frame_gate_probability=0.9,
        passport_available=True,
        passport_strength_score=2.0,
    )
    assert decision["action"] == "PASS"
    assert "HARD_PASS:invalid_odds_lt_1_01" in decision["warnings"]


def test_route_regime_requires_passport_support_for_win_candidate():
    no_passport = route_regime(
        sp_decimal=2.0,
        model_probability=0.6,
        field_size=7,
        class_num=4,
        win_gate_probability=0.8,
        frame_gate_probability=0.9,
        passport_available=False,
    )
    with_passport = route_regime(
        sp_decimal=2.0,
        model_probability=0.6,
        field_size=7,
        class_num=4,
        win_gate_probability=0.8,
        frame_gate_probability=0.9,
        passport_available=True,
        passport_strength_score=2.0,
    )
    assert no_passport["action"] == "CASH_RUN"
    assert "WIN_GATE_HIGH_BUT_PASSPORT_NOT_SUPPORTIVE" in no_passport["reasons"]
    assert with_passport["action"] == "WIN_CANDIDATE_SHADOW"


def test_sigma_feature_row_uses_verdict_contract():
    row = build_sigma_feature_row(
        {
            "scored": 8,
            "top": {
                "velo_prime_prob": 0.4,
                "sp_dec": 4.0,
                "execution_allowed": True,
            },
        },
        class_num=4,
    )
    assert row["model_probability"] == 0.4
    assert row["sp_decimal"] == 4.0
    assert row["implied_probability"] == 0.25
    assert row["edge"] == 0.15000000000000002
    assert row["field_size"] == 8.0
    assert row["router_v1_shadow_pass"] == 1.0
    assert row["router_v2_class4_shadow_pass"] == 1.0


def test_passport_snapshot_exposes_shadow_context_without_live_permission():
    snap = passport_snapshot(
        {
            "horse": "Fine Thing",
            "passport_available": True,
            "passport_strength_score": 2.5,
            "reason_codes": ["STRONG_PLACE_PROFILE"],
            "race_class": "4",
            "passport_live_features": {"pp_place_rate": 0.75, "pp_avg_sp_last5": 6.0},
        }
    )
    assert normalize_name("Fine Thing!") == "finething"
    assert snap["matched"] is True
    assert snap["passport_available"] is True
    assert snap["passport_live_features"]["pp_place_rate"] == 0.75
