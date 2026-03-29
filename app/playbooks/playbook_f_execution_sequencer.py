"""
PLAYBOOK F — EXECUTION SEQUENCER

Tactical Decision Engine

How doctrines convert into actual race positioning rules.

Playbook E tells us what the race is.
Playbook F tells us what the Oracle does with that information.

Not betting advice. Tactical positioning logic — the machine's internal decision tree.

FIX (sentient-feedback-loop):
- execution_hierarchy is now used to break ties between triggered directives
  (previously defined but never referenced in _determine_positioning_directive)
- G's doctrine_strengths now downweight directives whose backing doctrines have
  a strength < 0.5 in G's state
- G's structural_drift now boosts directives that match high-drift structures
  (e.g. if off_pace_wins is drifting high, POWER_ANCHOR gets a boost)
- The hardcoded 0.6 threshold in _determine_positioning_directive is replaced
  with G's appetite_state['directive_firing_threshold'] (falls back to 0.6)
"""

import logging
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

# Mapping: execution_hierarchy pillar → PositioningDirective
HIERARCHY_DIRECTIVE_MAP = {
    "power": "POWER_ANCHOR_MODE",
    "manipulation": "FAVOURITE_LIABILITY_MODE",
    "chaos": "CHAOS_CONTAINMENT_MODE",
    "vetp_memory": "VETP_IMPRINT_MODE",
    "narrative": "NARRATIVE_FRACTURE_MODE",
    "market": "HOUSE_REVERSAL_MODE",
}

# Mapping: structural_drift key → directive that benefits from it
DRIFT_DIRECTIVE_BOOST = {
    "off_pace_wins": "POWER_ANCHOR_MODE",
    "late_money_wins": "FAVOURITE_LIABILITY_MODE",
    "front_pace_wins": "POWER_ANCHOR_MODE",
    "chaos_wins": "CHAOS_CONTAINMENT_MODE",
    "narrative_wins": "NARRATIVE_FRACTURE_MODE",
}


class PositioningDirective(StrEnum):
    """The 7 Positioning Directives"""

    FAVOURITE_LIABILITY = "FAVOURITE_LIABILITY_MODE"
    POWER_ANCHOR = "POWER_ANCHOR_MODE"
    MULTI_THREAT_ZONE = "MULTI_THREAT_ZONE_MODE"
    NARRATIVE_FRACTURE = "NARRATIVE_FRACTURE_MODE"
    HOUSE_REVERSAL = "HOUSE_REVERSAL_MODE"
    CHAOS_CONTAINMENT = "CHAOS_CONTAINMENT_MODE"
    VETP_IMPRINT = "VETP_IMPRINT_MODE"


