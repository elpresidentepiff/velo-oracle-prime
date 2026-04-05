"""
Horse State Engine
==================
Computes a compact tagged state object for every runner before final decisioning.

These are NOT probability scores. They are named states that playbooks and gates
reason on. The tagging logic is explicit and auditable — no black box.

State tags computed:
  readiness_state   cold / warming / primed
  release_state     conditioning / hidden / release_candidate
  rest_pattern      neutral / fresh / over_rested / rebound
  class_move_state  rise / neutral / drop / engineered_drop
  stable_heat       cold / warm / hot
  jockey_signal     neutral / positive / strong_positive / negative
  market_state      ignored / drifting / quietly_backed / obvious
  race_fit_state    weak / adequate / strong
  chaos_exposure    low / medium / high

Usage:
    from src.intelligence.horse_state_engine import HorseStateEngine
    engine = HorseStateEngine()
    state = engine.tag(runner_features)
    # state.readiness_state == "primed"
    # state.to_dict() → flat dict for persistence / playbook consumption
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class HorseState:
    """Tagged state for one runner. All fields are named enum-strings."""
    # ── Core prep/readiness ───────────────────────────────────────────────────
    readiness_state:  str = "cold"         # cold / warming / primed
    release_state:    str = "conditioning" # conditioning / hidden / release_candidate
    rest_pattern:     str = "neutral"      # neutral / fresh / over_rested / rebound
    class_move_state: str = "neutral"      # rise / neutral / drop / engineered_drop
    # ── Connections / stable ─────────────────────────────────────────────────
    stable_heat:      str = "cold"         # cold / warm / hot
    jockey_signal:    str = "neutral"      # neutral / positive / strong_positive / negative
    # ── Market ───────────────────────────────────────────────────────────────
    market_state:     str = "ignored"      # ignored / drifting / quietly_backed / obvious
    # ── Structural fit ───────────────────────────────────────────────────────
    race_fit_state:   str = "adequate"     # weak / adequate / strong
    chaos_exposure:   str = "low"          # low / medium / high
    # ── Evidence trail ───────────────────────────────────────────────────────
    evidence: dict = field(default_factory=dict)  # tag → rule that fired it

    def to_dict(self) -> dict:
        d = asdict(self)
        # Flatten evidence into a list of strings for easy persistence
        d["state_evidence"] = [f"{tag}:{rule}" for tag, rule in self.evidence.items()]
        del d["evidence"]
        return d

    @property
    def live_signals(self) -> int:
        """Count of positive / active state signals (not neutral/cold/ignored)."""
        neutral = {"cold", "neutral", "conditioning", "ignored", "adequate", "rise", "low"}
        return sum(
            1 for v in [
                self.readiness_state, self.release_state, self.rest_pattern,
                self.class_move_state, self.stable_heat, self.jockey_signal,
                self.market_state, self.race_fit_state,
            ]
            if v not in neutral
        )

    @property
    def is_live_candidate(self) -> bool:
        """True if enough positive signals to be considered a live/prepared runner."""
        return (
            self.release_state == "release_candidate"
            or (self.readiness_state == "primed" and self.live_signals >= 3)
            or (self.live_signals >= 4)
        )

    @property
    def is_false_favorite_candidate(self) -> bool:
        """True if horse looks prominent but state tags suggest it's a public trap."""
        return (
            self.market_state == "obvious"
            and self.readiness_state in ("cold", "warming")
            and self.release_state == "conditioning"
        )


