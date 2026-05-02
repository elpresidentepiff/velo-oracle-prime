"""
VELO_PRIME_prob — Phase D Meta-Ensemble
Combines base SQPE v17 + specialist scores + macro regime context
into a single final production probability.

Per D003 (decisions.md):
  final production probability = meta-ensemble of:
    base SQPE v17, improvement_score, release_day_prob,
    market_deception_score, place_prob, macro_competitiveness_index,
    macro_favourite_compression_index

Per D004: macro context is structural, joined at race level, NOT runner level.
Per D007: all inputs are LIVE-USABLE (pre-race available).
"""
from __future__ import annotations

import re as _re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from src.intelligence.macro_regime.bha_macro_context import MacroContext

# ─── Playbook G — Shadow State Loader ──────────────────────────────────────────
# Loads G's evolved sentient state for shadow-mode adjustment.
# SHADOW MODE: G's state is logged and compared but NOT applied to live scoring.
#
# Controlled by env var VELO_G_SHADOW_MODE (set in Railway / .env):
#   "shadow" (default) → safe, G multiplier computed but never applied to prob
#   "live"             → G multiplier IS applied — requires explicit decision + review
#
# To promote G to live: set VELO_G_SHADOW_MODE=live AND remove the startup
# assertion in app/main.py. Both gates must be cleared intentionally.
import os as _os
_G_SHADOW_MODE: bool = _os.getenv("VELO_G_SHADOW_MODE", "shadow").lower() != "live"
# True = shadow only (safe). False = live impact.

def _load_g_state() -> dict:
    """Load Playbook G's sentient state. Returns empty dict if unavailable."""
    try:
        import json, os
        # State file lives at repo_root/data/sentient_state.json
        # velo_prime_ensemble.py is at src/intelligence/, so repo root is 2 levels up
        repo_root = Path(__file__).resolve().parent.parent.parent
        state_path = repo_root / "data" / "sentient_state.json"
        if state_path.exists():
            with open(state_path) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

# Load once at module import
_G_STATE: dict = _load_g_state()

# ─── G Shadow Multiplier ────────────────────────────────────────────────────────
# G's doctrine_strengths and structural_drift influence scoring multipliers.
# SHADOW LOGGED: when _G_SHADOW_MODE=True, the adjustment is computed and
# logged to verdict_flags but NOT applied to velo_prime_prob.

