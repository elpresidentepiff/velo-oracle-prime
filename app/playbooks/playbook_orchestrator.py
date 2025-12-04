"""
PLAYBOOK ORCHESTRATOR

Integrates all three playbooks into a unified intelligence system:
- Playbook E: Attack Doctrine Engine
- Playbook F: Execution Sequencer
- Playbook G: Sentient Loopback Engine

This is the complete VÉLØ intelligence stack.
"""

from typing import Dict, List, Any
from .playbook_e_attack_doctrine import create_attack_doctrine_engine
from .playbook_f_execution_sequencer import create_execution_sequencer
from .playbook_g_sentient_loopback import create_sentient_loopback_engine


class PlaybookOrchestrator:
    """
    The complete VÉLØ Playbook system.
    
    Orchestrates:
    1. Oracle Intelligence (dual-layer analysis)
    2. Attack Doctrine Engine (tactical modes)
    3. Execution Sequencer (positioning directives)
    4. Sentient Loopback (self-evolution)
    """
    
    def __init__(self):
        self.attack_doctrine = create_attack_doctrine_engine()
        self.execution_sequencer = create_execution_sequencer()
        self.sentient_loopback = create_sentient_loopback_engine()
    
    def analyze_race(self, oracle_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Complete race analysis through all playbooks.
        
        Flow:
        1. Oracle generates intelligence → oracle_data
        2. Playbook E evaluates doctrines
        3. Playbook F determines positioning directive
        4. Output complete tactical intelligence
        
        Args:
            oracle_data: Complete Oracle dossier
            
        Returns:
            Complete playbook output
        """
        # PLAYBOOK E: Evaluate attack doctrines
        doctrine_output = self.attack_doctrine.generate_doctrine_output(oracle_data)
        doctrines_triggered = doctrine_output["doctrines_triggered"]
        
        # PLAYBOOK F: Execute positioning sequence
        execution_output = self.execution_sequencer.execute_sequence(
            oracle_data,
            doctrines_triggered
        )
        
        # PLAYBOOK G: Get evolutionary state
        evolutionary_state = self.sentient_loopback.get_evolutionary_state()
        
        # Identify kingmaker
        kingmaker = self.sentient_loopback.identify_kingmaker(oracle_data)
        
        # Build complete output
        return {
            "race_id": oracle_data.get("race_id", "unknown"),
            "timestamp": oracle_data.get("timestamp", ""),
            
            # Oracle Intelligence
            "oracle": {
                "narrative_disruption": oracle_data.get("narrative_disruption", 0),
                "mpi": oracle_data.get("mpi", 0),
                "chaos_bloom": oracle_data.get("chaos_bloom", 0),
                "integrity_score": oracle_data.get("integrity_score", 0),
                "oracle_sentence": oracle_data.get("oracle_sentence", "")
            },
            
            # Playbook E: Attack Doctrines
            "attack_doctrines": {
                "triggered": doctrines_triggered,
                "details": doctrine_output.get("doctrine_details", []),
                "threat_cluster": doctrine_output.get("threat_cluster", []),
                "power_anchor": doctrine_output.get("power_anchor", ""),
                "story_anchor": doctrine_output.get("story_anchor", "")
            },
            
            # Playbook F: Execution
            "execution": {
                "positioning_directive": execution_output.get("positioning_directive", ""),
                "directive_effect": execution_output.get("directive_effect", {}),
                "confidence_vector": execution_output.get("confidence_vector", {}),
                "actionable": execution_output.get("actionable", True),
                "anchors": execution_output.get("anchors", {})
            },
            
            # Playbook G: Evolution
            "sentient_state": evolutionary_state,
            
            # Kingmaker
            "kingmaker": kingmaker,
            
            # Meta
            "playbooks_version": "1.0",
            "system": "VÉLØ PRIME"
        }
    
    def record_outcome(
        self,
        race_data: Dict[str, Any],
        prediction: Dict[str, Any],
        actual_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Record race outcome and trigger sentient evolution.
        
        This is the loopback: observe → learn → evolve
        
        Args:
            race_data: Original race intelligence
            prediction: What we predicted
            actual_result: What actually happened
            
        Returns:
            Evolution report
        """
        return self.sentient_loopback.observe_race_outcome(
            race_data,
            prediction,
            actual_result
        )
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get complete system status"""
        evolutionary_state = self.sentient_loopback.get_evolutionary_state()
        
        return {
            "system": "VÉLØ PRIME",
            "version": "1.0",
            "playbooks_active": ["E", "F", "G"],
            "total_races_observed": evolutionary_state["total_races_observed"],
            "appetite_multiplier": evolutionary_state["appetite_multiplier"],
            "doctrine_count": 12,
            "positioning_directives": 7,
            "evolution_pillars": 5,
            "self_improving": True,
            "status": "operational"
        }


def create_playbook_orchestrator() -> PlaybookOrchestrator:
    """Factory function to create complete playbook system"""
    return PlaybookOrchestrator()
