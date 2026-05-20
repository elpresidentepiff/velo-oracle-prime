"""
VÉLØ Signal Stack — Issue #84.

Builds a first-class structured signal payload for display, persistence, and
Telegram output. Does not modify scoring, routing, or execution.

Usage:
    from src.velo.signal_stack import build_signal_stack_payload

    top["signal_stack"] = build_signal_stack_payload(
        race=race, top=top, tier=tier, sec_prob=sec_prob,
        racecard_source=racecard_source, route_data=route_data,
    )

Hard constraints (permanent — never override):
    No scoring changes.  No routing changes.  No execution changes.
"""

from __future__ import annotations

from typing import Any


def _sf(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def effective_confidence(vp: float) -> str:
    """
    Post-normalization confidence label — canonical display truth.
    Thresholds must stay in sync with run_prime_today.effective_confidence().

    VP >= 0.45 → "high"
    VP >= 0.15 → "normal"
    else       → "low"
    """
    if vp >= 0.45:
        return "high"
    if vp >= 0.15:
        return "normal"
    return "low"


def build_execution_blockers(
    top: dict[str, Any],
    route_data: dict[str, Any] | None,
    racecard_source: str = "",
) -> list[str]:
    """
    Derive human-readable execution blockers from routing context.

    Returns an empty list when execution_allowed is True.
    Translates generic UNAUTHORISED_SELECTION into specific operator-readable
    reasons so the operator understands exactly why execution was blocked.
    Does not change routing or execution — display-layer derivation only.
    """
    if top.get("execution_allowed"):
        return []

    route_data = route_data or {}
    router_reasons: list[str] = list(top.get("router_reasons") or [])
    sp = _sf(top.get("sp_dec") or route_data.get("actual_winner_sp"), 0.0)
    prob_gap = _sf(route_data.get("prob_gap"), _sf(top.get("prob_gap"), 0.0))
    conf = str(top.get("confidence_level") or "").lower()
    vp = _sf(top.get("velo_prime_prob"), 0.0)
    eff_conf = effective_confidence(vp)
    source = racecard_source.lower()

    blockers: list[str] = []

    if "UNAUTHORISED_SELECTION" in router_reasons:
        if sp == 0.0:
            blockers.append("SP_MISSING")
        if "rp_merged" in source:
            blockers.append("SOURCE_RP_MERGED")
        if conf == "low" and eff_conf == "high":
            blockers.append("CONFIDENCE_STALE_LOW")
        elif conf == "low" and eff_conf == "normal":
            blockers.append("LOW_DISPLAY_CONFIDENCE")
        if prob_gap < 0.03:
            blockers.append("WEAK_MARGIN")
        blockers.append("ROUTER_FALLBACK")
    else:
        for rr in router_reasons:
            if rr not in blockers:
                blockers.append(rr)

    return blockers


def build_signal_stack_payload(
    race: dict[str, Any],
    top: dict[str, Any],
    tier: str,
    sec_prob: float = 0.0,
    racecard_source: str = "",
    route_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a first-class signal stack payload from a scored top prediction.

    Captures: sidecar scores, badges, risks, confidence fields (stale ensemble
    label and post-normalization effective label), and execution blockers in a
    single dict for persistence and display.

    Does not mutate any field on `top`.

    Return value is suitable for:
        top["signal_stack"]  (persistence, runner snapshots)
        governed-card API response
        dashboard rendering
        Telegram signal panel
    """
    route_data = route_data or {}

    vp = _sf(top.get("velo_prime_prob"), 0.0)
    mds = _sf(top.get("market_deception_score"), 0.0)
    improvement = _sf(top.get("improvement_score"), 0.0)
    place_prob = _sf(top.get("place_prob"), 0.0)
    prob_gap = max(0.0, vp - sec_prob)

    ensemble_confidence = top.get("confidence_level")
    eff_conf = (
        top.get("confidence_level_effective")
        or top.get("confidence_level_display")
        or effective_confidence(vp)
    )

    # ── Badges ────────────────────────────────────────────────────────────────
    badges: list[str] = []
    if vp >= 0.30 and tier == "A":
        badges.append("VP30_TIER_A")
    if mds > 0.50:
        badges.append("MDS_HIGH")
    if improvement > 0.40:
        badges.append("IMPROVE_HIGH")
    if place_prob > 0.80:
        badges.append("PLACE_PROB_HIGH")
    if tier == "B" and vp < 0.30:
        badges.append("B_LOW_VP_SUPPRESS")

    # ── Risks ─────────────────────────────────────────────────────────────────
    risks: list[str] = []
    if 0.20 <= vp < 0.30:
        risks.append("VP_DRAG_ZONE")
    sp = _sf(top.get("sp_dec"), 0.0)
    if sp > 0.0 and 3.0 <= sp <= 8.5:
        risks.append("MID_PRICE_ZONE")
    if sp > 0.0 and sp < 3.0:
        risks.append("SHORT_FAV_ZONE")

    # ── Execution blockers ────────────────────────────────────────────────────
    execution_blockers = build_execution_blockers(top, route_data, racecard_source)

    return {
        "vp": round(vp, 4),
        "tier": tier,
        "ensemble_confidence": ensemble_confidence,
        "effective_confidence": eff_conf,
        "prob_gap": round(prob_gap, 4),
        "mds": round(mds, 4),
        "improvement": round(improvement, 4),
        "place_prob": round(place_prob, 4),
        "badges": badges,
        "risks": risks,
        "assigned_product": top.get("assigned_product"),
        "execution_allowed": bool(top.get("execution_allowed")),
        "router_reasons": list(top.get("router_reasons") or []),
        "execution_blockers": execution_blockers,
        "source": racecard_source,
    }
