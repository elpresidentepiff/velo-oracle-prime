"""
PLAYBOOK E — ATTACK DOCTRINE ENGINE

Race Intelligence → Tactical Positioning Conversion

This is where VÉLØ stops being a "prediction system" and becomes a strategic operator.

Not bets. Not tips. Not staking.
Just positioning doctrines based on race structure, manipulation probability, 
chaos forecasting, and behavioural imbalance.

The 12 Tactical Modes.
"""

from typing import Dict, List, Any
from enum import Enum


class TacticalMode(str, Enum):
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
    """
    
    def __init__(self):
        self.doctrine_rules = self._initialize_doctrine_rules()
    
    def _initialize_doctrine_rules(self) -> Dict[TacticalMode, Dict[str, Any]]:
        """Initialize the rules for each tactical mode"""
        return {
            # ========== PRIMARY DOCTRINES ==========
            
            TacticalMode.LAY_THE_STORY: {
                "triggers": {
                    "narrative_disruption": lambda x: x > 70,
                    "mpi": lambda x: x > 60,
                    "story_anchor": lambda x: x == "Favourite",
                    "power_anchor": lambda x: x != "Favourite"
                },
                "meaning": "Favourite propped up by storylines, not power. Oppose the narrative. Follow the power.",
                "position": "Oppose narrative. Follow power."
            },
            
            TacticalMode.SHADOW_TRACKING: {
                "triggers": {
                    "threat_cluster_has_shadow": lambda x: "shadow" in str(x).lower() or "hidden" in str(x).lower(),
                    "energy_behaviour": lambda x: "rising late" in str(x).lower() or "late-phase" in str(x).lower(),
                    "house_comfort_longshots": lambda x: x == "high"
                },
                "meaning": "Real danger isn't second favourite—it's the horse no one's watching but the numbers whisper.",
                "position": "Track shadow improver trajectory for structure confirmation."
            },
            
            TacticalMode.ENGINE_SUPREMACY: {
                "triggers": {
                    "engine_superiority": lambda x: x == "unambiguous" or x == "dominant",
                    "chaos_bloom": lambda x: x < 30,
                    "pace_shaping": lambda x: "predictable" in str(x).lower() or "controlled" in str(x).lower()
                },
                "meaning": "Controlled environment. Dominant engine. You don't fight physics.",
                "position": "Lock on dominant engine. All others downweighted."
            },
            
            TacticalMode.TOP_4_ON_DANGER: {
                "triggers": {
                    "integrity_score": lambda x: 40 < x < 70,
                    "mpi": lambda x: x < 50,
                    "chaos_bloom": lambda x: x < 35,
                    "threat_cluster_size": lambda x: x >= 3
                },
                "meaning": "Structure stable, but winner identity volatile inside cluster. Power lies in the group, not the favourite.",
                "position": "Widen focus to group instead of individual."
            },
            
            TacticalMode.HOUSE_REVERSAL: {
                "triggers": {
                    "bookmaker_comfort_fav": lambda x: x == "high",
                    "true_power_location": lambda x: "mid-tier" in str(x).lower() or "mid-price" in str(x).lower(),
                    "price_story_divergence": lambda x: x > 20
                },
                "meaning": "Market inviting favourite money, not protecting it. House misdirection pattern.",
                "position": "Treat bookmaker comfort zone as danger zone."
            },
            
            TacticalMode.SARCOPHAGUS: {
                "triggers": {
                    "chaos_bloom": lambda x: x > 60,
                    "mpi": lambda x: x > 80,
                    "narrative_extreme": lambda x: "media horse" in str(x).lower() or "unbeaten hype" in str(x).lower() or x == True
                },
                "meaning": "Race is radioactive. Best position is information extraction, not outcome exposure.",
                "position": "CONTAINMENT MODE. Informational only, not actionable."
            },
            
            # ========== SECONDARY DOCTRINES ==========
            
            TacticalMode.PRESSURE_COLLAPSE: {
                "triggers": {
                    "favourite_engine": lambda x: "fragile" in str(x).lower(),
                    "pace_pressure": lambda x: "above equilibrium" in str(x).lower() or "high" in str(x).lower(),
                    "stress_curve": lambda x: "mismatch" in str(x).lower()
                },
                "meaning": "Favourite will crack under heat.",
                "position": "Downgrade favourite. Boost pressure-resistant runners."
            },
            
            TacticalMode.OVERLAY_ABSORPTION: {
                "triggers": {
                    "integrity_score": lambda x: 60 <= x <= 80,
                    "strong_engine_match": lambda x: x == True,
                    "threat_cluster_narrow": lambda x: x == True or x <= 2
                },
                "meaning": "Allow market to overprice one danger. Exploit the inefficiency.",
                "position": "Target overpriced danger horse."
            },
            
            TacticalMode.CHAOS_BLEED: {
                "triggers": {
                    "chaos_bloom": lambda x: 40 <= x <= 75,
                    "pace_map": lambda x: "unstable" in str(x).lower(),
                    "volatile_improvers": lambda x: x == True or x > 0
                },
                "meaning": "Race will bleed out into unpredictable lanes. Structure weakens.",
                "position": "Observational, not predictive. Reduce exposure."
            },
            
            TacticalMode.DRAW_SKEW: {
                "triggers": {
                    "clear_lane_bias": lambda x: x == True,
                    "tactical_draw_misalignment": lambda x: x == True,
                    "threat_cluster_in_bias_lane": lambda x: x == True
                },
                "meaning": "Draw decides the power.",
                "position": "Follow lane bias. Downgrade runners in wrong lane."
            },
            
            TacticalMode.GATEKEEPER: {
                "triggers": {
                    "fav_trip_blocked": lambda x: x == True,
                    "front_end_distorters": lambda x: x == True or x > 0
                },
                "meaning": "Favourite sabotaged by presence of specific opponent.",
                "position": "Identify gatekeeper. Downgrade favourite."
            },
            
            TacticalMode.VETP_ECHO: {
                "triggers": {
                    "pattern_match_score": lambda x: x > 65,
                    "behavioural_resemblance": lambda x: x == True
                },
                "meaning": "When a lived scar becomes a tactical forecast. Your trauma becomes the weapon.",
                "position": "Apply historical memory penalties/bonuses."
            }
        }
    
    def evaluate_doctrines(self, oracle_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate which tactical doctrines should fire based on Oracle intelligence.
        
        Args:
            oracle_data: Complete Oracle dossier data
            
        Returns:
            List of triggered doctrines with metadata
        """
        triggered_doctrines = []
        
        for mode, rules in self.doctrine_rules.items():
            if self._check_triggers(oracle_data, rules["triggers"]):
                triggered_doctrines.append({
                    "mode": mode.value,
                    "meaning": rules["meaning"],
                    "position": rules["position"]
                })
        
        return triggered_doctrines
    
    def _check_triggers(self, oracle_data: Dict[str, Any], triggers: Dict[str, Any]) -> bool:
        """
        Check if all triggers for a doctrine are satisfied.
        
        Args:
            oracle_data: Oracle intelligence data
            triggers: Dict of trigger conditions
            
        Returns:
            True if doctrine should fire
        """
        satisfied_count = 0
        total_triggers = len(triggers)
        
        for key, condition in triggers.items():
            value = self._extract_value(oracle_data, key)
            if value is not None:
                try:
                    if condition(value):
                        satisfied_count += 1
                except:
                    pass
        
        # Doctrine fires if at least 60% of triggers are satisfied
        return satisfied_count >= (total_triggers * 0.6)
    
    def _extract_value(self, oracle_data: Dict[str, Any], key: str) -> Any:
        """
        Extract value from Oracle data structure.
        
        Handles nested keys like 'narrative.disruption_score'
        """
        if '.' in key:
            parts = key.split('.')
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
            for section in ['narrative', 'manipulation', 'energy', 'chaos', 'house', 'vetp', 'verdict']:
                if section in oracle_data and isinstance(oracle_data[section], dict):
                    if key in oracle_data[section]:
                        return oracle_data[section][key]
            
            return None
    
    def generate_doctrine_output(self, oracle_data: Dict[str, Any]) -> Dict[str, Any]:
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
            "oracle_verdict": oracle_data.get("verdict", {}).get("oracle_sentence", "")
        }


def create_attack_doctrine_engine() -> AttackDoctrineEngine:
    """Factory function to create Attack Doctrine Engine"""
    return AttackDoctrineEngine()
