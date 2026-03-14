"""
PLAYBOOK ORCHESTRATOR

Integrates all three playbooks into a unified intelligence system:
- Playbook E: Attack Doctrine Engine
- Playbook F: Execution Sequencer
- Playbook G: Sentient Loopback Engine

This is the complete VÉLØ intelligence stack.

FIX (sentient-feedback-loop): The orchestrator now injects G's current evolutionary
state into E and F before every race analysis. This closes the sentient loop:

    Race data in
        ↓
    G's state read (threshold, emotion_laws, doctrine_strengths, structural_drift)
        ↓
    E evaluates doctrines using G's threshold + emotion law penalties
        ↓
    F selects directive using G's doctrine_strengths + structural_drift + hierarchy
        ↓
    Prediction made
        ↓
    Race runs → record_outcome() → G evolves
        ↓
    Next race: E and F are different because G evolved
        ↓
    Repeat forever

SPOTLIGHT INTEGRATION (5-step sequence — enforced):
    STEP 1: Structural layers run (Class, Differential, Setup, Stamina, Survivability)
    STEP 2: Intent Override and Market layers run
    STEP 3: Spotlight NLP pass — SpotlightGate.apply_modifiers() called
             → Flags modify existing scores ONLY
             → No new chassis entry via spotlight alone
             → Regime blocks cannot be lifted by spotlight
    STEP 4: Day Classification Engine runs (spotlight push is one input, not the driver)
    STEP 5: Verdict assembled — structural case is primary, spotlight tags are annotations

Doctrine: docs/VELO_SPOTLIGHT_HARD_LIMITS.md
"""

import sys
import os
from typing import Dict, List, Any, Optional
from .playbook_e_attack_doctrine import create_attack_doctrine_engine
from .playbook_f_execution_sequencer import create_execution_sequencer
from .playbook_g_sentient_loopback import create_sentient_loopback_engine

# Spotlight gate — enforces the hard architectural rule:
# "A spotlight comment cannot generate a selection. It can only modify one."
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'workers'))
    from spotlight_parser import SpotlightGate
    _SPOTLIGHT_AVAILABLE = True
except ImportError:
    _SPOTLIGHT_AVAILABLE = False
    import logging
    logging.getLogger(__name__).warning(
        "spotlight_parser not found — spotlight modifier layer disabled."
    )


