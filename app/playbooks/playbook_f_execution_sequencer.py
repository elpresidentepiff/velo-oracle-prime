"""
PLAYBOOK F — EXECUTION SEQUENCER

Tactical Decision Engine

How doctrines convert into actual race positioning rules.

Playbook E tells us what the race is.
Playbook F tells us what the Oracle does with that information.

Not betting advice. Tactical positioning logic — the machine's internal decision tree.
"""

from typing import Dict, List, Any, Optional
from enum import Enum


class PositioningDirective(str, Enum):
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
    """
    
    def __init__(self):
        self.directive_rules = self._initialize_directive_rules()
        self.execution_hierarchy = [
            "power",           # Power Anchor beats all
            "manipulation",    # Rigged structure voids engine edge
            "chaos",           # Chaos collapses all logic
            "vetp_memory",     # Memory overrides arrogance
            "narrative",       # Narrative structure
            "market"           # Market behaviour
        ]
    
    def _initialize_directive_rules(self) -> Dict[PositioningDirective, Dict[str, Any]]:
        """Initialize rules for each positioning directive"""
        return {
            PositioningDirective.FAVOURITE_LIABILITY: {
                "triggers": {
                    "story_power_mismatch": lambda oracle: oracle.get("story_anchor") != oracle.get("power_anchor"),
                    "high_mpi": lambda oracle: oracle.get("mpi", 0) > 65,
                    "vetp_trap_match": lambda oracle: any("mesaafi" in str(p).lower() or "trap" in str(p).lower() 
                                                          for p in oracle.get("vetp_patterns", []))
                },
                "effect": {
                    "favourite_confidence_multiplier": 0.15,  # Downgrade -85%
                    "power_cluster_boost": 1.5,
                    "description": "Oracle downgrades favourite confidence by -40 to -85%. Power cluster boosted."
                }
            },
            
            PositioningDirective.POWER_ANCHOR: {
                "triggers": {
                    "stable_engine_superiority": lambda oracle: oracle.get("engine_superiority") == "dominant",
                    "low_chaos": lambda oracle: oracle.get("chaos_bloom", 100) < 35,
                    "adequate_integrity": lambda oracle: oracle.get("integrity_score", 0) > 50
                },
                "effect": {
                    "engine_horse_lock": True,
                    "others_downweighted": 0.5,
                    "description": "Oracle locks target on the engine horse. All other horses downweighted."
                }
            },
            
            PositioningDirective.MULTI_THREAT_ZONE: {
                "triggers": {
                    "large_threat_cluster": lambda oracle: len(oracle.get("threat_cluster", [])) > 3,
                    "moderate_integrity": lambda oracle: oracle.get("integrity_score", 100) < 65,
                    "controlled_chaos": lambda oracle: oracle.get("chaos_bloom", 100) < 40
                },
                "effect": {
                    "focus_mode": "group",
                    "individual_confidence_reduction": 0.7,
                    "description": "Oracle widens focus to group instead of individual."
                }
            },
            
            PositioningDirective.NARRATIVE_FRACTURE: {
                "triggers": {
                    "extreme_narrative_disruption": lambda oracle: oracle.get("narrative_disruption", 0) > 80,
                    "media_reality_gap": lambda oracle: oracle.get("media_sync", 0) > 0.75
                },
                "effect": {
                    "suppress_narrative_favourites": True,
                    "mid_range_power_boost": 1.8,
                    "description": "Oracle suppresses all favourites with narrative inflation. Mid-range power gets heavy promotion."
                }
            },
            
            PositioningDirective.HOUSE_REVERSAL: {
                "triggers": {
                    "excessive_bookmaker_pressure": lambda oracle: oracle.get("bookmaker_comfort_fav") == "high",
                    "price_power_divergence": lambda oracle: oracle.get("price_power_divergence", 0) > 18
                },
                "effect": {
                    "bookmaker_comfort_inversion": True,
                    "comfort_zone_penalty": 0.6,
                    "description": "Oracle treats bookmaker comfort zone as a danger zone."
                }
            },
            
            PositioningDirective.CHAOS_CONTAINMENT: {
                "triggers": {
                    "high_chaos": lambda oracle: oracle.get("chaos_bloom", 0) > 60,
                    "low_integrity": lambda oracle: oracle.get("integrity_score", 100) < 30,
                    "no_stable_engine": lambda oracle: oracle.get("engine_superiority") != "dominant"
                },
                "effect": {
                    "structure_collapse_flag": True,
                    "actionable": False,
                    "description": "Oracle outputs 'structure collapse' flag. Race marked informational, not actionable."
                }
            },
            
            PositioningDirective.VETP_IMPRINT: {
                "triggers": {
                    "high_pattern_match": lambda oracle: max([p.get("score", 0) for p in oracle.get("vetp_patterns", [{}])], default=0) > 65
                },
                "effect": {
                    "memory_penalties_active": True,
                    "behavioural_classification_adjusted": True,
                    "description": "Oracle enforces memory penalties or bonuses. Adjusts behavioural classification."
                }
            }
        }
    
    def execute_sequence(self, oracle_data: Dict[str, Any], doctrines: List[str]) -> Dict[str, Any]:
        """
        Execute the full decision sequence.
        
        STEP 1: Identify anchors
        STEP 2: Quantify structural integrity
        STEP 3: Compute manipulation vectors
        STEP 4: Evaluate historical resonance (VETP)
        STEP 5: Doctrine triggering (from Playbook E)
        STEP 6: Convert doctrines → Positioning Directive
        STEP 7: Generate Oracle sentence
        STEP 8: Build dual-layer report
        
        Args:
            oracle_data: Complete Oracle intelligence
            doctrines: List of triggered doctrines from Playbook E
            
        Returns:
            Execution output with positioning directive
        """
        # STEP 1: Identify anchors
        anchors = self._identify_anchors(oracle_data)
        
        # STEP 2-4: Already in oracle_data
        
        # STEP 5: Doctrines already provided
        
        # STEP 6: Convert doctrines to positioning directive
        directive = self._determine_positioning_directive(oracle_data, doctrines)
        
        # STEP 7: Oracle sentence (already in oracle_data)
        
        # STEP 8: Build execution output
        return self._build_execution_output(oracle_data, anchors, doctrines, directive)
    
    def _identify_anchors(self, oracle_data: Dict[str, Any]) -> Dict[str, Any]:
        """Identify power, story, chaos, and VETP anchors"""
        return {
            "power": oracle_data.get("power_anchor", "Unknown"),
            "story": oracle_data.get("story_anchor", "Favourite"),
            "chaos": "High" if oracle_data.get("chaos_bloom", 0) > 60 else "Low",
            "vetp_match": self._get_top_vetp_match(oracle_data)
        }
    
    def _get_top_vetp_match(self, oracle_data: Dict[str, Any]) -> str:
        """Get the top VETP pattern match"""
        vetp_patterns = oracle_data.get("vetp_patterns", [])
        if not vetp_patterns:
            return "None"
        
        top_pattern = max(vetp_patterns, key=lambda x: x.get("score", 0), default={})
        if top_pattern:
            return f"{top_pattern.get('pattern', 'Unknown')} ({top_pattern.get('score', 0)}%)"
        return "None"
    
    def _determine_positioning_directive(
        self,
        oracle_data: Dict[str, Any],
        doctrines: List[str]
    ) -> PositioningDirective:
        """
        Determine the primary positioning directive.
        
        Uses doctrine combinations and Oracle data to select the best directive.
        """
        # Check each directive's triggers
        triggered_directives = []
        
        for directive, rules in self.directive_rules.items():
            satisfied = sum(1 for trigger in rules["triggers"].values() 
                          if self._safe_trigger_check(trigger, oracle_data))
            total = len(rules["triggers"])
            
            if satisfied >= (total * 0.6):  # 60% threshold
                triggered_directives.append((directive, satisfied / total))
        
        # If multiple directives triggered, use execution hierarchy
        if triggered_directives:
            # Sort by score
            triggered_directives.sort(key=lambda x: x[1], reverse=True)
            return triggered_directives[0][0]
        
        # Fallback: Determine from doctrines
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
    
    def _safe_trigger_check(self, trigger_func, oracle_data: Dict[str, Any]) -> bool:
        """Safely check a trigger function"""
        try:
            return trigger_func(oracle_data)
        except:
            return False
    
    def _build_execution_output(
        self,
        oracle_data: Dict[str, Any],
        anchors: Dict[str, Any],
        doctrines: List[str],
        directive: PositioningDirective
    ) -> Dict[str, Any]:
        """Build the complete execution output"""
        
        # Get directive effect
        effect = self.directive_rules[directive]["effect"]
        
        # Build confidence vector
        confidence_vector = {
            "engine": oracle_data.get("engine_confidence", 0.5),
            "chaos": 1.0 - (oracle_data.get("chaos_bloom", 50) / 100.0),
            "manipulation": oracle_data.get("mpi", 50) / 100.0,
            "narrative": oracle_data.get("narrative_disruption", 50) / 100.0,
            "vetp_bias": max([p.get("score", 0) for p in oracle_data.get("vetp_patterns", [{}])], default=0) / 100.0
        }
        
        return {
            "anchors": anchors,
            "doctrines_fired": doctrines,
            "positioning_directive": directive.value,
            "directive_effect": effect,
            "confidence_vector": confidence_vector,
            "oracle_sentence": oracle_data.get("oracle_sentence", ""),
            "actionable": effect.get("actionable", True)
        }


def create_execution_sequencer() -> ExecutionSequencer:
    """Factory function to create Execution Sequencer"""
    return ExecutionSequencer()