def _g_shadow_adjustment(
    market_deception_score: Optional[float],
    is_fav: bool,
    sp_dec: Optional[float],
    horse_id: Optional[str],
    doctrine_strengths: dict,
    appetite_state: dict,
    emotion_laws: dict,
) -> tuple[float, list[str], list[str], str]:
    """
    Compute G's shadow adjustment multiplier for a runner.

    Returns (multiplier, flags, doctrine_fired, pain_horse_id) where:
      - multiplier: what velo_prime_prob would be multiplied by (1.0 = no change)
      - flags: list of strings describing what G did (always logged)
      - doctrine_fired: list of doctrine names that fired (for capture)
      - pain_horse_id: horse_id that triggered a pain rule (if any)

    When _G_SHADOW_MODE=True: multiplier is computed but NOT applied.
    When _G_SHADOW_MODE=False: multiplier IS applied (promoted to live).

    G targets:
    - mid_priced_won (35.1% of misses): via FAVOURITE_LIABILITY doctrine
    - market_decoy_followed (26.9% of misses): via LAY_THE_STORY doctrine
    - outsider_won (10.9% of misses): via SHADOW_TRACKING doctrine
    """
    flags = []
    doctrine_fired = []
    pain_horse_id = ""

    multiplier = 1.0

    if not _G_STATE:
        return 1.0, ["g_state:unavailable"], [], ""

    # Effective doctrine_firing_threshold
    raw_threshold = appetite_state.get("doctrine_firing_threshold", 1.0)
    # 1.0 means all triggers required — that's a frozen state. Default to 0.6.
    threshold = raw_threshold if raw_threshold < 1.0 else 0.6
    flags.append(f"g_threshold:{threshold:.2f}")

    # ── Emotion law penalties ─────────────────────────────────────────────────
    # Pain rules: suppress signals when a specific horse_id + high MPI trap occurred.
    if emotion_laws and market_deception_score is not None and horse_id:
        pain_rules = emotion_laws.get("pain_rules", [])
        for rule in pain_rules:
            if not isinstance(rule, dict):
                continue
            # Extract horse_ids from rule text: "Avoid hrs_XXXXX when MPI > 70"
            horse_ids_in_rule = _re.findall(r'(hrs_\w+)', rule.get('rule', ''))
            if horse_id in horse_ids_in_rule:
                # This specific horse was flagged in a pain rule
                if market_deception_score > 0.6:
                    penalty = 0.85
                    multiplier *= penalty
                    pain_horse_id = horse_id
                    flags.append(f"g_pain_rule:{rule.get('pattern','unknown')}:0.85")
                    doctrine_fired.append("PAIN_RULE")

        # Triumph rules (Euphoria): boost signals when a specific horse_id previously delivered engine supremacy.
        triumph_rules = emotion_laws.get("triumph_rules", [])
        for rule in triumph_rules:
            if not isinstance(rule, dict):
                continue
            # Extract horse_ids from rule text: "Trust hrs_XXXXX engine supremacy"
            horse_ids_in_rule = _re.findall(r'(hrs_\w+)', rule.get('rule', ''))
            if horse_id in horse_ids_in_rule:
                # This specific horse delivered a high-confidence win before
                # Boost probability to reflect proven historical trust
                euphoria_boost = 1.15
                multiplier *= euphoria_boost
                flags.append(f"g_triumph_rule:{rule.get('pattern','unknown')}:1.15")
                doctrine_fired.append("TRIUMPH_RULE")

    # ── Doctrine strength discounts ────────────────────────────────────────────
    # If a doctrine has low strength (< 0.5), G has lost on it repeatedly.
    # Apply a discount proportional to how weak it is.
    STRONG_DOCTRINES = ["LAY_THE_STORY", "SHADOW_TRACKING", "NARRATIVE_FRACTURE"]
    for doc in STRONG_DOCTRINES:
        strength = doctrine_strengths.get(doc, 1.0)
        if 0 < strength < 0.5:
            # Progressive discount: strength 0.3 → 0.9x multiplier
            discount = 0.7 + (strength * 0.67)  # 0.3→0.9x, 0.4→0.97x
            multiplier *= discount
            flags.append(f"g_{doc.lower()}_weak:{strength:.2f}x")
            doctrine_fired.append(doc)

    # ── Favourite liability doctrine ───────────────────────────────────────────
    # G's FAVOURITE_LIABILITY fires when story ≠ power.
    # If this horse is the favourite and doctrine strength is healthy,
    # apply a small discount (market over-pricing the story).
    # Only applies to is_fav=True and when market_deception_score > 0.5
    fav_strength = doctrine_strengths.get("LAY_THE_STORY", 1.0)
    if is_fav and market_deception_score is not None and market_deception_score > 0.55:
        if fav_strength >= 0.5:
            # Market is priced as fav but story/power may not match
            discount = 0.93  # small discount to favourite confidence
            multiplier *= discount
            flags.append(f"g_fav_liability:{discount}")
            doctrine_fired.append("FAVOURITE_LIABILITY")

    # ── Shadow vs live ───────────────────────────────────────────────────────
    if _G_SHADOW_MODE:
        flags.append("g_shadow:applied_not_live")
    else:
        flags.append("g_shadow:live_promoted")

    return multiplier, flags, doctrine_fired, pain_horse_id

# ─── Weights ───────────────────────────────────────────────────────────────────
# Tunable. Defaults based on architecture brief.
_WEIGHTS = {
    # ── LIVE components (enter the weighted average) ──────────────────────────
    "sqpe_v17":              0.45,  # base model (strongest single signal per L004)
    "market_deception_score":0.10,
    "place_prob":            0.08,
    "longshot_score":        0.07,  # only applied when sp > 10.0
    # ── STORED FOR OBSERVABILITY — NOT IN ENSEMBLE ────────────────────────────
    # These weights are defined for reference but the components are all listed
    # in _DISABLED_COMPONENTS below and will NEVER enter the weighted average.
    # They are computed and persisted in velo_verdicts for auditing only.
    # See excluded_from_ensemble field on every verdict row for confirmation.
    "improvement_score":     0.12,  # DISABLED — ablation 2026-04-04: hurts top-1 (-0.6 ppts)
    "release_window_score":  0.10,  # DISABLED — RPD features not wired in live pipeline
    "comment_intel_score":   0.08,  # DISABLED — RPD features not wired in live pipeline
}

