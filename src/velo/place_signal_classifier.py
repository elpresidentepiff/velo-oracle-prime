"""
Place Signal Classifier
========================

Classifies each VÉLØ top selection into an operator place signal stack.

RECALIBRATED 2026-09-03. Two of the three thresholds were switched off.

MDS_HIGH sat at 0.50 and market_deception_score has p99.9 = 0.578, so it
fired on 0.20% of runners — 30 times in 14,748. IMPROVE_HIGH sat at 0.40
against a p99 of 0.383 and fired on 0.77%. Every stack gated on them was
therefore built from 13-38 selections, and the evidence recorded here was
correspondingly fictional: ELITE was documented as Frame=100% and E/W 1/4
ROI +170% on n=28. Measured across 248 selections it is Frame 64.1% and a
place-leg ROI of -9.13%.

Thresholds are now set by percentile of the observed live distribution, so
each fires at a stated rate rather than landing in the tail by accident.
VP30 was left effectively where it was: the 91.5th percentile is 0.2979,
which is the clearest sign the method is calibrating firing rate and not
chasing returns.

Evidence base — 14,748 runners, 1,855 races, 2026-05-20..2026-09-02, joined
to actual SP and finishing position, place legs settled at industry terms
(2 places @1/4 for 5-7 runners; 3 @1/5 for 8+ non-handicap; 3 @1/4 for
12-15 handicaps; 4 @1/4 for 16+; no place market under 5 runners):

  stack                     n    frame%   place ROI   win ROI
  ELITE_PLACE_STACK       248     64.1%      -9.13%   -14.18%
  STRONG_PLACE_STACK_PLUS  38     76.3%      +3.31%   -16.79%
  STRONG_PLACE_STACK       84     64.3%     -10.38%   -21.56%
  IMPROVE_PLACE_WATCH      28     57.1%     +24.35%    +2.25%
  BASE_PLACE_TRUST        856     47.0%     -15.90%   -15.64%
  SUPPRESS               4316     25.6%     -18.91%   -24.45%
  baseline (all runners) 14748    28.1%     -18.56%   -27.29%

Read that honestly. The stacks order frame rate correctly and monotonically
— 64% down to 26% — which is real signal. None of them clears zero on the
economics, the two that show positive place ROI are n=38 and n=28, and the
thresholds were calibrated on the same window the table measures. Nothing
here is proven; it is now merely measurable, which it was not before.

Place markets are about nine points cheaper than win markets on this data
(-18.56% against -27.29% backing everything), which is why a place product
is where this signal has any chance at all.

This is operator visibility only.
No staking. No betting instruction. No live execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ── Thresholds ────────────────────────────────────────────────────────────────
# Set by percentile of the observed live distribution (14,748 runners,
# 2026-05-20..09-02) so each fires at a stated rate. The firing rate is the
# calibration target, not the return — see the module docstring.
#
#   market_deception_score  p97.0 -> fires  3.00%  (was 0.50, fired 0.20%)
#   improvement_score       p98.0 -> fires  2.01%  (was 0.40, fired 0.77%)
#   velo_prime_prob         p91.5 -> fires  8.50%  (was 0.30, fired 8.39%)
#
# If a live firing rate drifts far from these, the distribution has moved and
# the thresholds are stale again — which is exactly how they got to 0.20%.

VP30_T         = 0.2979
MDS_HIGH_T     = 0.1693
IMPROVE_HIGH_T = 0.2892
PLACE_HIGH_T   = 0.80

# Expected firing rates, carried so a monitor can assert against them.
EXPECTED_FIRE_RATE = {"VP30": 0.0850, "MDS_HIGH": 0.0300, "IMPROVE_HIGH": 0.0201}
CALIBRATION_WINDOW = "2026-05-20..2026-09-02"
CALIBRATION_ROWS   = 14748


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
            evidence_n=248,
            evidence_frame_rate=0.641,
            evidence_win_sr=0.375,
            evidence_win_roi=-0.1418,
            evidence_ew_1_4_roi=-0.0913,
            badges=badges,
            place_operator_note=(
                "Elite stack. Frame 64.1% over 248 selections against a 28.1% "
                "baseline; place-leg ROI -9.13%. Highest frame rate of any stack, "
                "not a profitable one. Min place odds 1.05."
                + (f" Also qualifies: {', '.join(extras)}." if extras else "")
            ),
        )

    # 2. STRONG_PLACE_STACK_PLUS: VP30 + MDS + IMPROVE
    if vp30 and mds_high and imp_high:
        return PlaceSignal(
            place_stack_label="STRONG_PLACE_STACK_PLUS",
            place_stack_status="LIVE_OPERATOR_PLACE_SIGNAL",
            min_place_odds=1.05,
            evidence_n=38,
            evidence_frame_rate=0.763,
            evidence_win_sr=0.368,
            evidence_win_roi=-0.1679,
            evidence_ew_1_4_roi=0.0331,
            badges=badges,
            place_operator_note=(
                "Triple confluence: VP30 + MDS + IMPROVE. Frame 76.3%, place-leg "
                "ROI +3.31% — on n=38, which is far too few to act on. Min place odds 1.05."
            ),
        )

    # 3. STRONG_PLACE_STACK: VP30 + MDS
    if vp30 and mds_high:
        return PlaceSignal(
            place_stack_label="STRONG_PLACE_STACK",
            place_stack_status="LIVE_OPERATOR_PLACE_SIGNAL",
            min_place_odds=1.05,
            evidence_n=84,
            evidence_frame_rate=0.643,
            evidence_win_sr=0.369,
            evidence_win_roi=-0.2156,
            evidence_ew_1_4_roi=-0.1038,
            badges=badges,
            place_operator_note=(
                "Strong confluence: VP30 + MDS. Frame 64.3% over 84 selections, "
                "place-leg ROI -10.38%. Min place odds 1.05."
            ),
        )

    # 4. IMPROVE_PLACE_WATCH: VP30 + IMPROVE (no MDS)
    if vp30 and imp_high and not mds_high:
        return PlaceSignal(
            place_stack_label="IMPROVE_PLACE_WATCH",
            place_stack_status="LIVE_OPERATOR_PLACE_WATCH",
            min_place_odds=1.20,
            evidence_n=28,
            evidence_frame_rate=0.571,
            evidence_win_sr=0.250,
            evidence_win_roi=+0.0225,
            evidence_ew_1_4_roi=0.2435,
            badges=badges,
            place_operator_note=(
                "Improve stack: VP30 + improvement_score. Frame 57.1%, place-leg "
                "ROI +24.35% on n=28. The largest number in the table and the "
                "smallest sample behind it; treat as unmeasured. Min place odds 1.20."
            ),
        )

    # 5. SUPPRESS: B-tier + VP < 0.30
    if t == "B" and not vp30:
        return PlaceSignal(
            place_stack_label="SUPPRESS",
            place_stack_status="SUPPRESS",
            min_place_odds=None,
            evidence_n=4316,
            evidence_frame_rate=0.256,
            evidence_win_sr=0.087,
            evidence_win_roi=-0.2445,
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