class ExecutionSequencer:
    """
    The Execution Sequencer.

    Converts Attack Doctrines into Positioning Directives.
    The machine's decision brain.

    Reads Playbook G's evolved state on every evaluation:
    - directive_firing_threshold (replaces hardcoded 0.6)
    - doctrine_strengths (downweights directives backed by weak doctrines)
    - structural_drift (boosts directives aligned with current drift)
    - execution_hierarchy (used to break ties between triggered directives)
    """

    def __init__(self, sentient_state: dict[str, Any] | None = None):
        self.directive_rules = self._initialize_directive_rules()
        self.execution_hierarchy = [
            "power",  # Power Anchor beats all
            "manipulation",  # Rigged structure voids engine edge
            "chaos",  # Chaos collapses all logic
            "vetp_memory",  # Memory overrides arrogance
            "narrative",  # Narrative structure
            "market",  # Market behaviour
        ]
        self._sentient_state = sentient_state  # Injected from Playbook G via orchestrator

    def update_sentient_state(self, state: dict[str, Any]) -> None:
        """Receive updated state from Playbook G before each race evaluation."""
        self._sentient_state = state

    def _get_directive_threshold(self) -> float:
        """
        Return the directive firing threshold.

        Reads G's appetite_state['directive_firing_threshold'] if available.
        Falls back to 0.6 if G has not yet evolved.
        """
        if self._sentient_state:
            threshold = self._sentient_state.get("appetite_state", {}).get("directive_firing_threshold")
            if threshold is not None:
                logger.debug("[F] Using G's dynamic directive threshold: %.3f", threshold)
                return float(threshold)
        return 0.6

    def _get_doctrine_strength(self, doctrine_name: str) -> float:
        """
        Return G's learned strength for a given doctrine name.
        Returns 1.0 (neutral) if G has no data yet.
        """
        if not self._sentient_state:
            return 1.0
        strengths = self._sentient_state.get("doctrine_strengths", {})
        return float(strengths.get(doctrine_name, 1.0))

    def _get_structural_drift_boost(self, directive_value: str) -> float:
        """
        Return a boost multiplier for a directive based on G's structural drift.

        If a drift pattern is strong (weight > 0.6) and maps to this directive,
        apply a 1.2x boost to its score.
        """
        if not self._sentient_state:
            return 1.0
        drift = self._sentient_state.get("structural_drift", {})
        for drift_key, mapped_directive in DRIFT_DIRECTIVE_BOOST.items():
            if mapped_directive == directive_value:
                weight = drift.get(drift_key, 0.0)
                if weight > 0.6:
                    logger.debug(
                        "[F] Structural drift boost: %s → %s (weight=%.2f)", drift_key, directive_value, weight
                    )
                    return 1.2
        return 1.0

    def _initialize_directive_rules(self) -> dict[PositioningDirective, dict[str, Any]]:
        """Initialize rules for each positioning directive"""
        return {
            PositioningDirective.FAVOURITE_LIABILITY: {
                "triggers": {
                    "story_power_mismatch": lambda oracle: oracle.get("story_anchor") != oracle.get("power_anchor"),
                    "high_mpi": lambda oracle: oracle.get("mpi", 0) > 65,
                    "vetp_trap_match": lambda oracle: any(
                        "mesaafi" in str(p).lower() or "trap" in str(p).lower() for p in oracle.get("vetp_patterns", [])
                    ),
                },
                "effect": {
                    "favourite_confidence_multiplier": 0.15,
                    "power_cluster_boost": 1.5,
                    "description": "Oracle downgrades favourite confidence by -40 to -85%. Power cluster boosted.",
                },
                "hierarchy_pillar": "manipulation",
            },
            PositioningDirective.POWER_ANCHOR: {
                "triggers": {
                    "stable_engine_superiority": lambda oracle: oracle.get("engine_superiority") == "dominant",
                    "low_chaos": lambda oracle: oracle.get("chaos_bloom", 100) < 35,
                    "adequate_integrity": lambda oracle: oracle.get("integrity_score", 0) > 50,
                },
                "effect": {
                    "engine_horse_lock": True,
                    "others_downweighted": 0.5,
                    "description": "Oracle locks target on the engine horse. All other horses downweighted.",
                },
                "hierarchy_pillar": "power",
            },
            PositioningDirective.MULTI_THREAT_ZONE: {
                "triggers": {
                    "large_threat_cluster": lambda oracle: len(oracle.get("threat_cluster", [])) > 3,
                    "moderate_integrity": lambda oracle: oracle.get("integrity_score", 100) < 65,
                    "controlled_chaos": lambda oracle: oracle.get("chaos_bloom", 100) < 40,
                },
                "effect": {
                    "focus_mode": "group",
                    "individual_confidence_reduction": 0.7,
                    "description": "Oracle widens focus to group instead of individual.",
                },
                "hierarchy_pillar": "market",
            },
            PositioningDirective.NARRATIVE_FRACTURE: {
                "triggers": {
                    "extreme_narrative_disruption": lambda oracle: oracle.get("narrative_disruption", 0) > 80,
                    "media_reality_gap": lambda oracle: oracle.get("media_sync", 0) > 0.75,
                },
                "effect": {
                    "suppress_narrative_favourites": True,
                    "mid_range_power_boost": 1.8,
                    "description": "Oracle suppresses all favourites with narrative inflation. Mid-range power gets heavy promotion.",
                },
                "hierarchy_pillar": "narrative",
            },
            PositioningDirective.HOUSE_REVERSAL: {
                "triggers": {
                    "excessive_bookmaker_pressure": lambda oracle: oracle.get("bookmaker_comfort_fav") == "high",
                    "price_power_divergence": lambda oracle: oracle.get("price_power_divergence", 0) > 18,
                },
                "effect": {
                    "bookmaker_comfort_inversion": True,
                    "comfort_zone_penalty": 0.6,
                    "description": "Oracle treats bookmaker comfort zone as a danger zone.",
                },
                "hierarchy_pillar": "market",
            },
            PositioningDirective.CHAOS_CONTAINMENT: {
                "triggers": {
                    "high_chaos": lambda oracle: oracle.get("chaos_bloom", 0) > 60,
                    "low_integrity": lambda oracle: oracle.get("integrity_score", 100) < 30,
                    "no_stable_engine": lambda oracle: oracle.get("engine_superiority") != "dominant",
                },
                "effect": {
                    "structure_collapse_flag": True,
                    "actionable": False,
                    "description": "Oracle outputs 'structure collapse' flag. Race marked informational, not actionable.",
                },
                "hierarchy_pillar": "chaos",
            },
            PositioningDirective.VETP_IMPRINT: {
                "triggers": {
                    "high_pattern_match": lambda oracle: (
                        max([p.get("score", 0) for p in oracle.get("vetp_patterns", [{}])], default=0) > 65
                    )
                },
                "effect": {
                    "memory_penalties_active": True,
                    "behavioural_classification_adjusted": True,
                    "description": "Oracle enforces memory penalties or bonuses. Adjusts behavioural classification.",
                },
                "hierarchy_pillar": "vetp_memory",
            },
        }

    def execute_sequence(self, oracle_data: dict[str, Any], doctrines: list[str]) -> dict[str, Any]:
        """
        Execute the full decision sequence.

        STEP 1: Identify anchors
        STEP 2: Quantify structural integrity (reads from oracle_data)
        STEP 3: Compute manipulation vectors (reads from oracle_data)
        STEP 4: Evaluate historical resonance / VETP (reads from oracle_data)
        STEP 5: Doctrine triggering (provided by Playbook E)
        STEP 6: Convert doctrines → Positioning Directive (uses G's state)
        STEP 7: Generate Oracle sentence (reads from oracle_data)
        STEP 8: Build dual-layer report

        Args:
            oracle_data: Complete Oracle intelligence
            doctrines: List of triggered doctrines from Playbook E

        Returns:
            Execution output with positioning directive
        """
        # STEP 1: Identify anchors
        anchors = self._identify_anchors(oracle_data)

        # STEPS 2-4: Values are in oracle_data (structural_integrity, mpi, vetp_patterns)
        # These are computed upstream by the Oracle/SQPE layer and passed in.

        # STEP 5: Doctrines already provided by Playbook E

        # STEP 6: Convert doctrines to positioning directive (G-aware)
        directive = self._determine_positioning_directive(oracle_data, doctrines)

        # STEP 7: Oracle sentence already in oracle_data

        # STEP 8: Build execution output
        return self._build_execution_output(oracle_data, anchors, doctrines, directive)

    def _identify_anchors(self, oracle_data: dict[str, Any]) -> dict[str, Any]:
        """Identify power, story, chaos, and VETP anchors"""
        return {
            "power": oracle_data.get("power_anchor", "Unknown"),
            "story": oracle_data.get("story_anchor", "Favourite"),
            "chaos": "High" if oracle_data.get("chaos_bloom", 0) > 60 else "Low",
            "vetp_match": self._get_top_vetp_match(oracle_data),
        }

    def _get_top_vetp_match(self, oracle_data: dict[str, Any]) -> str:
        """Get the top VETP pattern match"""
        vetp_patterns = oracle_data.get("vetp_patterns", [])
        if not vetp_patterns:
            return "None"
        top_pattern = max(vetp_patterns, key=lambda x: x.get("score", 0), default={})
        if top_pattern:
            return f"{top_pattern.get('pattern', 'Unknown')} ({top_pattern.get('score', 0)}%)"
        return "None"

    def _determine_positioning_directive(
        self, oracle_data: dict[str, Any], doctrines: list[str]
    ) -> PositioningDirective:
        """
        Determine the primary positioning directive.

        Uses doctrine combinations, Oracle data, and G's evolved state to select
        the best directive. Ties are broken using execution_hierarchy (now active).

        G's doctrine_strengths downweight directives backed by weak doctrines.
        G's structural_drift boosts directives aligned with current drift.
        G's directive_firing_threshold replaces the hardcoded 0.6.
        """
        threshold = self._get_directive_threshold()
        triggered_directives: list[tuple[PositioningDirective, float]] = []

        for directive, rules in self.directive_rules.items():
            satisfied = sum(
                1 for trigger in rules["triggers"].values() if self._safe_trigger_check(trigger, oracle_data)
            )
            total = len(rules["triggers"])
            base_score = satisfied / total if total > 0 else 0.0

            if base_score >= threshold:
                # Apply G's structural drift boost
                drift_boost = self._get_structural_drift_boost(directive.value)
                # Apply G's doctrine strength penalty for backing doctrines
                # (if any doctrine that maps to this directive has low strength, penalise)
                strength_factor = 1.0
                for doc in doctrines:
                    doc_strength = self._get_doctrine_strength(doc)
                    if doc_strength < 0.5:
                        strength_factor = min(strength_factor, doc_strength + 0.5)

                final_score = base_score * drift_boost * strength_factor
                triggered_directives.append((directive, final_score))

        if triggered_directives:
            # Use execution_hierarchy to break ties: higher hierarchy rank wins
            hierarchy_order = {v: i for i, v in enumerate(self.execution_hierarchy)}

            def sort_key(item: tuple[PositioningDirective, float]):
                directive, score = item
                pillar = self.directive_rules[directive].get("hierarchy_pillar", "market")
                rank = hierarchy_order.get(pillar, len(self.execution_hierarchy))
                # Primary: higher score; secondary: lower hierarchy rank (higher priority)
                return (score, -rank)

            triggered_directives.sort(key=sort_key, reverse=True)
            logger.debug(
                "[F] Triggered directives (sorted): %s", [(d.value, round(s, 3)) for d, s in triggered_directives]
            )
            return triggered_directives[0][0]

        # Fallback: determine from doctrine names
        if "LAY_THE_STORY" in doctrines and "PRESSURE_COLLAPSE" in doctrines:
            return PositioningDirective.FAVOURITE_LIABILITY
        elif "ENGINE_SUPREMACY" in doctrines:
            return PositioningDirective.POWER_ANCHOR
        elif "SARCOPHAGUS" in doctrines or "CHAOS_BLEED" in doctrines:
            return PositioningDirective.CHAOS_CONTAINMENT
        elif "VETP_ECHO" in doctrines:
            return PositioningDirective.VETP_IMPRINT
        elif "NARRATIVE_FRACTURE" in doctrines:
            return PositioningDirective.NARRATIVE_FRACTURE
        elif "TOP_4_ON_DANGER" in doctrines:
            return PositioningDirective.MULTI_THREAT_ZONE
        else:
            return PositioningDirective.POWER_ANCHOR  # Default

    def _safe_trigger_check(self, trigger_func, oracle_data: dict[str, Any]) -> bool:
        """Safely check a trigger function"""
        try:
            return trigger_func(oracle_data)
        except Exception:
            return False

    def _build_execution_output(
        self,
        oracle_data: dict[str, Any],
        anchors: dict[str, Any],
        doctrines: list[str],
        directive: PositioningDirective,
    ) -> dict[str, Any]:
        """Build the complete execution output"""
        effect = self.directive_rules[directive]["effect"]

        confidence_vector = {
            "engine": oracle_data.get("engine_confidence", 0.5),
            "chaos": 1.0 - (oracle_data.get("chaos_bloom", 50) / 100.0),
            "manipulation": oracle_data.get("mpi", 50) / 100.0,
            "narrative": oracle_data.get("narrative_disruption", 50) / 100.0,
            "vetp_bias": max([p.get("score", 0) for p in oracle_data.get("vetp_patterns", [{}])], default=0) / 100.0,
        }

        return {
            "anchors": anchors,
            "doctrines_fired": doctrines,
            "positioning_directive": directive.value,
            "directive_effect": effect,
            "confidence_vector": confidence_vector,
            "oracle_sentence": oracle_data.get("oracle_sentence", ""),
            "actionable": effect.get("actionable", True),
            "threshold_used": self._get_directive_threshold(),  # Audit trail
            "hierarchy_applied": True,
        }


def create_execution_sequencer(sentient_state: dict[str, Any] | None = None) -> "ExecutionSequencer":
    """Factory function to create Execution Sequencer"""
    return ExecutionSequencer(sentient_state=sentient_state)