class HorseStateEngine:
    """
    Tags each runner with a HorseState using explicit deterministic rules.

    All rules are documented inline. The intent is that a human can read any
    tag and understand exactly which feature combination produced it.

    Feature keys expected in runner dict (all optional — missing → safe default):
      From v17 extractor / live feature dict:
        days_since_run, class_delta, runs_since_win, runs_since_place,
        runs_since_mkt_support, trainer_timing_score, jockey_switch_intent,
        quiet_run_score, odds_contraction_score, odds_resilience_score,
        decoy_support_flag, course_fit_score, going_fit_score, distance_fit_score,
        sp_dec, sp_rank, is_fav, field_size, or_num, rpr_num, ts_num
      From specialist models:
        market_deception_score, place_prob, sqpe_v17_prob
    """

    def tag(self, features: dict) -> HorseState:
        state = HorseState()
        ev = {}  # tag → rule description

        # ── Pull features (all with safe defaults) ────────────────────────────
        days          = _f(features, "days_since_run", 14.0)
        class_d       = _f(features, "class_delta", 0.0)
        rsw           = _f(features, "runs_since_win", 99)
        rsp           = _f(features, "runs_since_place", 99)
        rsm           = _f(features, "runs_since_mkt_support", 99)
        trainer_ts    = _f(features, "trainer_timing_score", 0.0)
        jockey_sw     = _f(features, "jockey_switch_intent", 0.0)
        quiet_run     = _f(features, "quiet_run_score", 0.0)
        odds_contract = _f(features, "odds_contraction_score", 0.0)
        odds_resil    = _f(features, "odds_resilience_score", 0.0)
        decoy_flag    = bool(features.get("decoy_support_flag", False))
        course_fit    = _f(features, "course_fit_score", 0.5)
        going_fit     = _f(features, "going_fit_score", 0.5)
        dist_fit      = _f(features, "distance_fit_score", 0.5)
        sp            = _f(features, "sp_dec", 10.0)
        sp_rank       = _f(features, "sp_rank", 5.0)
        is_fav        = bool(features.get("is_fav", False))
        field_size    = _f(features, "field_size", 10.0)
        mkt_decep     = _f(features, "market_deception_score", 0.0)
        place_p       = _f(features, "place_prob", 0.0)
        sqpe_p        = _f(features, "sqpe_v17_prob", 0.0)

        # ── 1. rest_pattern ───────────────────────────────────────────────────
        if 14 <= days <= 28:
            state.rest_pattern = "fresh"
            ev["rest_pattern"] = f"days_since_run={days:.0f} (14-28 = deliberate rest)"
        elif days > 60:
            state.rest_pattern = "over_rested"
            ev["rest_pattern"] = f"days_since_run={days:.0f} (>60 = long absence)"
        elif days < 7:
            state.rest_pattern = "rebound"
            ev["rest_pattern"] = f"days_since_run={days:.0f} (<7 = quick back)"
        # else neutral

        # ── 2. class_move_state ───────────────────────────────────────────────
        if class_d <= -2:
            # Significant class drop — often deliberate
            if trainer_ts >= 0.4 or rsw <= 8:
                state.class_move_state = "engineered_drop"
                ev["class_move_state"] = (
                    f"class_delta={class_d:.0f} (drop) + "
                    f"trainer_timing={trainer_ts:.2f} or rsw={rsw:.0f}"
                )
            else:
                state.class_move_state = "drop"
                ev["class_move_state"] = f"class_delta={class_d:.0f} (simple drop)"
        elif class_d < 0:
            state.class_move_state = "drop"
            ev["class_move_state"] = f"class_delta={class_d:.1f} (slight drop)"
        elif class_d > 1:
            state.class_move_state = "rise"
            ev["class_move_state"] = f"class_delta={class_d:.0f} (class rise)"
        # else neutral

        # ── 3. readiness_state ────────────────────────────────────────────────
        readiness_score = 0
        if state.rest_pattern == "fresh":
            readiness_score += 1
        if rsp <= 3:
            readiness_score += 1
        if place_p >= 0.30:
            readiness_score += 1
        if course_fit >= 0.6 and going_fit >= 0.6:
            readiness_score += 1
        if dist_fit >= 0.6:
            readiness_score += 1

        if readiness_score >= 4:
            state.readiness_state = "primed"
            ev["readiness_state"] = f"score={readiness_score}/5 (primed)"
        elif readiness_score >= 2:
            state.readiness_state = "warming"
            ev["readiness_state"] = f"score={readiness_score}/5 (warming)"
        # else cold

        # ── 4. release_state ──────────────────────────────────────────────────
        # release_candidate: multiple prep signals align
        release_score = 0
        if state.class_move_state in ("drop", "engineered_drop"):
            release_score += 1
        if state.rest_pattern == "fresh":
            release_score += 1
        if rsw >= 5 and rsw <= 15:
            release_score += 1  # win being held off
        if trainer_ts >= 0.5:
            release_score += 1
        if quiet_run >= 0.4:
            release_score += 1  # deliberately running quietly

        if release_score >= 4:
            state.release_state = "release_candidate"
            ev["release_state"] = f"score={release_score}/5 (ready to fire)"
        elif release_score >= 2:
            state.release_state = "hidden"
            ev["release_state"] = f"score={release_score}/5 (being set up)"
        # else conditioning

        # ── 5. stable_heat ────────────────────────────────────────────────────
        heat_score = 0
        if trainer_ts >= 0.5:
            heat_score += 1
        if jockey_sw >= 0.5:
            heat_score += 1
        if rsm <= 3:
            heat_score += 1  # stable has been in the market recently
        if quiet_run >= 0.5:
            heat_score += 1

        if heat_score >= 3:
            state.stable_heat = "hot"
            ev["stable_heat"] = f"score={heat_score}/4 (multiple stable signals)"
        elif heat_score >= 2:
            state.stable_heat = "warm"
            ev["stable_heat"] = f"score={heat_score}/4"
        # else cold

        # ── 6. jockey_signal ──────────────────────────────────────────────────
        if jockey_sw >= 0.7:
            state.jockey_signal = "strong_positive"
            ev["jockey_signal"] = f"jockey_switch_intent={jockey_sw:.2f}"
        elif jockey_sw >= 0.4:
            state.jockey_signal = "positive"
            ev["jockey_signal"] = f"jockey_switch_intent={jockey_sw:.2f}"
        elif jockey_sw < 0:
            state.jockey_signal = "negative"
            ev["jockey_signal"] = f"jockey_switch_intent={jockey_sw:.2f} (downgrade)"
        # else neutral

        # ── 7. market_state ───────────────────────────────────────────────────
        if is_fav and mkt_decep < 0.1:
            state.market_state = "obvious"
            ev["market_state"] = "is_fav with low deception = public trap candidate"
        elif decoy_flag or mkt_decep >= 0.3:
            state.market_state = "drifting"
            ev["market_state"] = f"decoy_flag={decoy_flag} mkt_decep={mkt_decep:.2f}"
        elif odds_contract >= 0.4 and not is_fav:
            state.market_state = "quietly_backed"
            ev["market_state"] = f"odds_contraction={odds_contract:.2f} (not fav)"
        elif odds_resil >= 0.5 and sp_rank <= 4:
            state.market_state = "quietly_backed"
            ev["market_state"] = f"odds_resilience={odds_resil:.2f} sp_rank={sp_rank:.0f}"
        elif is_fav:
            state.market_state = "obvious"
            ev["market_state"] = "market favourite"
        # else ignored

        # ── 8. race_fit_state ─────────────────────────────────────────────────
        fit_score = (course_fit + going_fit + dist_fit) / 3.0
        if fit_score >= 0.65:
            state.race_fit_state = "strong"
            ev["race_fit_state"] = f"avg_fit={fit_score:.2f}"
        elif fit_score <= 0.35:
            state.race_fit_state = "weak"
            ev["race_fit_state"] = f"avg_fit={fit_score:.2f}"
        # else adequate

        # ── 9. chaos_exposure ─────────────────────────────────────────────────
        # High chaos: big field, horse is unconsidered longshot, no fit signal
        if field_size >= 14 and sp_rank >= 8 and fit_score < 0.5:
            state.chaos_exposure = "high"
            ev["chaos_exposure"] = (
                f"field={field_size:.0f} sp_rank={sp_rank:.0f} fit={fit_score:.2f}"
            )
        elif field_size >= 10 and sp_rank >= 6:
            state.chaos_exposure = "medium"
            ev["chaos_exposure"] = f"field={field_size:.0f} sp_rank={sp_rank:.0f}"
        # else low

        state.evidence = ev
        return state

    def tag_field(self, runners: list[dict]) -> list[dict]:
        """
        Tag all runners in a race. Adds state fields to each runner dict in-place.

        Parameters
        ----------
        runners : list[dict]
            Each dict should contain the feature keys expected by tag().
            Can be the flat feature dict or a nested dict with a 'features' key.
        """
        for runner in runners:
            feats = runner.get("features") or runner
            state = self.tag(feats)
            runner.update(state.to_dict())
        return runners


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _f(d: dict, key: str, default: float) -> float:
    """Safe float extraction with default."""
    v = d.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default
