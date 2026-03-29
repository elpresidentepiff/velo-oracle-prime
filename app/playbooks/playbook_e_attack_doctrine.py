"""
PLAYBOOK E — ATTACK DOCTRINE ENGINE

Race Intelligence → Tactical Positioning Conversion

This is where VÉLØ stops being a "prediction system" and becomes a strategic operator.

Not bets. Not tips. Not staking.
Just positioning doctrines based on race structure, manipulation probability,
chaos forecasting, and behavioural imbalance.

The 12 Tactical Modes.

FIX (sentient-feedback-loop): Replaced hardcoded 0.6 threshold with dynamic read
from Playbook G's appetite_state['doctrine_firing_threshold']. Added emotion law
penalties from G's pain_rules and anger_rules. Added oracle_data schema validation.
"""

import logging
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

# Required oracle_data keys for doctrine evaluation — missing keys are logged as warnings
ORACLE_SCHEMA_KEYS = ["narrative_disruption", "mpi", "chaos_bloom", "integrity_score", "power_anchor", "story_anchor"]


class TacticalMode(StrEnum):
    """The 12 Tactical Modes"""

    # Primary Doctrines (House-Warfare Responses)
    LAY_THE_STORY = "LAY_THE_STORY"
    SHADOW_TRACKING = "SHADOW_TRACKING"
    ENGINE_SUPREMACY = "ENGINE_SUPREMACY"
    TOP_4_ON_DANGER = "TOP_4_ON_DANGER"
    HOUSE_REVERSAL = "HOUSE_REVERSAL"
    SARCOPHAGUS = "SARCOPHAGUS"

    # Secondary Doctrines (Behavioural Targeting)
    PRESSURE_COLLAPSE = "PRESSURE_COLLAPSE"
    OVERLAY_ABSORPTION = "OVERLAY_ABSORPTION"
    CHAOS_BLEED = "CHAOS_BLEED"
    DRAW_SKEW = "DRAW_SKEW"
    GATEKEEPER = "GATEKEEPER"
    VETP_ECHO = "VETP_ECHO"


