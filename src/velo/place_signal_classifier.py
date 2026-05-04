"""
Place Signal Classifier
========================

Classifies each VÉLØ top selection into an operator place signal stack,
based on the place economics audit (2026-05-01).

Evidence base:
  ELITE_PLACE_STACK    (Tier A + VP30 + MDS):  n=28, Frame=100%, E/W 1/4 ROI +170%
  STRONG_PLACE_STACK   (VP30 + MDS):           n=35, Frame=100%, E/W 1/4 ROI +169%
  STRONG_PLACE_STACK_PLUS (VP30+MDS+IMPROVE):  n=20, Frame=100%, E/W 1/4 ROI +90%
  IMPROVE_PLACE_WATCH  (VP30 + IMPROVE):       n=46, Frame=87%,  E/W 1/4 ROI +51%
  PLACE_SUPPORT_WATCH  (VP30 + PLACE):         n=251,Frame=74.9%,E/W 1/4 ROI +59%
  BASE_PLACE_TRUST     (VP30 only):            n=380,Frame=70%,  E/W 1/4 ROI +52%
  SUPPRESS             (B-tier + VP<0.30):     n=303,Frame=42.9%,never profitable

This is operator visibility only.
No staking. No betting instruction. No live execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ── Thresholds (locked from confluence + place economics audits) ──────────────

VP30_T         = 0.30
MDS_HIGH_T     = 0.50
IMPROVE_HIGH_T = 0.40
PLACE_HIGH_T   = 0.80


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class PlaceSignal:
    # Primary label
    place_stack_label: str          # ELITE_PLACE_STACK etc.
    place_stack_status: str         # LIVE_OPERATOR_PLACE_SIGNAL / WATCH / BASE / SUPPRESS
    min_place_odds: Optional[float] # Minimum exchange/bookmaker place odds for +EV

    # Evidence (from audit)
    evidence_n: int
    evidence_frame_rate: float
    evidence_win_sr: float
    evidence_win_roi: float         # flat win ROI from audit
    evidence_ew_1_4_roi: float      # each-way 1/4 place-leg ROI from audit

    # Flags that fired
    badges: list[str] = field(default_factory=list)

    # Suppress details
    suppress_reason: Optional[str] = None

    # Human note
    place_operator_note: str = ""

    def to_dict(self) -> dict:
        return {
            "place_stack_label":    self.place_stack_label,
            "place_stack_status":   self.place_stack_status,
            "min_place_odds":       self.min_place_odds,
            "evidence_n":           self.evidence_n,
            "evidence_frame_rate":  round(self.evidence_frame_rate, 4),
            "evidence_win_sr":      round(self.evidence_win_sr, 4),
            "evidence_win_roi":     round(self.evidence_win_roi, 4),
            "evidence_ew_1_4_roi":  round(self.evidence_ew_1_4_roi, 4),
            "badges":               self.badges,
            "suppress_reason":      self.suppress_reason,
            "place_operator_note":  self.place_operator_note,
        }


# ── Classifier ────────────────────────────────────────────────────────────────

def classify(
    velo_prime_prob: float,
    tier: str,
    market_deception_score: float,
    improvement_score: float,
    place_prob: float,
    candidate_execution_allowed: Optional[bool] = None,
    router_shadow_lane: Optional[str] = None,
) -> PlaceSignal:
    """
    Classify a single top-selection into an operator place signal stack.

    All inputs should be floats (0.0 if unknown/null).
    tier should be 'A', 'B', 'C', 'D', or 'X'.
    """
    vp  = float(velo_prime_prob or 0)
    mds = float(market_deception_score or 0)
    imp = float(improvement_score or 0)
    pp  = float(place_prob or 0)
    t   = (tier or "").strip().upper()

    vp30       = vp  >= VP30_T
    mds_high   = mds >  MDS_HIGH_T
    imp_high   = imp >  IMPROVE_HIGH_T
    place_high = pp  >  PLACE_HIGH_T

    # Build badge list
    badges: list[str] = []
    if vp30:       badges.append("VP30")
    if mds_high:   badges.append("MDS_HIGH")
    if imp_high:   badges.append("IMP_HIGH")
    if place_high: badges.append("PLACE_HIGH")
    if t == "A":   badges.append("TIER_A")

    # ── Priority classification (most specific first) ─────────────────────────

    # 1. ELITE: Tier A + VP30 + MDS
    if t == "A" and vp30 and mds_high:
        extras = []
        if imp_high:  extras.append("STRONG_PLACE_STACK_PLUS")
        if place_high: extras.append("PLACE_HIGH_CONFIRMED")
        return PlaceSignal(
            place_stack_label="ELITE_PLACE_STACK",
            place_stack_status="LIVE_OPERATOR_PLACE_SIGNAL",
            min_place_odds=1.05,
            evidence_n=28,
            evidence_frame_rate=1.00,
            evidence_win_sr=0.643,
            evidence_win_roi=-0.090,
            evidence_ew_1_4_roi=1.701,
            badges=badges,
            place_operator_note=(
                "Elite stack: every horse placed or won in 28-race sample. "
                "E/W 1/4 place-leg ROI +170%. Min place odds 1.05."
                + (f" Also qualifies: {', '.join(extras)}." if extras else "")
            ),
        )

    # 2. STRONG_PLACE_STACK_PLUS: VP30 + MDS + IMPROVE
    if vp30 and mds_high and imp_high:
        return PlaceSignal(
            place_stack_label="STRONG_PLACE_STACK_PLUS",
            place_stack_status="LIVE_OPERATOR_PLACE_SIGNAL",
            min_place_odds=1.05,
            evidence_n=20,
            evidence_frame_rate=1.00,
            evidence_win_sr=0.550,
            evidence_win_roi=-0.239,
            evidence_ew_1_4_roi=0.901,
            badges=badges,
            place_operator_note=(
                "Triple confluence: VP30 + MDS + IMPROVE. "
                "Frame=100% (n=20). E/W 1/4 place-leg ROI +90%. Min place odds 1.05."
            ),
        )

    # 3. STRONG_PLACE_STACK: VP30 + MDS
    if vp30 and mds_high:
        return PlaceSignal(
            place_stack_label="STRONG_PLACE_STACK",
            place_stack_status="LIVE_OPERATOR_PLACE_SIGNAL",
            min_place_odds=1.05,
            evidence_n=35,
            evidence_frame_rate=1.00,
            evidence_win_sr=0.543,
            evidence_win_roi=-0.238,
            evidence_ew_1_4_roi=1.691,
            badges=badges,
            place_operator_note=(
                "Strong confluence: VP30 + MDS. "
                "Frame=100% (n=35). E/W 1/4 place-leg ROI +169%. Min place odds 1.05."
            ),
        )

    # 4. IMPROVE_PLACE_WATCH: VP30 + IMPROVE (no MDS)
    if vp30 and imp_high and not mds_high:
        return PlaceSignal(
            place_stack_label="IMPROVE_PLACE_WATCH",
            place_stack_status="LIVE_OPERATOR_PLACE_WATCH",
            min_place_odds=1.20,
            evidence_n=46,
            evidence_frame_rate=0.870,
            evidence_win_sr=0.500,
            evidence_win_roi=-0.098,
            evidence_ew_1_4_roi=0.514,
            badges=badges,
            place_operator_note=(
                "Improve stack: VP30 + improvement_score. "
                "Frame=87% (n=46). E/W 1/4 ROI +51%. Min place odds 1.20."
            ),
        )

    # 5. SUPPRESS: B-tier + VP < 0.30
    if t == "B" and not vp30:
        return PlaceSignal(
            place_stack_label="SUPPRESS",
            place_stack_status="SUPPRESS",
            min_place_odds=None,
            evidence_n=303,
            evidence_frame_rate=0.429,
            evidence_win_sr=0.162,
            evidence_win_roi=-0.231,
            evidence_ew_1_4_roi=-0.30,   # approx from audit
            badges=badges,
            suppress_reason="B_TIER_LOW_VP",
            place_operator_note="SUPPRESS — B-tier + VP<0.30. Never profitable at any tested place price. Do not rescue with sidecars.",
        )

    # 6. PLACE_SUPPORT_WATCH: VP30 + PLACE (no MDS, no IMPROVE)
    if vp30 and place_high and not mds_high and not imp_high:
        return PlaceSignal(
            place_stack_label="PLACE_SUPPORT_WATCH",
            place_stack_status="LIVE_OPERATOR_PLACE_WATCH",
            min_place_odds=1.40,
            evidence_n=251,
            evidence_frame_rate=0.749,
            evidence_win_sr=0.363,
            evidence_win_roi=-0.230,
            evidence_ew_1_4_roi=0.586,
            badges=badges,
            place_operator_note=(
                "Place support: VP30 + place_prob high. "
                "Frame=74.9% (n=251). Needs place odds ≥1.40 for +EV."
            ),
        )

    # 7. BASE_PLACE_TRUST: VP30 only
    if vp30:
        return PlaceSignal(
            place_stack_label="BASE_PLACE_TRUST",
            place_stack_status="BASE_PLACE_TRUST",
            min_place_odds=1.50,
            evidence_n=380,
            evidence_frame_rate=0.700,
            evidence_win_sr=0.329,
            evidence_win_roi=-0.177,
            evidence_ew_1_4_roi=0.522,
            badges=badges,
            place_operator_note=(
                "Base trust: VP ≥ 0.30. "
                "Frame=70% (n=380). Needs place odds ≥1.50 for +EV."
            ),
        )

    # 8. Below VP30 — no place signal
    return PlaceSignal(
        place_stack_label="BELOW_VP30",
        place_stack_status="NO_SIGNAL",
        min_place_odds=None,
        evidence_n=0,
        evidence_frame_rate=0.0,
        evidence_win_sr=0.0,
        evidence_win_roi=0.0,
        evidence_ew_1_4_roi=0.0,
        badges=badges,
        place_operator_note="VP < 0.30 — no place signal.",
    )


def classify_from_verdict(verdict: dict) -> PlaceSignal:
    """Classify directly from a velo_verdicts row or flat governed-card dict."""
    return classify(
        velo_prime_prob=float(verdict.get("velo_prime_prob") or 0),
        tier=str(verdict.get("decision_tier") or verdict.get("tier") or ""),
        market_deception_score=float(verdict.get("market_deception_score") or 0),
        improvement_score=float(verdict.get("improvement_score") or 0),
        place_prob=float(verdict.get("place_prob") or 0),
        candidate_execution_allowed=verdict.get("candidate_execution_allowed"),
        router_shadow_lane=verdict.get("router_shadow_lane"),
    )
