"""
TIE v3 — Trainer Intent Gate (Rule-Based Prototype)
=====================================================
Phase 1 of the TIE v3 gate architecture described in docs/TIE_V3_DESIGN.md.

Role: policy instrument, NOT a probability scorer.
  - Sits after scoring (velo_prime_prob is already computed)
  - Sits before final tier assignment
  - Can UPGRADE a tier (C→B, D→C) when intent conviction is high
  - Can flag EW eligibility for longshots with intent signals
  - CANNOT lower velo_prime_prob
  - CANNOT enter _WEIGHTS

Intent signals used (all available in v17 live extractor or Racing API form):
  Tier 1 — always available:
    days_since_run      days since last race (from v17 extractor)
    class_delta         class change vs last run, negative = class drop
    runs_since_win      runs since last win (from v17 doctrine features)
    runs_since_place    runs since last place
    trainer_timing_score from v17 doctrine features

  Tier 2 — from SP/market:
    sp_dec              starting price (decimal)
    sp_rank             SP rank in field (1 = fav)
    is_fav              boolean

  Tier 3 — Specialist Signals (added in v3.1):
    headgear_run        1 if first-time headgear today
    wind_surgery_run    1 if first run since wind surgery
    spotlight_score     0.0 to 1.0 (from spotlight_parser)
    handicap_plot_score 0.0 to 1.0 (near winning mark)

Gate fires when >= MIN_SIGNALS intent signals are present (conviction threshold).

Usage:
    from src.intelligence.tie_v3_gate import TIEv3Gate
    gate = TIEv3Gate()
    result = gate.evaluate(runner_features, current_tier, velo_prime_prob)

    if result.fires:
        # apply result.tier_upgrade, result.ew_flag
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ─── Thresholds ───────────────────────────────────────────────────────────────
# How many intent signals must be present for the gate to fire.
# Higher = fewer fires, better precision. Lower = more coverage, lower precision.
MIN_SIGNALS_FOR_UPGRADE = 4    # to upgrade tier (C→B or D→C) — validated: 1.35-1.49x place precision
MIN_SIGNALS_FOR_EW_FLAG = 3    # to enable EW flag on longshots

# Individual signal thresholds
MAX_DAYS_SINCE_RUN = 42       # within 6 weeks = "fit and ready"
MIN_REST_DAYS = 14             # at least 2 weeks rest = deliberate
MAX_CLASS_DELTA = 0            # same class or class drop = prepared
MIN_RUNS_SINCE_WIN_SIGNAL = 6  # >=6 runs since last win = could be a hold
MAX_RUNS_SINCE_WIN_SIGNAL = 15 # within 15 runs = still has form on record
MAX_RUNS_SINCE_PLACE = 4       # placed within last 4 runs = in form
MIN_TRAINER_TIMING = 0.5       # trainer_timing_score >= 0.5 = pattern present
LONGSHOT_SP_THRESHOLD = 8.0    # SP > 8 = qualifies for EW flag path


@dataclass
class TIEv3GateResult:
    """Outcome of evaluating TIE v3 gate on a single runner."""
    fires: bool = False
    signals_found: list[str] = field(default_factory=list)
    signal_count: int = 0
    tier_upgrade: Optional[str] = None   # new tier if upgrade applies, else None
    ew_flag: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "tie_gate_fires": self.fires,
            "tie_gate_signals": self.signals_found,
            "tie_gate_signal_count": self.signal_count,
            "tie_gate_tier_upgrade": self.tier_upgrade,
            "tie_gate_ew_flag": self.ew_flag,
            "tie_gate_reason": self.reason,
        }


class TIEv3Gate:
    """
    Rule-based TIE v3 gate prototype.

    Each rule returns a named signal string when it fires. The gate then
    applies conviction threshold logic to decide what actions to take.

    This is deliberately deterministic and inspectable — no ML, no black box.
    Phase 2 will replace the rules with a learned classifier only if Phase 1
    demonstrates measurable lift in tier upgrade / EW hit rate backtests.
    """

    def evaluate(
        self,
        features: dict,
        current_tier: Optional[str] = None,
        velo_prime_prob: Optional[float] = None,
    ) -> TIEv3GateResult:
        """
        Evaluate TIE v3 gate for a single runner.

        Parameters
        ----------
        features : dict
            Runner feature dict. Expected keys (all optional — missing = no signal):
              days_since_run, class_delta, runs_since_win, runs_since_place,
              trainer_timing_score, sp_dec, sp_rank, is_fav
        current_tier : str or None
            Current verdict tier (A/B/C/D/X). Gate can only upgrade, never downgrade.
        velo_prime_prob : float or None
            Ensemble probability for this runner.

        Returns
        -------
        TIEv3GateResult
        """
        signals = self._collect_signals(features)
        n = len(signals)

        result = TIEv3GateResult(
            signals_found=signals,
            signal_count=n,
        )

        if n == 0:
            result.reason = "no intent signals"
            return result

        # ── Tier upgrade path ─────────────────────────────────────────────────
        if n >= MIN_SIGNALS_FOR_UPGRADE and current_tier in ("C", "D"):
            upgraded = "B" if current_tier == "C" else "C"
            result.fires = True
            result.tier_upgrade = upgraded
            result.reason = (
                f"{n} intent signals → upgrade {current_tier}→{upgraded}"
            )

        # ── EW flag path (longshots only) ─────────────────────────────────────
        sp = features.get("sp_dec") or 0.0
        is_fav = features.get("is_fav", False)
        if (
            n >= MIN_SIGNALS_FOR_EW_FLAG
            and sp > LONGSHOT_SP_THRESHOLD
            and not is_fav
        ):
            result.ew_flag = True
            result.fires = True
            ew_reason = f"EW flag: {n} signals + SP {sp:.1f}"
            result.reason = (result.reason + " | " + ew_reason).lstrip(" | ")

        if result.fires and not result.reason:
            result.reason = f"{n} intent signals (no tier action)"

        if not result.fires:
            result.reason = f"{n} signals (below threshold {MIN_SIGNALS_FOR_UPGRADE})"

        return result

    def _collect_signals(self, features: dict) -> list[str]:
        """Return list of named intent signals present in features."""
        signals = []

        days = features.get("days_since_run")
        if days is not None:
            if MIN_REST_DAYS <= days <= MAX_DAYS_SINCE_RUN:
                signals.append("rested_and_fit")           # 14–42 days = deliberate prep
            elif days > MAX_DAYS_SINCE_RUN:
                pass                                        # too long absent = not a signal

        class_d = features.get("class_delta")
        if class_d is not None and class_d <= MAX_CLASS_DELTA:
            signals.append("class_drop_or_same")           # dropping/same = easier target

        rsw = features.get("runs_since_win")
        if rsw is not None and MIN_RUNS_SINCE_WIN_SIGNAL <= rsw <= MAX_RUNS_SINCE_WIN_SIGNAL:
            signals.append("win_withheld")                  # held off for a while = timed

        rsp = features.get("runs_since_place")
        if rsp is not None and rsp <= MAX_RUNS_SINCE_PLACE:
            signals.append("in_form_placed_recently")       # placed recently = in form

        tts = features.get("trainer_timing_score")
        if tts is not None and tts >= MIN_TRAINER_TIMING:
            signals.append("trainer_timing_pattern")        # trainer has timing habit

        sp = features.get("sp_dec")
        sp_rank = features.get("sp_rank")
        is_fav = features.get("is_fav", False)
        if sp is not None and sp_rank is not None:
            if not is_fav and sp_rank <= 4 and sp > 3.0:
                signals.append("market_mid_range_support")  # not fav but top-4 market = interest

        # ── Tier 3: Specialist Signals ──────────────────────────────────────
        hg = features.get("headgear_run")
        if hg == 1:
            signals.append("first_time_headgear")           # tactical change

        ws = features.get("wind_surgery_run")
        if ws == 1:
            signals.append("first_run_since_wind_surgery")   # physical fix

        spot = features.get("spotlight_score", 0.0)
        if spot >= 0.7:
            signals.append("high_spotlight_conviction")     # expert narrative support

        plot = features.get("handicap_plot_score", 0.0)
        if plot >= 0.9:
            signals.append("handicap_plot_active")          # near winning mark

        return signals

    def evaluate_field(
        self,
        runners: list[dict],
    ) -> list[dict]:
        """
        Evaluate gate for all runners in a race.

        Parameters
        ----------
        runners : list[dict]
            Each dict must have 'features', optionally 'decision_tier' and
            'velo_prime_prob'. Gate output is added to each runner dict.

        Returns
        -------
        list[dict] — same runners with tie_gate_* fields added in-place.
        """
        for runner in runners:
            feats = runner.get("features") or runner  # support flat or nested
            result = self.evaluate(
                features=feats,
                current_tier=runner.get("decision_tier") or runner.get("tier"),
                velo_prime_prob=runner.get("velo_prime_prob"),
            )
            runner.update(result.to_dict())
            if result.tier_upgrade:
                runner["decision_tier"] = result.tier_upgrade
        return runners