class AttackDoctrineEngine:
    """
    The Attack Doctrine Engine.

    Converts Oracle intelligence into tactical positioning modes.

    Reads Playbook G's evolved state on every evaluation:
    - doctrine_firing_threshold (replaces hardcoded 0.6)
    - emotion_laws (pain/anger rules suppress trigger weights for flagged structures)
    """

    def __init__(self, sentient_state: dict[str, Any] | None = None):
        self.doctrine_rules = self._initialize_doctrine_rules()
        self._sentient_state = sentient_state  # Injected from Playbook G via orchestrator

    def update_sentient_state(self, state: dict[str, Any]) -> None:
        """Receive updated state from Playbook G before each race evaluation."""
        self._sentient_state = state

    def _get_doctrine_threshold(self) -> float:
        """
        Return the doctrine firing threshold.

        Reads G's appetite_state['doctrine_firing_threshold'] if available.
        Falls back to 0.6 if G has not yet evolved or state is unavailable.
        """
        if self._sentient_state:
            threshold = self._sentient_state.get("appetite_state", {}).get("doctrine_firing_threshold")
            if threshold is not None:
                logger.debug("[E] Using G's dynamic threshold: %.3f", threshold)
                return float(threshold)
        return 0.6  # Default — G has not yet evolved

    def _get_emotion_law_penalties(self) -> dict[str, float]:
        """
        Build a dict of oracle_data key → penalty multiplier from G's emotion laws.

        Pain rules: 50% suppression on matching trigger keys.
        Anger rules: 40% suppression on matching trigger keys.

        A key can accumulate multiple penalties (multiplicative).
        """
        penalties: dict[str, float] = {}
        if not self._sentient_state:
            return penalties
        emotion_laws = self._sentient_state.get("emotion_laws", {})
        for rule in emotion_laws.get("pain_rules", []):
            key = rule.get("key")
            if key:
                penalties[key] = penalties.get(key, 1.0) * 0.5
        for rule in emotion_laws.get("anger_rules", []):
            key = rule.get("key")
            if key:
                penalties[key] = penalties.get(key, 1.0) * 0.6
        return penalties

    def validate_oracle_schema(self, oracle_data: dict[str, Any]) -> list[str]:
        """Return list of missing required keys in oracle_data."""
        return [k for k in ORACLE_SCHEMA_KEYS if k not in oracle_data]

    def _initialize_doctrine_rules(self) -> dict[TacticalMode, dict[str, Any]]:
        """Initialize the rules for each tactical mode"""
        return {
            # ========== PRIMARY DOCTRINES ==========
            TacticalMode.LAY_THE_STORY: {
                "triggers": {
                    "narrative_disruption": lambda x: x > 70,
                    "mpi": lambda x: x > 60,
                    "story_anchor": lambda x: x == "Favourite",
                    "power_anchor": lambda x: x != "Favourite",
                },
                "meaning": "Favourite propped up by storylines, not power. Oppose the narrative. Follow the power.",
                "position": "Oppose narrative. Follow power.",
            },
            TacticalMode.SHADOW_TRACKING: {
                "triggers": {
                    "threat_cluster_has_shadow": lambda x: "shadow" in str(x).lower() or "hidden" in str(x).lower(),
                    "energy_behaviour": lambda x: "rising late" in str(x).lower() or "late-phase" in str(x).lower(),
                    "house_comfort_longshots": lambda x: x == "high",
                },
                "meaning": "Real danger isn't second favourite—it's the horse no one's watching but the numbers whisper.",
                "position": "Track shadow improver trajectory for structure confirmation.",
            },
            TacticalMode.ENGINE_SUPREMACY: {
                "triggers": {
                    "engine_superiority": lambda x: x == "unambiguous" or x == "dominant",
                    "chaos_bloom": lambda x: x < 30,
                    "pace_shaping": lambda x: "predictable" in str(x).lower() or "controlled" in str(x).lower(),
                },
                "meaning": "Controlled environment. Dominant engine. You don't fight physics.",
                "position": "Lock on dominant engine. All others downweighted.",
            },
            TacticalMode.TOP_4_ON_DANGER: {
                "triggers": {
                    "integrity_score": lambda x: 40 < x < 70,
                    "mpi": lambda x: x < 50,
                    "chaos_bloom": lambda x: x < 35,
                    "threat_cluster_size": lambda x: x >= 3,
                },
                "meaning": "Structure stable, but winner identity volatile inside cluster. Power lies in the group, not the favourite.",
                "position": "Widen focus to group instead of individual.",
            },
            TacticalMode.HOUSE_REVERSAL: {
                "triggers": {
                    "bookmaker_comfort_fav": lambda x: x == "high",
                    "true_power_location": lambda x: "mid-tier" in str(x).lower() or "mid-price" in str(x).lower(),
                    "price_story_divergence": lambda x: x > 20,
                },
                "meaning": "Market inviting favourite money, not protecting it. House misdirection pattern.",
                "position": "Treat bookmaker comfort zone as danger zone.",
            },
            TacticalMode.SARCOPHAGUS: {
                "triggers": {
                    "chaos_bloom": lambda x: x > 60,
                    "mpi": lambda x: x > 80,
                    "narrative_extreme": lambda x: (
                        "media horse" in str(x).lower() or "unbeaten hype" in str(x).lower() or x is True
                    ),
                },
                "meaning": "Race is radioactive. Best position is information extraction, not outcome exposure.",
                "position": "CONTAINMENT MODE. Informational only, not actionable.",
            },
            # ========== SECONDARY DOCTRINES ==========
            TacticalMode.PRESSURE_COLLAPSE: {
                "triggers": {
                    "favourite_engine": lambda x: "fragile" in str(x).lower(),
                    "pace_pressure": lambda x: "above equilibrium" in str(x).lower() or "high" in str(x).lower(),
                    "stress_curve": lambda x: "mismatch" in str(x).lower(),
                },
                "meaning": "Favourite will crack under heat.",
                "position": "Downgrade favourite. Boost pressure-resistant runners.",
            },
            TacticalMode.OVERLAY_ABSORPTION: {
                "triggers": {
                    "integrity_score": lambda x: 60 <= x <= 80,
                    "strong_engine_match": lambda x: x is True,
                    "threat_cluster_narrow": lambda x: x is True or x <= 2,
                },
                "meaning": "Allow market to overprice one danger. Exploit the inefficiency.",
                "position": "Target overpriced danger horse.",
            },
            TacticalMode.CHAOS_BLEED: {
                "triggers": {
                    "chaos_bloom": lambda x: 40 <= x <= 75,
                    "pace_map": lambda x: "unstable" in str(x).lower(),
                    "volatile_improvers": lambda x: x is True or x > 0,
                },
                "meaning": "Race will bleed out into unpredictable lanes. Structure weakens.",
                "position": "Observational, not predictive. Reduce exposure.",
            },
            TacticalMode.DRAW_SKEW: {
                "triggers": {
                    "clear_lane_bias": lambda x: x is True,
                    "tactical_draw_misalignment": lambda x: x is True,
                    "threat_cluster_in_bias_lane": lambda x: x is True,
                },
                "meaning": "Draw decides the power.",
                "position": "Follow lane bias. Downgrade runners in wrong lane.",
            },
            TacticalMode.GATEKEEPER: {
                "triggers": {
                    "fav_trip_blocked": lambda x: x is True,
                    "front_end_distorters": lambda x: x is True or x > 0,
                },
                "meaning": "Favourite sabotaged by presence of specific opponent.",
                "position": "Identify gatekeeper. Downgrade favourite.",
            },
            TacticalMode.VETP_ECHO: {
                "triggers": {"pattern_match_score": lambda x: x > 65, "behavioural_resemblance": lambda x: x is True},
                "meaning": "When a lived scar becomes a tactical forecast. Your trauma becomes the weapon.",
                "position": "Apply historical memory penalties/bonuses.",
            },
        }

    def evaluate_doctrines(self, oracle_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Evaluate which tactical doctrines should fire based on Oracle intelligence.

        Validates oracle_data schema before evaluation and logs any missing keys.
        Applies G's dynamic threshold and emotion law penalties.

        Args:
            oracle_data: Complete Oracle dossier data

        Returns:
            List of triggered doctrines with metadata
        """
        # Schema validation — log missing keys, do not abort
        missing = self.validate_oracle_schema(oracle_data)
        if missing:
            logger.warning("[E] oracle_data missing keys: %s — some doctrines may not fire", missing)

        emotion_penalties = self._get_emotion_law_penalties()
        triggered_doctrines = []

        for mode, rules in self.doctrine_rules.items():
            if self._check_triggers(oracle_data, rules["triggers"], emotion_penalties):
                triggered_doctrines.append(
                    {"mode": mode.value, "meaning": rules["meaning"], "position": rules["position"]}
                )

        return triggered_doctrines

    def _check_triggers(
        self, oracle_data: dict[str, Any], triggers: dict[str, Any], emotion_penalties: dict[str, float] | None = None
    ) -> bool:
        """
        Check if triggers for a doctrine are satisfied.

        Uses G's dynamic threshold (via _get_doctrine_threshold) instead of
        a hardcoded 0.6. Also applies emotion law penalties from G's pain/anger
        rules to reduce effective satisfaction count for flagged structures.

        Args:
            oracle_data: Oracle intelligence data
            triggers: Dict of trigger conditions
            emotion_penalties: Optional key→multiplier penalties from G's emotion laws

        Returns:
            True if doctrine should fire
        """
        if emotion_penalties is None:
            emotion_penalties = {}

        satisfied_count = 0.0
        total_triggers = len(triggers)

        for key, condition in triggers.items():
            value = self._extract_value(oracle_data, key)
            if value is not None:
                try:
                    if condition(value):
                        # Apply emotion law penalty if this key is flagged by G
                        weight = emotion_penalties.get(key, 1.0)
                        satisfied_count += weight
                except Exception:
                    pass

        threshold = self._get_doctrine_threshold()
        return satisfied_count >= (total_triggers * threshold)

    def _extract_value(self, oracle_data: dict[str, Any], key: str) -> Any:
        """
        Extract value from Oracle data structure.

        Handles nested keys like 'narrative.disruption_score'
        """
        if "." in key:
            parts = key.split(".")
            value = oracle_data
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None
            return value
        else:
            # Try common locations
            if key in oracle_data:
                return oracle_data[key]

            # Check nested structures
            for section in ["narrative", "manipulation", "energy", "chaos", "house", "vetp", "verdict"]:
                if section in oracle_data and isinstance(oracle_data[section], dict):
                    if key in oracle_data[section]:
                        return oracle_data[section][key]

            return None

    def generate_doctrine_output(self, oracle_data: dict[str, Any]) -> dict[str, Any]:
        """
        Generate complete doctrine output for a race.

        Args:
            oracle_data: Complete Oracle dossier

        Returns:
            Doctrine output structure
        """
        triggered = self.evaluate_doctrines(oracle_data)

        return {
            "doctrines_triggered": [d["mode"] for d in triggered],
            "doctrine_details": triggered,
            "threat_cluster": oracle_data.get("verdict", {}).get("primary_threat_cluster", []),
            "power_anchor": self._extract_value(oracle_data, "power_anchor") or "Unknown",
            "story_anchor": self._extract_value(oracle_data, "story_anchor") or "Favourite",
            "oracle_verdict": oracle_data.get("verdict", {}).get("oracle_sentence", ""),
            "threshold_used": self._get_doctrine_threshold(),  # Audit trail
            "emotion_penalties_active": bool(self._get_emotion_law_penalties()),
        }


def create_attack_doctrine_engine(sentient_state: dict[str, Any] | None = None) -> "AttackDoctrineEngine":
    """Factory function to create Attack Doctrine Engine"""
    return AttackDoctrineEngine(sentient_state=sentient_state)