# ─── Disabled components ────────────────────────────────────────────────────────
# Components listed here are excluded from the ensemble regardless of weight.
# Condition for disabling: required input features are not available in the live
# scoring pipeline, causing the specialist model to return a constant output that
# adds zero ranking signal while distorting probability scaling.
#
# release_window_score — requires RPD timing features (setup_run_flag,
#   cash_run_flag, trainer_timing_score, runs_since_win/place …)
#   NOT wired in _build_live_features(). Attribution audit: std=0.0, unique=1.
#   Persisted in velo_verdicts as release_day_prob for observability — NOT used.
#
# comment_intel_score — requires RPD intent features (quiet_run_score,
#   decoy_support_flag, jockey_switch_intent, setup_run_flag, cash_run_flag …)
#   NOT wired in _build_live_features(). Attribution audit: std=0.0, unique=1.
#   Persisted in full_analysis for observability — NOT used.
#
# Re-enable only when the required feature pipeline is fully wired and
# the field-level zero-variance kill switch (in predict_race) does NOT fire.
_DISABLED_COMPONENTS: set[str] = {
    "release_window_score",
    "comment_intel_score",
    # Ablation backtest (2026-04-04, 647 races): improvement_score hurts top-1
    # (-0.6 ppts vs SQPE+Place) and avgWinP (-0.003). No compensating case.
    # Re-enable only if a retrained model demonstrates lift over SQPE+Place+MktDeception.
    "improvement_score",
}

# ─── Ablation modes ─────────────────────────────────────────────────────────────
# Used for backtesting only. Production always runs FULL_MINUS_DEAD.
# Each mode maps to an additional set of components to exclude on top of
# _DISABLED_COMPONENTS. These are passed as forced_exclude into predict_race().
ABLATION_SQPE_ONLY                     = "SQPE_ONLY"
ABLATION_SQPE_PLUS_PLACE               = "SQPE_PLUS_PLACE"
ABLATION_SQPE_PLUS_PLACE_PLUS_IMPROVE  = "SQPE_PLUS_PLACE_PLUS_IMPROVEMENT"
ABLATION_SQPE_PLUS_PLACE_PLUS_MKT     = "SQPE_PLUS_PLACE_PLUS_MARKET_DECEPTION"
ABLATION_SQPE_PLUS_PLACE_PLUS_LONG    = "SQPE_PLUS_PLACE_PLUS_LONGSHOT"
ABLATION_FULL_MINUS_DEAD               = "FULL_MINUS_DEAD"

_ALL_SPECIALIST_KEYS: set[str] = {
    "improvement_score", "release_window_score", "market_deception_score",
    "place_prob", "comment_intel_score", "longshot_score",
}

# mode → set of components to force-exclude (beyond _DISABLED_COMPONENTS)
_MODE_FORCED_EXCLUDE: dict[str, set[str]] = {
    ABLATION_SQPE_ONLY:                    _ALL_SPECIALIST_KEYS,
    ABLATION_SQPE_PLUS_PLACE:              _ALL_SPECIALIST_KEYS - {"place_prob"},
    ABLATION_SQPE_PLUS_PLACE_PLUS_IMPROVE: _ALL_SPECIALIST_KEYS - {"place_prob", "improvement_score"},
    ABLATION_SQPE_PLUS_PLACE_PLUS_MKT:    _ALL_SPECIALIST_KEYS - {"place_prob", "market_deception_score"},
    ABLATION_SQPE_PLUS_PLACE_PLUS_LONG:   _ALL_SPECIALIST_KEYS - {"place_prob", "longshot_score"},
    ABLATION_FULL_MINUS_DEAD:              set(),
}

# Macro modifiers — these adjust confidence/weight, don't replace probabilities
_MACRO_CHAOS_CONFIDENCE_DAMPER    = 0.80  # reduce model confidence in chaos regime
_MACRO_COMPRESSION_FAV_PENALTY    = 0.05  # subtract from favourite's prob when trap=high
_MACRO_THIN_MARKET_UNCERTAINTY    = 0.10  # spread probability when field_size_regime=tight


