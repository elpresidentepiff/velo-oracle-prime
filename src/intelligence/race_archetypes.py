"""
Race Archetype Classifier
=========================
Layer 3 of the VÉLØ Organism.

Sits after Horse State Brain (Layer 1) and TIE v3 Gate (Layer 2).
Classifies each race into one of 5 archetypes based on horse states,
gate outputs, and race shape.

Each archetype defines:
  - bet style  (win | ew | watch | pass)
  - suppression (is the top pick a trap to fade?)
  - promotion  (extra conviction boost on top pick)
  - trap_flag  (explicit false-favourite warning)

Archetypes
----------
Structure    — strong form, expected outcome, back confidently
Compression  — trainer-backed class drop, each-way value
PrepRelease  — horse deliberately placed to fire, back with conviction
PublicTrap   — false favourite, fade the top pick
Chaos        — field unstable, reduce stakes or pass

Rules are deterministic and inspectable. No ML, no black box.
No archetype alters velo_prime_prob. They add reasoning context and
action guidance above the proven spine.

Usage
-----
    from src.intelligence.race_archetypes import RaceArchetypeClassifier

    clf = RaceArchetypeClassifier()
    archetype = clf.classify(top, preds, tier, separation)
    # archetype.name      == "PrepRelease"
    # archetype.bet_style == "ew"
    # archetype.to_dict() → flat dict for persistence
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ─── Result ───────────────────────────────────────────────────────────────────

@dataclass
class RaceArchetype:
    """Classification for one race."""
    name:        str                      # Structure | Compression | PrepRelease | PublicTrap | Chaos
    label:       str                      # Human-readable description
    confidence:  str                      # high | medium | low
    bet_style:   str                      # win | ew | watch | pass
    suppression: bool                     # True = top pick is a public trap to fade
    promotion:   bool                     # True = extra conviction boost
    trap_flag:   bool                     # True = explicit false-favourite warning
    rationale:   list[str] = field(default_factory=list)  # evidence trail (readable)
    score:       int = 0                  # raw classification score (debugging)

    def to_dict(self) -> dict:
        return {
            "race_archetype":      self.name,
            "archetype_label":     self.label,
            "archetype_confidence": self.confidence,
            "archetype_bet_style": self.bet_style,
            "archetype_suppression": self.suppression,
            "archetype_trap_flag": self.trap_flag,
            "archetype_rationale": self.rationale,
        }

    def telegram_note(self) -> str:
        """Compact one-line annotation for Telegram cards."""
        icon = {
            "Structure":   "S",
            "Compression": "C",
            "PrepRelease": "PR",
            "PublicTrap":  "T",
            "Chaos":       "X",
        }.get(self.name, "?")
        trap_marker = " ⚠ TRAP" if self.trap_flag else ""
        evidence = " | ".join(self.rationale[:2]) if self.rationale else ""
        note = f"[{icon}:{self.confidence[0].upper()}]{trap_marker}"
        if evidence:
            note += f"  {evidence}"
        return note


# ─── Classifier ───────────────────────────────────────────────────────────────

_LABELS = {
    "Structure":   "Structure — form-backed, expected outcome",
    "Compression": "Compression — trainer-backed class drop",
    "PrepRelease": "Prep/Release — horse placed to fire",
    "PublicTrap":  "Public Trap — false favourite warning",
    "Chaos":       "Chaos — field unstable, reduce stakes",
}

_BET_STYLE = {
    "Structure":   "win",
    "Compression": "ew",
    "PrepRelease": "win",
    "PublicTrap":  "pass",
    "Chaos":       "watch",
}

_FLAGS = {
    #                  suppression  promotion  trap_flag
    "Structure":   dict(suppression=False, promotion=True,  trap_flag=False),
    "Compression": dict(suppression=False, promotion=True,  trap_flag=False),
    "PrepRelease": dict(suppression=False, promotion=True,  trap_flag=False),
    "PublicTrap":  dict(suppression=True,  promotion=False, trap_flag=True),
    "Chaos":       dict(suppression=False, promotion=False, trap_flag=False),
}

# Minimum score required before an archetype can win
_THRESHOLDS = {
    "PublicTrap":  3,
    "PrepRelease": 4,
    "Compression": 4,
    "Chaos":       3,
    "Structure":   3,
}

# Priority order for tie-breaking (most actionable first)
_PRIORITY = ["PublicTrap", "PrepRelease", "Compression", "Chaos", "Structure"]

# Maximum theoretical scores (for confidence normalisation)
_MAX_SCORES = {
    "Structure":   8,
    "Compression": 11,
    "PrepRelease": 11,
    "PublicTrap":  10,
    "Chaos":       9,
}

# SP threshold: PrepRelease prefers EW when horse is not short-priced
_PREP_RELEASE_EW_SP_THRESHOLD = 6.0


class RaceArchetypeClassifier:
    """
    Classifies a race into one of 5 archetypes using deterministic scoring rules.

    Each archetype accumulates a score from Boolean feature tests drawn from:
      - horse_state tags (from HorseStateEngine)
      - TIE v3 gate outputs (tie_gate_*)
      - ensemble outputs (velo_prime_prob, place_prob, market_deception_score)
      - race shape (separation between top and second runner)

    The archetype with the highest score above its threshold wins.
    Ties are broken by priority order (PublicTrap > PrepRelease > Compression > Chaos > Structure).
    Structure is the default when nothing else qualifies.
    """

    def classify(
        self,
        top: dict,
        preds: list[dict],
        tier: str,
        separation: float,
    ) -> RaceArchetype:
        """
        Classify one race.

        Parameters
        ----------
        top        : top-ranked runner dict (contains horse_state nested dict,
                     tie_gate_* fields, velo_prime_prob, etc.)
        preds      : all runners sorted by velo_prime_prob desc
        tier       : current tier (A/B/C/D/X) after TIE gate has applied
        separation : probability gap between top and second runner
        """
        hs = top.get("horse_state") or {}

        # ── Horse state tags (safe defaults) ─────────────────────────────────
        readiness   = hs.get("readiness_state",  "cold")
        release     = hs.get("release_state",    "conditioning")
        rest        = hs.get("rest_pattern",     "neutral")
        class_move  = hs.get("class_move_state", "neutral")
        stable_heat = hs.get("stable_heat",      "cold")
        jockey_sig  = hs.get("jockey_signal",    "neutral")
        market_st   = hs.get("market_state",     "ignored")
        race_fit    = hs.get("race_fit_state",   "adequate")
        chaos_exp   = hs.get("chaos_exposure",   "low")

        # ── Ensemble / market fields ──────────────────────────────────────────
        vp_prob   = float(top.get("velo_prime_prob") or 0.0)
        place_p   = float(top.get("place_prob") or 0.0)
        mkt_decep = float(top.get("market_deception_score") or 0.0)
        is_fav    = bool(top.get("is_fav"))
        sp_dec    = float(top.get("sp_dec") or top.get("best_odds_decimal") or 10.0)

        # ── TIE gate outputs ──────────────────────────────────────────────────
        gate_fires = bool(top.get("tie_gate_fires"))
        gate_n     = int(top.get("tie_gate_signal_count") or 0)

        # ── Derived helpers ───────────────────────────────────────────────────
        # Live signal count: number of state tags that are not "default neutral"
        _neutral = {"cold", "neutral", "conditioning", "ignored", "adequate", "rise", "low"}
        live_sigs = sum(
            1 for v in [readiness, release, rest, class_move, stable_heat, jockey_sig, market_st, race_fit]
            if v not in _neutral
        )

        # False-favourite check (mirror of HorseState.is_false_favorite_candidate)
        is_false_fav = (
            market_st == "obvious"
            and readiness in ("cold", "warming")
            and release == "conditioning"
        )

        # ── Score each archetype ──────────────────────────────────────────────

        arch_scores: dict[str, int] = {}
        arch_evidence: dict[str, list[str]] = {}

        # ── PublicTrap ────────────────────────────────────────────────────────
        s, ev = 0, []
        if is_false_fav:
            s += 4; ev.append("false_fav: obvious+cold+conditioning")
        if market_st == "obvious" and not is_false_fav:
            s += 1; ev.append("market_obvious")
        if is_fav and not gate_fires:
            s += 2; ev.append("fav_no_gate_signal")
        if mkt_decep >= 0.25:
            s += 2; ev.append(f"mkt_deception={mkt_decep:.2f}")
        if live_sigs <= 1:
            s += 1; ev.append(f"weak_state({live_sigs}_signals)")
        arch_scores["PublicTrap"] = s
        arch_evidence["PublicTrap"] = ev

        # ── PrepRelease ───────────────────────────────────────────────────────
        s, ev = 0, []
        if release == "release_candidate":
            s += 4; ev.append("release_candidate")
        if readiness == "primed" and rest == "fresh":
            s += 2; ev.append("primed+fresh")
        elif readiness == "primed":
            s += 1; ev.append("primed")
        if stable_heat == "hot":
            s += 2; ev.append("stable_hot")
        elif stable_heat == "warm":
            s += 1; ev.append("stable_warm")
        if market_st == "quietly_backed":
            s += 1; ev.append("quietly_backed")
        if gate_fires:
            s += 1; ev.append(f"gate_fires({gate_n})")
        if class_move in ("drop", "engineered_drop"):
            s += 1; ev.append(f"class_{class_move}")
        arch_scores["PrepRelease"] = s
        arch_evidence["PrepRelease"] = ev

        # ── Compression ───────────────────────────────────────────────────────
        s, ev = 0, []
        if class_move == "engineered_drop":
            s += 3; ev.append("engineered_drop")
        elif class_move == "drop":
            s += 1; ev.append("class_drop")
        if stable_heat == "hot":
            s += 2; ev.append("stable_hot")
        elif stable_heat == "warm":
            s += 1; ev.append("stable_warm")
        if jockey_sig == "strong_positive":
            s += 2; ev.append("jockey_strong_positive")
        elif jockey_sig == "positive":
            s += 1; ev.append("jockey_positive")
        if market_st == "quietly_backed":
            s += 2; ev.append("quietly_backed")
        if release in ("hidden", "release_candidate"):
            s += 1; ev.append(f"release={release}")
        if gate_n >= 2:
            s += 1; ev.append(f"gate_signals={gate_n}")
        arch_scores["Compression"] = s
        arch_evidence["Compression"] = ev

        # ── Structure ─────────────────────────────────────────────────────────
        s, ev = 0, []
        if readiness == "primed":
            s += 2; ev.append("primed")
        elif readiness == "warming":
            s += 1; ev.append("warming")
        if race_fit == "strong":
            s += 2; ev.append("race_fit_strong")
        if vp_prob >= 0.25:
            s += 1; ev.append(f"vp={vp_prob:.3f}")
        if place_p >= 0.30:
            s += 1; ev.append(f"place={place_p:.2f}")
        if separation >= 0.05:
            s += 1; ev.append(f"sep={separation:.3f}")
        if chaos_exp == "low":
            s += 1; ev.append("chaos_low")
        if not is_false_fav and not is_fav:
            s += 1; ev.append("not_obvious_fav")
        arch_scores["Structure"] = s
        arch_evidence["Structure"] = ev

        # ── Chaos ─────────────────────────────────────────────────────────────
        s, ev = 0, []
        if chaos_exp == "high":
            s += 4; ev.append("chaos_high")
        elif chaos_exp == "medium":
            s += 2; ev.append("chaos_medium")
        if separation < 0.03:
            s += 2; ev.append(f"compressed_sep={separation:.3f}")
        if vp_prob < 0.18:
            s += 1; ev.append(f"weak_leader={vp_prob:.3f}")
        if release == "conditioning" and stable_heat == "cold":
            s += 1; ev.append("no_prep_signal")
        arch_scores["Chaos"] = s
        arch_evidence["Chaos"] = ev

        # ── Select winner ─────────────────────────────────────────────────────
        winner = "Structure"
        winner_score = 0
        for arch in _PRIORITY:
            s = arch_scores[arch]
            if s >= _THRESHOLDS[arch] and s > winner_score:
                winner = arch
                winner_score = s

        winner_ev = arch_evidence[winner]

        # ── Confidence from score ratio ───────────────────────────────────────
        ratio = winner_score / _MAX_SCORES.get(winner, 8)
        confidence = "high" if ratio >= 0.55 else ("medium" if ratio >= 0.35 else "low")

        # ── Bet style override: PrepRelease EW when price is available ────────
        bet_style = _BET_STYLE[winner]
        if winner == "PrepRelease" and sp_dec > _PREP_RELEASE_EW_SP_THRESHOLD:
            bet_style = "ew"

        flags = _FLAGS[winner]

        return RaceArchetype(
            name=winner,
            label=_LABELS[winner],
            confidence=confidence,
            bet_style=bet_style,
            suppression=flags["suppression"],
            promotion=flags["promotion"],
            trap_flag=flags["trap_flag"],
            rationale=winner_ev,
            score=winner_score,
        )
