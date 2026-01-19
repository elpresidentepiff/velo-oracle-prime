"""
Shadow Racing Runner for V13 Observe-Only Mode

Runs VÉLØ engine on live race cards, executes critics, persists proposals.
No auto-apply, no learning, no doctrine mutation.

Author: VÉLØ Team
Date: 2026-01-19
Status: Active
"""

import sqlite3
from datetime import datetime, UTC, timedelta
from typing import Dict, Any, List, Optional
import json
import hashlib

from ..governance import ProposalPersistence, ProposalTransitions


class ShadowRacingRunner:
    """
    Shadow racing runner for V13 observe-only mode.
    
    Constitutional guarantees:
    - No auto-apply (all proposals end in PENDING)
    - No learning (no model updates)
    - No doctrine mutation (no rule application)
    - Read-only critics (zero state mutation)
    - Epistemic time separation (decisionTime ≠ createdAt)
    """
    
    def __init__(self, db_connection: sqlite3.Connection):
        self.db = db_connection
        self.persistence = ProposalPersistence(db_connection)
        self.transitions = ProposalTransitions(db_connection)
    
    def run_race(self, race_data: Dict[str, Any]) -> str:
        """
        Run shadow racing for a single race.
        
        Args:
            race_data: Race data dict with:
                - race_id: Unique race identifier
                - off_time: Race start time (ISO 8601)
                - venue: Venue name
                - distance: Distance in meters
                - going: Going description
                - class_: Race class
                - runners: List of runner dicts
                - market_snapshot: Market data at decision time
                - form_data: Historical form data
        
        Returns:
            Episode ID
        """
        # 1. Create episode
        decision_time = datetime.fromisoformat(race_data["off_time"]) - timedelta(minutes=10)
        episode_id = self._create_episode(
            race_id=race_data["race_id"],
            decision_time=decision_time,
            context={
                "venue": race_data["venue"],
                "distance": race_data["distance"],
                "going": race_data["going"],
                "class": race_data.get("class_"),
            }
        )
        
        # 2. Write PRE_STATE artifact
        pre_state = {
            "runners": race_data["runners"],
            "market": race_data["market_snapshot"],
            "form": race_data["form_data"],
        }
        self._write_artifact(episode_id, "PRE_STATE", pre_state)
        
        # 3. Run engine (placeholder - integrate actual engine)
        inference = self._run_engine(episode_id, pre_state)
        
        # 4. Write INFERENCE artifact
        self._write_artifact(episode_id, "INFERENCE", inference)
        
        # 5. Run critics (placeholder - integrate actual critics)
        self._run_critics(episode_id)
        
        return episode_id
    
    def finalize_race(self, episode_id: str, result: Dict[str, Any]):
        """
        Finalize episode after race completes.
        
        Args:
            episode_id: Episode ID
            result: Race result dict with:
                - winner: Winner runner ID
                - placed: List of placed runner IDs
                - starting_prices: Dict of runner ID to SP
        """
        # 1. Write OUTCOME artifact
        outcome = {
            "winner": result["winner"],
            "placed": result["placed"],
            "sp": result["starting_prices"],
        }
        self._write_artifact(episode_id, "OUTCOME", outcome)
        
        # 2. Mark episode as finalized
        self.db.execute(
            "UPDATE episodes SET finalized = TRUE, finalized_at = ? WHERE id = ?",
            (datetime.now(UTC).isoformat(), episode_id)
        )
        self.db.commit()
        
        # 3. Transition proposals to PENDING
        self.transitions.transition_to_pending(episode_id)
    
    def _create_episode(
        self,
        race_id: str,
        decision_time: datetime,
        context: Dict[str, Any]
    ) -> str:
        """
        Create episode with epistemic time separation.
        
        Args:
            race_id: Race identifier
            decision_time: When the decision was made (knowledge cutoff)
            context: Episode context dict
        
        Returns:
            Episode ID
        """
        # Generate deterministic episode ID
        # Format: race_{date}_{race_id}
        episode_id = f"race_{decision_time.strftime('%Y-%m-%d')}_{race_id}"
        
        # Generate context hash
        context_str = json.dumps(context, sort_keys=True)
        context_hash = hashlib.sha256(context_str.encode()).hexdigest()[:16]
        
        # Insert episode
        self.db.execute(
            """
            INSERT OR IGNORE INTO episodes (
                id, decision_time, created_at, context_hash, finalized
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                episode_id,
                decision_time.isoformat(),
                datetime.now(UTC).isoformat(),
                context_hash,
                False,
            )
        )
        self.db.commit()
        
        return episode_id
    
    def _write_artifact(
        self,
        episode_id: str,
        artifact_type: str,
        payload: Dict[str, Any]
    ):
        """
        Write artifact to episode.
        
        Args:
            episode_id: Episode ID
            artifact_type: PRE_STATE, INFERENCE, or OUTCOME
            payload: Artifact payload dict
        """
        payload_json = json.dumps(payload, sort_keys=True)
        payload_checksum = hashlib.sha256(payload_json.encode()).hexdigest()
        
        # Generate artifact ID
        artifact_id = f"{episode_id}_{artifact_type}"
        
        self.db.execute(
            """
            INSERT OR REPLACE INTO episode_artifacts (
                id, episode_id, artifact_type, content, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                episode_id,
                artifact_type,
                payload_json,
                datetime.now(UTC).isoformat(),
            )
        )
        self.db.commit()
    
    def _run_engine(
        self,
        episode_id: str,
        pre_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run VÉLØ engine (placeholder).
        
        TODO: Integrate actual VÉLØ engine from existing codebase.
        
        Args:
            episode_id: Episode ID
            pre_state: Pre-state artifact
        
        Returns:
            Inference result dict
        """
        # Placeholder inference
        return {
            "verdict": "PLACEHOLDER",
            "confidence": 0.0,
            "top_4": [],
            "internal_signals": {},
            "rationale": "Placeholder inference - engine not yet integrated",
        }
    
    def _run_critics(self, episode_id: str):
        """
        Run all critics on episode (placeholder).
        
        TODO: Integrate actual critics from existing codebase.
        
        Args:
            episode_id: Episode ID
        """
        # Placeholder critics - generate sample proposals
        
        # Leakage Detector
        self.persistence.persist_proposals(
            episode_id=episode_id,
            critic_type="LEAKAGE",
            proposals=[
                {
                    "severity": "CRITICAL",
                    "finding_type": "FUTURE_MARKET_LEAKAGE",
                    "description": "Placeholder: Market snapshot timestamp validation needed",
                    "proposed_change": {
                        "rule_type": "temporal_validation",
                        "condition": "market_snapshot.timestamp <= decision_time",
                    }
                }
            ]
        )
        
        # Cognitive Bias
        self.persistence.persist_proposals(
            episode_id=episode_id,
            critic_type="BIAS",
            proposals=[
                {
                    "severity": "HIGH",
                    "finding_type": "ANCHORING_BIAS",
                    "description": "Placeholder: Favorite over-weighted by 15%",
                    "proposed_change": {
                        "rule_type": "confidence_calibration",
                        "adjustment": -0.15,
                    }
                }
            ]
        )
        
        # Feature Extractor
        self.persistence.persist_proposals(
            episode_id=episode_id,
            critic_type="FEATURE",
            proposals=[
                {
                    "severity": "MEDIUM",
                    "finding_type": "MISSING_FEATURE",
                    "description": "Placeholder: Jockey strike rate not included",
                    "proposed_change": {
                        "rule_type": "feature_addition",
                        "feature_name": "jockey_strike_rate",
                    }
                }
            ]
        )
        
        # Decision Critic
        self.persistence.persist_proposals(
            episode_id=episode_id,
            critic_type="DECISION",
            proposals=[
                {
                    "severity": "LOW",
                    "finding_type": "NARRATIVE_DRIFT",
                    "description": "Placeholder: Rationale mentions form but doesn't cite specific races",
                    "proposed_change": {
                        "rule_type": "rationale_validation",
                        "requirement": "cite_specific_races",
                    }
                }
            ]
        )
    
    def get_episode_stats(self) -> Dict[str, int]:
        """
        Get episode statistics.
        
        Returns:
            Dict with episode counts
        """
        cursor = self.db.execute(
            "SELECT COUNT(*) FROM episodes WHERE finalized = FALSE"
        )
        pending = cursor.fetchone()[0]
        
        cursor = self.db.execute(
            "SELECT COUNT(*) FROM episodes WHERE finalized = TRUE"
        )
        finalized = cursor.fetchone()[0]
        
        return {
            "processed": pending + finalized,
            "finalized": finalized,
            "pending": pending,
        }