class PlaybookOrchestrator:
    """
    The complete VÉLØ Playbook system.

    Orchestrates:
    1. Oracle Intelligence (dual-layer analysis)
    2. Attack Doctrine Engine (tactical modes) — G-aware
    3. Execution Sequencer (positioning directives) — G-aware
    4. Sentient Loopback (self-evolution)
    """

    def __init__(self):
        self.sentient_loopback = create_sentient_loopback_engine()
        # E and F are initialised with G's current state immediately
        initial_state = self.sentient_loopback.get_evolutionary_state()
        self.attack_doctrine = create_attack_doctrine_engine(sentient_state=initial_state)
        self.execution_sequencer = create_execution_sequencer(sentient_state=initial_state)

    def _sync_sentient_state(self):
        """
        Push G's latest evolved state into E and F.

        Called at the start of every analyze_race() call to ensure E and F
        are always operating on the most current G state.
        """
        current_state = self.sentient_loopback.get_evolutionary_state()
        self.attack_doctrine.update_sentient_state(current_state)
        self.execution_sequencer.update_sentient_state(current_state)

    def analyze_race(
        self,
        oracle_data: Dict[str, Any],
        spotlight_records: Optional[Dict[str, dict]] = None,
    ) -> Dict[str, Any]:
        """
        Complete race analysis through all playbooks.

        Flow (5-step spotlight integration enforced):
        1. Sync G's evolved state into E and F (closes the feedback loop)
        2. Playbook E evaluates doctrines using G's threshold + emotion laws
           (structural layers — Steps 1 & 2 of spotlight sequence)
        3. Spotlight NLP pass via SpotlightGate — modifiers applied to runners
           already in the preliminary chassis ONLY (Step 3)
        4. Playbook F determines positioning directive (Step 4 — Day Classification)
        5. Output assembled — structural case primary, spotlight tags as annotations

        Args:
            oracle_data:        Complete Oracle dossier
            spotlight_records:  Optional dict of {horse_name: spotlight_record}
                                from spotlight_parser.extract_spotlight_signals().
                                If None, spotlight modifier layer is skipped.

        Returns:
            Complete playbook output
        """
        # SYNC: Push G's current state into E and F before every analysis
        self._sync_sentient_state()

        # STEP 1 & 2: Structural layers + Intent/Market (Playbook E)
        doctrine_output = self.attack_doctrine.generate_doctrine_output(oracle_data)
        doctrines_triggered = doctrine_output["doctrines_triggered"]

        # STEP 3: Spotlight NLP pass — SpotlightGate enforces hard limits
        # NULL PATHWAY CONTRACT:
        #   If spotlight_records is None, empty, or the spotlight module is
        #   unavailable, the engine continues cleanly on structural-only verdict.
        #   No exception is raised. No warning noise is emitted to the caller.
        #   The output will carry spotlight_layer.active = False and
        #   spotlight_layer.null_reason explaining why.
        #   This is the correct behaviour on days when card data is unavailable,
        #   PDF parse fails, or the source has no per-horse comments.
        spotlight_gate_summary = {"applied": 0, "blocked": 0, "total": 0}
        spotlight_null_reason = None
        try:
            if not _SPOTLIGHT_AVAILABLE:
                spotlight_null_reason = "SPOTLIGHT_MODULE_UNAVAILABLE"
            elif spotlight_records is None:
                spotlight_null_reason = "NO_SPOTLIGHT_RECORDS_PROVIDED"
            elif len(spotlight_records) == 0:
                spotlight_null_reason = "SPOTLIGHT_RECORDS_EMPTY"
            else:
                gate = SpotlightGate()
                runners = oracle_data.get("runners", [])
                for runner in runners:
                    horse_name = runner.get("horse_name", runner.get("name", ""))
                    spotlight_record = spotlight_records.get(horse_name)
                    if spotlight_record:
                        gate.apply_modifiers(runner, spotlight_record)
                spotlight_gate_summary = gate.summary()
        except Exception as exc:  # noqa: BLE001
            # Pipeline failure must never block the engine.
            # Log the error, set null reason, continue on structural-only verdict.
            import logging
            logging.getLogger(__name__).error(
                f"[SPOTLIGHT_PIPELINE_FAILURE] Exception in spotlight gate: {exc}. "
                "Continuing on structural-only verdict.",
                exc_info=True,
            )
            spotlight_null_reason = f"PIPELINE_EXCEPTION: {type(exc).__name__}"
            spotlight_gate_summary = {"applied": 0, "blocked": 0, "total": 0}

        # PLAYBOOK F: Execute positioning sequence (G-aware)
        execution_output = self.execution_sequencer.execute_sequence(
            oracle_data,
            doctrines_triggered
        )

        # PLAYBOOK G: Get evolutionary state for output
        evolutionary_state = self.sentient_loopback.get_evolutionary_state()

        # Identify kingmaker (now uses running_style from runners list)
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
                "story_anchor": doctrine_output.get("story_anchor", ""),
                "threshold_used": doctrine_output.get("threshold_used", 0.6),
                "emotion_penalties_active": doctrine_output.get("emotion_penalties_active", False)
            },

            # Playbook F: Execution
            "execution": {
                "positioning_directive": execution_output.get("positioning_directive", ""),
                "directive_effect": execution_output.get("directive_effect", {}),
                "confidence_vector": execution_output.get("confidence_vector", {}),
                "actionable": execution_output.get("actionable", True),
                "anchors": execution_output.get("anchors", {}),
                "threshold_used": execution_output.get("threshold_used", 0.6),
                "hierarchy_applied": execution_output.get("hierarchy_applied", False)
            },

            # Playbook G: Evolution (includes structural_drift for transparency)
            "sentient_state": {
                "total_races_observed": evolutionary_state["total_races_observed"],
                "appetite_multiplier": evolutionary_state["appetite_multiplier"],
                "doctrine_strengths": evolutionary_state["doctrine_strengths"],
                "structural_drift": evolutionary_state["structural_drift"],
                "emotion_laws_count": evolutionary_state["emotion_laws_count"],
                "last_updated": evolutionary_state["last_updated"]
            },

            # Kingmaker
            "kingmaker": kingmaker,

            # Spotlight Layer (Step 3 gate summary)
            # null_reason is set when spotlight data was absent or pipeline failed.
            # The engine always returns a valid verdict regardless.
            "spotlight_layer": {
                "active": spotlight_null_reason is None,
                "modifiers_applied": spotlight_gate_summary["applied"],
                "modifiers_blocked": spotlight_gate_summary["blocked"],
                "null_reason": spotlight_null_reason,
                "doctrine": "docs/VELO_SPOTLIGHT_HARD_LIMITS.md"
            },

            # Meta
            "playbooks_version": "1.2",
            "system": "VÉLØ PRIME",
            "sentient_loop_active": True,
            "spotlight_gate_active": True
        }

    def record_outcome(
        self,
        race_data: Dict[str, Any],
        prediction: Dict[str, Any],
        actual_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Record race outcome and trigger sentient evolution.

        This is the loopback: observe → learn → evolve → redeploy

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
            "version": "1.1",
            "playbooks_active": ["E", "F", "G"],
            "total_races_observed": evolutionary_state["total_races_observed"],
            "appetite_multiplier": evolutionary_state["appetite_multiplier"],
            "doctrine_count": 12,
            "positioning_directives": 7,
            "evolution_pillars": 5,
            "self_improving": True,
            "sentient_loop_active": True,
            "status": "operational"
        }


def create_playbook_orchestrator() -> PlaybookOrchestrator:
    """Factory function to create complete playbook system"""
    return PlaybookOrchestrator()
