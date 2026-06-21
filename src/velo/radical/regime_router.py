"""Evidence-based regime routing for Radical Velo shadow packets."""

from __future__ import annotations

from typing import Any


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        out = float(value)
        if out != out or out in (float("inf"), float("-inf")):
            return default
        return out
    except Exception:
        return default


def odds_band(sp_decimal: Any) -> str:
    v = safe_float(sp_decimal, 0.0)
    if v <= 0:
        return "NO_ODDS"
    if v < 1.01:
        return "INVALID_ODDS_LT_1_01"
    if v < 1.5:
        return "ODDS_ON_LT_1_5"
    if v < 2.5:
        return "EVS_TO_6_4"
    if v < 4.0:
        return "TWO_TO_THREE"
    if v < 6.0:
        return "THREE_TO_FIVE"
    if v < 9.0:
        return "FIVE_TO_EIGHT"
    if v < 15.0:
        return "EIGHT_TO_FOURTEEN"
    return "LONGSHOT_15_PLUS"


def vp_band(vp: Any) -> str:
    v = safe_float(vp, 0.0)
    if v >= 0.55:
        return "VP_55_PLUS"
    if v >= 0.45:
        return "VP_45_55"
    if v >= 0.35:
        return "VP_35_45"
    if v >= 0.25:
        return "VP_25_35"
    if v >= 0.15:
        return "VP_15_25"
    return "VP_LT_15"


def field_band(field_size: Any) -> str:
    fs = int(safe_float(field_size, 0))
    if fs <= 0:
        return "FS_UNKNOWN"
    if fs <= 5:
        return "FS_2_5"
    if fs <= 8:
        return "FS_6_8"
    if fs <= 12:
        return "FS_9_12"
    return "FS_13_PLUS"


def class_band(class_num: Any) -> str:
    cn = int(safe_float(class_num, 0))
    return f"CLASS_{cn}" if cn else "CLASS_UNKNOWN"


def route_regime(
    *,
    sp_decimal: Any,
    model_probability: Any,
    field_size: Any,
    class_num: Any,
    frame_gate_probability: float | None = None,
    win_gate_probability: float | None = None,
    passport_available: bool = False,
    passport_strength_score: Any = None,
    midprice_shadow_action: str | None = None,
    midprice_shadow_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Route a runner using the June 19 radical edge discovery."""

    ob = odds_band(sp_decimal)
    vb = vp_band(model_probability)
    fb = field_band(field_size)
    cb = class_band(class_num)
    reasons: list[str] = []
    warnings: list[str] = []

    if fb == "FS_6_8":
        reasons.append("EDGE_REGIME:field_size_6_8")
    if cb == "CLASS_4" and fb in {"FS_2_5", "FS_6_8"}:
        reasons.append(f"EDGE_REGIME:{cb}_{fb}")
    if ob == "EIGHT_TO_FOURTEEN" and fb == "FS_6_8":
        reasons.append("DISCOVERY_LONGSHOT:8_to_14_field_6_8_shadow_only")

    if fb == "FS_9_12":
        warnings.append("TOXIC_REGIME:field_size_9_12")
    if ob == "LONGSHOT_15_PLUS":
        warnings.append("TOXIC_REGIME:longshot_15_plus")
    if cb == "CLASS_5":
        warnings.append("TOXIC_REGIME:class_5")
    if cb == "CLASS_5" and fb == "FS_9_12":
        warnings.append("HARD_PASS:class_5_field_9_12")
    if ob == "LONGSHOT_15_PLUS" and fb == "FS_9_12":
        warnings.append("HARD_PASS:longshot_15_plus_field_9_12")
    if ob == "INVALID_ODDS_LT_1_01":
        warnings.append("HARD_PASS:invalid_odds_lt_1_01")

    midprice_action = (midprice_shadow_action or "").strip().upper()
    if midprice_action == "MIDPRICE_SUPPRESS_TOP":
        warnings.append("HARD_PASS:midprice_suppress_top")
    elif midprice_action == "MIDPRICE_NO_EDGE":
        warnings.append("MIDPRICE_NO_EDGE:top_pick_lacks_win_edge")
    elif midprice_action == "MIDPRICE_SPLIT_RACE":
        warnings.append("MIDPRICE_SPLIT_RACE:frame_possible_win_uncertain")

    frame_gate_probability = frame_gate_probability if frame_gate_probability is not None else 0.0
    win_gate_probability = win_gate_probability if win_gate_probability is not None else 0.0
    passport_strength = safe_float(passport_strength_score, -1.0)
    passport_supports_win = passport_available and passport_strength >= 1.0

    if any(w.startswith("HARD_PASS") for w in warnings):
        action = "PASS"
        confidence = "high"
    elif midprice_action == "MIDPRICE_NO_EDGE":
        action = "PASS_OR_WATCH"
        confidence = "medium"
    elif midprice_action == "MIDPRICE_SPLIT_RACE":
        action = "CASH_RUN" if frame_gate_probability >= 0.62 else "WATCHLIST_SHADOW"
        confidence = "medium" if action == "CASH_RUN" else "low"
    elif warnings and not reasons:
        action = "PASS_OR_WATCH"
        confidence = "medium"
    elif frame_gate_probability >= 0.62 and (win_gate_probability < 0.48 or not passport_supports_win):
        action = "CASH_RUN"
        confidence = "medium"
        if win_gate_probability >= 0.58 and not passport_supports_win:
            reasons.append("WIN_GATE_HIGH_BUT_PASSPORT_NOT_SUPPORTIVE")
        reasons.append("FRAME_GATE_HIGH_WIN_GATE_NOT_HIGH")
    elif win_gate_probability >= 0.58 and reasons:
        action = "WIN_CANDIDATE_SHADOW"
        confidence = "medium"
        reasons.append("WIN_GATE_HIGH_EDGE_REGIME")
    elif reasons:
        action = "WATCHLIST_SHADOW"
        confidence = "low"
    else:
        action = "NO_BET_SHADOW"
        confidence = "low"

    return {
        "action": action,
        "confidence": confidence,
        "odds_band": ob,
        "vp_band": vb,
        "field_band": fb,
        "class_band": cb,
        "reasons": reasons,
        "warnings": warnings,
        "midprice_shadow_action": midprice_action or None,
        "midprice_shadow_evidence": midprice_shadow_evidence or None,
    }