@dataclass
class VeloPrimePrediction:
    horse: str
    race_id: str
    sqpe_v17_prob: float
    horse_id: Optional[str] = None  # for horse-specific G emotion law matching

    # Specialist scores (optional — if model not available, excluded from ensemble)
    improvement_score: Optional[float] = None
    release_window_score: Optional[float] = None
    market_deception_score: Optional[float] = None
    place_prob: Optional[float] = None
    comment_intel_score: Optional[float] = None
    longshot_score: Optional[float] = None

    # Market context
    sp_dec: Optional[float] = None
    is_fav: bool = False

    # Macro regime (applied at race level)
    macro_context: Optional[MacroContext] = None

    # Outputs (populated by compute())
    velo_prime_prob: float = 0.0
    confidence_level: str = "normal"  # low / normal / high
    regime_override: Optional[str] = None
    verdict_flags: list = field(default_factory=list)
    # Observability: populated by compute() so callers can audit what actually ran
    active_components: list = field(default_factory=list)
    excluded_from_ensemble: list = field(default_factory=list)
    # Playbook G shadow (populated by compute())
    g_base_prob: float = 0.0  # prob before G adjustment
    g_shadow_multiplier: float = 1.0  # G multiplier applied
    g_shadow_horse_id: str = ""  # horse_id that triggered pain rule (if any)
    doctrines_fired: list = field(default_factory=list)  # list of doctrine names that fired
    g_shadow_flags: list = field(default_factory=list)  # what G did

    # HFS Signal Contract v1 — populated by _compute_hfs_signals() after compute()
    mpi: Optional[float] = None
    chaos_bloom: Optional[float] = None
    mpi_source: Optional[str] = None
    chaos_bloom_source: Optional[str] = None
    mpi_block_reason: Optional[str] = None
    chaos_bloom_block_reason: Optional[str] = None
    signal_contract_version: str = "hfs_signal_contract_v1"

    def compute(self, killed: set[str] | None = None) -> "VeloPrimePrediction":
        """Build VELO_PRIME_prob from all available signals.

        Args:
            killed: additional components to exclude this race (from field-level
                    zero-variance kill switch in predict_race).
        """
        excluded = _DISABLED_COMPONENTS | (killed or set())
        scores = {"sqpe_v17": self.sqpe_v17_prob}
        # Track for observability (populated after scores dict is built below)

        if "improvement_score" not in excluded and self.improvement_score is not None:
            scores["improvement_score"] = self.improvement_score
        if "release_window_score" not in excluded and self.release_window_score is not None:
            scores["release_window_score"] = self.release_window_score
        if "market_deception_score" not in excluded and self.market_deception_score is not None:
            scores["market_deception_score"] = self.market_deception_score
        if "place_prob" not in excluded and self.place_prob is not None:
            scores["place_prob"] = self.place_prob
        if "comment_intel_score" not in excluded and self.comment_intel_score is not None:
            scores["comment_intel_score"] = self.comment_intel_score
        if ("longshot_score" not in excluded
                and self.longshot_score is not None
                and (self.sp_dec or 0) >= 10.0):
            scores["longshot_score"] = self.longshot_score

        # Store observability — what actually contributed vs what was excluded
        self.active_components = sorted(scores.keys())
        self.excluded_from_ensemble = sorted(excluded)

        # Weighted average of available scores
        total_weight = sum(_WEIGHTS[k] for k in scores)
        prob = sum(_WEIGHTS[k] * v for k, v in scores.items()) / total_weight

        # ── Macro adjustments ──────────────────────────────────────────────────
        if self.macro_context is not None:
            ctx = self.macro_context

            # Chaos mode: dampen confidence (flatten towards 1/field_size)
            if ctx.chaos_mode:
                field_size = 8  # default if unknown
                uniform = 1.0 / field_size
                prob = _MACRO_CHAOS_CONFIDENCE_DAMPER * prob + (1 - _MACRO_CHAOS_CONFIDENCE_DAMPER) * uniform
                self.verdict_flags.append("macro:chaos_regime_dampened")
                self.regime_override = "chaos"

            # Favourite trap: if market is heavily compressed AND this is the favourite,
            # apply a small penalty (the market may be over-efficient on hot-pots)
            if ctx.favourite_trap_risk == "high" and self.is_fav:
                prob = max(0.01, prob - _MACRO_COMPRESSION_FAV_PENALTY)
                self.verdict_flags.append("macro:fav_trap_penalty_applied")

            # Thin market: if field size regime is tight, increase uncertainty
            if ctx.field_size_regime == "tight":
                field_size = 8
                uniform = 1.0 / field_size
                prob = (1 - _MACRO_THIN_MARKET_UNCERTAINTY) * prob + _MACRO_THIN_MARKET_UNCERTAINTY * uniform
                self.verdict_flags.append("macro:thin_market_uncertainty")

        # Clip to valid probability range (base probability before G shadow)
        self.velo_prime_prob = max(0.001, min(0.999, prob))

        # ── Playbook G Shadow Adjustment ──────────────────────────────────────────
        # Shadow mode: multiplier is computed but NOT applied to velo_prime_prob.
        # Logged for comparison. When G has evolved (after running close_sigma_loops.py
        # on the full archive), this will show what G would have done.
        doctrine_strengths = _G_STATE.get("doctrine_strengths", {})
        appetite_state = _G_STATE.get("appetite_state", {})
        emotion_laws = _G_STATE.get("emotion_laws", {})

        g_mult, g_flags, g_doctrines, g_pain_horse = _g_shadow_adjustment(
            market_deception_score=self.market_deception_score,
            is_fav=self.is_fav,
            sp_dec=self.sp_dec,
            horse_id=self.horse_id,
            doctrine_strengths=doctrine_strengths,
            appetite_state=appetite_state,
            emotion_laws=emotion_laws,
        )
        self.g_base_prob = self.velo_prime_prob
        self.g_shadow_multiplier = g_mult
        self.g_shadow_flags = g_flags
        self.g_shadow_horse_id = g_pain_horse
        self.doctrines_fired = g_doctrines
        self.verdict_flags.extend(g_flags)

        # Apply G multiplier only when promoted to live (not shadow mode)
        if not _G_SHADOW_MODE:
            self.velo_prime_prob = max(0.001, min(0.999, self.velo_prime_prob * g_mult))

        # Confidence classification (calibration insight from L005: model underconfident at top)
        if self.velo_prime_prob >= 0.50:
            self.confidence_level = "high"
        elif self.velo_prime_prob >= 0.25:
            self.confidence_level = "normal"
        else:
            self.confidence_level = "low"

        # Compute HFS signal contract fields after velo_prime_prob is finalised
        self._compute_hfs_signals()

        return self

    def _compute_hfs_signals(self) -> None:
        """
        Compute mpi and chaos_bloom for the HFS signal contract.
        Called at the end of compute() so velo_prime_prob is already finalised.
        Formula version: hfs_signal_contract_v1

        MPI  = market pressure index (model vs market disagreement), bounded [0,1]
        chaos_bloom = race entropy index (macro context), bounded [0,1]
        """
        # ── MPI ───────────────────────────────────────────────────────────────
        vp = getattr(self, 'velo_prime_prob', None)
        mds = getattr(self, 'market_deception_score', None)
        if vp is not None and mds is not None:
            # MPI = blend of model confidence and market deception signal
            # Higher vp + higher mds = market underpricing a confident pick = high MPI
            raw = (vp * 0.6) + (mds * 0.4)
            self.mpi = round(min(1.0, max(0.0, raw)), 4)
            self.mpi_source = "derived_from_vp_mds"
        elif vp is not None:
            self.mpi = round(min(1.0, max(0.0, vp)), 4)
            self.mpi_source = "derived_from_vp_only"
            self.mpi_block_reason = "mds_missing"
        else:
            self.mpi = None
            self.mpi_block_reason = "velo_prime_prob_missing"

        # ── Chaos bloom ───────────────────────────────────────────────────────
        chaos_mode = None
        trap_risk = None
        if self.macro_context:
            chaos_mode = getattr(self.macro_context, 'chaos_mode', None)
            trap_risk = getattr(self.macro_context, 'favourite_trap_risk', None)

        if chaos_mode is not None or trap_risk is not None:
            base = 0.3
            if chaos_mode:
                base += 0.4
            if trap_risk in ("high", "HIGH", True, 1):
                base += 0.3
            elif trap_risk in ("medium", "MEDIUM"):
                base += 0.15
            self.chaos_bloom = round(min(1.0, max(0.0, base)), 4)
            self.chaos_bloom_source = "derived_from_macro_field_trap"
        else:
            self.chaos_bloom = None
            self.chaos_bloom_block_reason = "macro_context_missing"

    def to_dict(self) -> dict:
        return {
            "horse": self.horse,
            "race_id": self.race_id,
            "sqpe_v17_prob": round(self.sqpe_v17_prob, 4),
            "velo_prime_prob": round(self.velo_prime_prob, 4),
            "improvement_score": self.improvement_score,
            "release_window_score": self.release_window_score,
            "market_deception_score": self.market_deception_score,
            "place_prob": self.place_prob,
            "comment_intel_score": self.comment_intel_score,
            "longshot_score": self.longshot_score,
            "confidence_level": self.confidence_level,
            "regime_override": self.regime_override,
            "verdict_flags": self.verdict_flags,
            "macro_regime": self.macro_context.regime_label if self.macro_context else None,
            "macro_favourite_trap": self.macro_context.favourite_trap_risk if self.macro_context else None,
            "macro_available": self.macro_context.macro_available if self.macro_context else None,
            # Observability: explicit audit trail of what ran vs what was excluded
            "active_components": self.active_components,
            "excluded_from_ensemble": self.excluded_from_ensemble,
            # Playbook G shadow observables
            "g_base_prob": round(self.g_base_prob, 4),
            "g_shadow_multiplier": round(self.g_shadow_multiplier, 4),
            "g_shadow_horse_id": self.g_shadow_horse_id,
            "g_shadow_flags": self.g_shadow_flags,
            "g_shadow_mode": _G_SHADOW_MODE,
            "doctrines_fired": self.doctrines_fired,
            # HFS Signal Contract v1
            "mpi": self.mpi,
            "chaos_bloom": self.chaos_bloom,
            "mpi_source": self.mpi_source,
            "chaos_bloom_source": self.chaos_bloom_source,
            "mpi_block_reason": self.mpi_block_reason,
            "chaos_bloom_block_reason": self.chaos_bloom_block_reason,
            "signal_contract_version": self.signal_contract_version,
        }


class VeloPrimeEnsemble:
    """
    Builds VELO_PRIME_prob for a full race field.

    Usage:
        ensemble = VeloPrimeEnsemble()
        predictions = ensemble.predict_race(race_runners, macro_context)
    """

    def predict_race(
        self,
        runners: list[dict],
        macro_context: Optional[MacroContext] = None,
        mode: str | None = None,
    ) -> list[VeloPrimePrediction]:
        """
        Args:
            runners: list of dicts, each with at minimum:
                     horse, race_id, sqpe_v17_prob
                     Optional: improvement_score, release_window_score,
                               market_deception_score, place_prob,
                               comment_intel_score, longshot_score,
                               sp_dec, is_fav
            macro_context: MacroContext from get_macro_context()
            mode: ablation mode (SQPE_ONLY, SQPE_PLUS_PLACE, FULL_MINUS_DEAD).
                  None = FULL_MINUS_DEAD (production default).
                  Use ABLATION_* constants from this module.

        Returns:
            List of VeloPrimePrediction, sorted by velo_prime_prob desc.
        """
        effective_mode = mode or ABLATION_FULL_MINUS_DEAD
        mode_forced: set[str] = _MODE_FORCED_EXCLUDE.get(effective_mode, set())

        # ── Field-level zero-variance kill switch ──────────────────────────────
        # If all runners in this race have the same value for a component, that
        # component is adding zero ranking signal and distorting normalization.
        # Exclude it for this race and log in verdict_flags.
        # Skip components already excluded by _DISABLED_COMPONENTS or mode_forced.
        _score_keys = {
            "improvement_score":      "improvement_score",
            "release_window_score":   "release_window_score",
            "market_deception_score": "market_deception_score",
            "place_prob":             "place_prob",
            "comment_intel_score":    "comment_intel_score",
            "longshot_score":         "longshot_score",
        }
        already_excluded = _DISABLED_COMPONENTS | mode_forced
        field_killed: set[str] = set()
        for comp_key, runner_key in _score_keys.items():
            if comp_key in already_excluded:
                continue
            vals = [r.get(runner_key) for r in runners if r.get(runner_key) is not None]
            if len(vals) >= 2 and (max(vals) - min(vals)) < 1e-6:
                field_killed.add(comp_key)
                warnings.warn(
                    f"VeloPrimeEnsemble: {comp_key} is constant across field "
                    f"(val={vals[0]:.4f}) — excluded from this race",
                    stacklevel=2,
                )

        all_killed = mode_forced | field_killed

        predictions = []
        for r in runners:
            pred = VeloPrimePrediction(
                horse=r["horse"],
                race_id=r["race_id"],
                sqpe_v17_prob=r["sqpe_v17_prob"],
                horse_id=r.get("horse_id"),
                improvement_score=r.get("improvement_score"),
                release_window_score=r.get("release_window_score"),
                market_deception_score=r.get("market_deception_score"),
                place_prob=r.get("place_prob"),
                comment_intel_score=r.get("comment_intel_score"),
                longshot_score=r.get("longshot_score"),
                sp_dec=r.get("sp_dec"),
                is_fav=bool(r.get("is_fav", False)),
                macro_context=macro_context,
            )
            pred.compute(killed=all_killed)
            # Verdict flags: mode + field-level kills
            pred.verdict_flags.append(f"mode:{effective_mode}")
            if mode_forced - _DISABLED_COMPONENTS:
                pred.verdict_flags.append(
                    f"mode_excluded:{','.join(sorted(mode_forced - _DISABLED_COMPONENTS))}"
                )
            if field_killed:
                pred.verdict_flags.append(f"field_killed:{','.join(sorted(field_killed))}")
            predictions.append(pred)

        # Re-normalise so race probabilities sum to 1.0
        total = sum(p.velo_prime_prob for p in predictions)
        if total > 0:
            for p in predictions:
                p.velo_prime_prob = round(p.velo_prime_prob / total, 4)

        predictions.sort(key=lambda p: p.velo_prime_prob, reverse=True)
        return predictions


# ─── Quick self-test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    from src.intelligence.macro_regime.bha_macro_context import get_macro_context

    test_runners = [
        {"horse": "Alpha", "race_id": "T001", "sqpe_v17_prob": 0.35,
         "improvement_score": 0.60, "release_window_score": 0.70,
         "market_deception_score": 0.55, "place_prob": 0.55,
         "sp_dec": 3.5, "is_fav": True},
        {"horse": "Beta",  "race_id": "T001", "sqpe_v17_prob": 0.25,
         "improvement_score": 0.40, "sp_dec": 6.0, "is_fav": False},
        {"horse": "Gamma", "race_id": "T001", "sqpe_v17_prob": 0.15,
         "longshot_score": 0.55, "sp_dec": 14.0, "is_fav": False},
        {"horse": "Delta", "race_id": "T001", "sqpe_v17_prob": 0.10,
         "sp_dec": 8.0, "is_fav": False},
        {"horse": "Epsilon", "race_id": "T001", "sqpe_v17_prob": 0.08,
         "sp_dec": 20.0, "is_fav": False},
        {"horse": "Zeta",  "race_id": "T001", "sqpe_v17_prob": 0.07,
         "sp_dec": 25.0, "is_fav": False},
    ]

    # Test with normal 2023 flat regime
    ctx = get_macro_context(2023, "flat")
    ensemble = VeloPrimeEnsemble()

    preds = ensemble.predict_race(test_runners, macro_context=ctx)
    print(f"\nRegime: {ctx.regime_label} | fav_trap={ctx.favourite_trap_risk}")
    print(f"{'Horse':<10} {'SQPE':>6} {'VELO_PRIME':>10} {'Conf':>8} {'Flags'}")
    print("-" * 60)
    for p in preds:
        flags = ", ".join(p.verdict_flags) if p.verdict_flags else "-"
        print(f"{p.horse:<10} {p.sqpe_v17_prob:>6.3f} {p.velo_prime_prob:>10.4f} {p.confidence_level:>8} {flags}")

    # Test chaos regime (2020)
    ctx_chaos = get_macro_context(2020, "jump")
    preds_chaos = ensemble.predict_race(test_runners, macro_context=ctx_chaos)
    print(f"\nChaos regime (2020 jump):")
    print(f"{'Horse':<10} {'VELO_PRIME':>10} {'Flags'}")
    for p in preds_chaos:
        flags = ", ".join(p.verdict_flags) if p.verdict_flags else "-"
        print(f"{p.horse:<10} {p.velo_prime_prob:>10.4f} {flags}")
