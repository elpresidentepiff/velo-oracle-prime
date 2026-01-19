"""
VÉLØ V13 - Leakage Detector Critic

Detects temporal leakage (future information contaminating pre-state).

Leakage Types:
- Future outcome leakage (ISP, winner, finishing position in pre-state)
- Future market leakage (market snapshots after decision time)
- Timestamp violations (data timestamps after decision time)
- Lookahead bias (suspicious feature names suggesting future knowledge)
- Training contamination (test set information in training features)

Author: VÉLØ Team
Date: 2026-01-19
Status: LOCKED
Doctrine: DOCTRINE_CRITIC_AUTHORITY, DOCTRINE_EPISTEMIC_TIME
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from ..doctrine import enforce_read_only, enforce_episode_bound
from ..episodes.schema import Episode, EpisodeArtifact, ArtifactType


@dataclass
class LeakageFinding:
    """A single leakage detection finding."""
    leakage_type: str  # FUTURE_OUTCOME, FUTURE_MARKET, etc.
    description: str
    evidence: dict[str, Any]  # Episode artifact citations
    severity: str  # INFO, WARNING, CRITICAL


@dataclass
class LeakageCritique:
    """Result of leakage detection critique."""
    episode_id: str
    findings: list[LeakageFinding]
    is_clean: bool
    total_leaks: int


@dataclass
class LeakagePatchProposal:
    """Proposed patch to fix leakage."""
    episode_id: str
    leakage_type: str
    proposed_fix: str
    rationale: str


class LeakageDetectorCritic:
    """
    Read-only critic that detects temporal leakage.
    
    Doctrine:
    - Read-only (no state mutation)
    - Episode-bound (all findings cite artifacts)
    - No auto-apply (emits proposals only)
    - Anchored to decisionTime (epistemic time)
    """
    
    # Suspicious feature names that suggest lookahead bias
    LOOKAHEAD_PATTERNS = [
        "winner", "finishing_position", "final_time", "result",
        "actual_", "outcome_", "post_race_", "final_"
    ]
    
    # Outcome fields that should never appear in pre-state
    OUTCOME_FIELDS = [
        "isp", "finishing_position", "winner", "result", "actual_time"
    ]
    
    @enforce_read_only
    @enforce_episode_bound
    def critique(
        self,
        episode: Episode,
        artifacts: list[EpisodeArtifact],
    ) -> LeakageCritique:
        """
        Detect temporal leakage in episode artifacts.
        
        Args:
            episode: Episode to critique
            artifacts: All artifacts for this episode
            
        Returns:
            LeakageCritique with findings
            
        Doctrine: DOCTRINE_CRITIC_AUTHORITY, DOCTRINE_EPISTEMIC_TIME
        """
        findings: list[LeakageFinding] = []
        
        # Get PRE_STATE artifact
        pre_state_artifact = next(
            (a for a in artifacts if a.artifact_type == ArtifactType.PRE_STATE),
            None
        )
        
        if not pre_state_artifact:
            return LeakageCritique(
                episode_id=episode.id,
                findings=[],
                is_clean=True,
                total_leaks=0,
            )
        
        pre_state = pre_state_artifact.payload
        
        # Check for future outcome leakage
        findings.extend(self._detect_future_outcome_leakage(
            episode, pre_state_artifact, pre_state
        ))
        
        # Check for future market leakage
        findings.extend(self._detect_future_market_leakage(
            episode, pre_state_artifact, pre_state
        ))
        
        # Check for timestamp violations
        findings.extend(self._detect_timestamp_violations(
            episode, pre_state_artifact, pre_state
        ))
        
        # Check for lookahead bias
        findings.extend(self._detect_lookahead_bias(
            episode, pre_state_artifact, pre_state
        ))
        
        return LeakageCritique(
            episode_id=episode.id,
            findings=findings,
            is_clean=len(findings) == 0,
            total_leaks=len(findings),
        )
    
    def _detect_future_outcome_leakage(
        self,
        episode: Episode,
        artifact: EpisodeArtifact,
        pre_state: dict[str, Any],
    ) -> list[LeakageFinding]:
        """Detect outcome information in pre-state."""
        findings = []
        
        # Check for outcome fields in pre-state
        for field in self.OUTCOME_FIELDS:
            if field in pre_state:
                findings.append(LeakageFinding(
                    leakage_type="FUTURE_OUTCOME",
                    description=f"Outcome field '{field}' found in pre-state",
                    evidence={
                        "artifact_id": artifact.id,
                        "field": field,
                        "value": pre_state[field],
                    },
                    severity="CRITICAL",
                ))
        
        # Check runners for outcome fields
        if "runners" in pre_state:
            for i, runner in enumerate(pre_state["runners"]):
                for field in self.OUTCOME_FIELDS:
                    if field in runner:
                        findings.append(LeakageFinding(
                            leakage_type="FUTURE_OUTCOME",
                            description=f"Outcome field '{field}' found in runner {i} pre-state",
                            evidence={
                                "artifact_id": artifact.id,
                                "runner_index": i,
                                "field": field,
                                "value": runner[field],
                            },
                            severity="CRITICAL",
                        ))
        
        return findings
    
    def _detect_future_market_leakage(
        self,
        episode: Episode,
        artifact: EpisodeArtifact,
        pre_state: dict[str, Any],
    ) -> list[LeakageFinding]:
        """Detect market snapshots after decision time."""
        findings = []
        
        # Check market_snapshots for timestamps after decision time
        if "market_snapshots" in pre_state:
            for i, snapshot in enumerate(pre_state["market_snapshots"]):
                if "timestamp" in snapshot:
                    snapshot_time = datetime.fromisoformat(
                        snapshot["timestamp"].replace("Z", "+00:00")
                    )
                    
                    # Compare against episode.decisionTime (EPISTEMIC TIME)
                    if snapshot_time > episode.decision_time:
                        findings.append(LeakageFinding(
                            leakage_type="FUTURE_MARKET",
                            description=f"Market snapshot {i} is after decision time",
                            evidence={
                                "artifact_id": artifact.id,
                                "snapshot_index": i,
                                "snapshot_time": snapshot["timestamp"],
                                "decision_time": episode.decision_time.isoformat(),
                            },
                            severity="CRITICAL",
                        ))
        
        return findings
    
    def _detect_timestamp_violations(
        self,
        episode: Episode,
        artifact: EpisodeArtifact,
        pre_state: dict[str, Any],
    ) -> list[LeakageFinding]:
        """Detect data timestamps after decision time."""
        findings = []
        
        # Check for timestamp fields in pre-state
        timestamp_fields = ["timestamp", "updated_at", "fetched_at", "scraped_at"]
        
        for field in timestamp_fields:
            if field in pre_state:
                try:
                    data_time = datetime.fromisoformat(
                        pre_state[field].replace("Z", "+00:00")
                    )
                    
                    # Compare against episode.decisionTime (EPISTEMIC TIME)
                    if data_time > episode.decision_time:
                        findings.append(LeakageFinding(
                            leakage_type="TIMESTAMP_VIOLATION",
                            description=f"Timestamp field '{field}' is after decision time",
                            evidence={
                                "artifact_id": artifact.id,
                                "field": field,
                                "data_time": pre_state[field],
                                "decision_time": episode.decision_time.isoformat(),
                            },
                            severity="WARNING",
                        ))
                except (ValueError, AttributeError):
                    # Skip invalid timestamps
                    pass
        
        return findings
    
    def _detect_lookahead_bias(
        self,
        episode: Episode,
        artifact: EpisodeArtifact,
        pre_state: dict[str, Any],
    ) -> list[LeakageFinding]:
        """Detect suspicious feature names suggesting future knowledge."""
        findings = []
        
        # Check features for lookahead patterns
        if "features" in pre_state:
            for feature_name in pre_state["features"].keys():
                for pattern in self.LOOKAHEAD_PATTERNS:
                    if pattern in feature_name.lower():
                        findings.append(LeakageFinding(
                            leakage_type="LOOKAHEAD_BIAS",
                            description=f"Suspicious feature name '{feature_name}' suggests future knowledge",
                            evidence={
                                "artifact_id": artifact.id,
                                "feature_name": feature_name,
                                "pattern": pattern,
                            },
                            severity="WARNING",
                        ))
        
        return findings
    
    def propose_patch(
        self,
        critique: LeakageCritique,
    ) -> list[LeakagePatchProposal]:
        """
        Propose patches to fix detected leakage.
        
        Args:
            critique: Leakage critique with findings
            
        Returns:
            List of patch proposals
            
        Doctrine: DOCTRINE_CRITIC_AUTHORITY (no auto-apply)
        """
        proposals = []
        
        for finding in critique.findings:
            if finding.leakage_type == "FUTURE_OUTCOME":
                proposals.append(LeakagePatchProposal(
                    episode_id=critique.episode_id,
                    leakage_type=finding.leakage_type,
                    proposed_fix=f"Remove field '{finding.evidence.get('field')}' from pre-state",
                    rationale="Outcome information must not appear in pre-state",
                ))
            
            elif finding.leakage_type == "FUTURE_MARKET":
                proposals.append(LeakagePatchProposal(
                    episode_id=critique.episode_id,
                    leakage_type=finding.leakage_type,
                    proposed_fix=f"Filter market snapshots to only include timestamps <= decision_time",
                    rationale="Market data after decision time is future information",
                ))
            
            elif finding.leakage_type == "TIMESTAMP_VIOLATION":
                proposals.append(LeakagePatchProposal(
                    episode_id=critique.episode_id,
                    leakage_type=finding.leakage_type,
                    proposed_fix=f"Filter data to only include timestamps <= decision_time",
                    rationale="Data timestamps after decision time indicate temporal leakage",
                ))
            
            elif finding.leakage_type == "LOOKAHEAD_BIAS":
                proposals.append(LeakagePatchProposal(
                    episode_id=critique.episode_id,
                    leakage_type=finding.leakage_type,
                    proposed_fix=f"Rename or remove feature '{finding.evidence.get('feature_name')}'",
                    rationale="Feature name suggests future knowledge",
                ))
        
        return proposals


__all__ = [
    "LeakageFinding",
    "LeakageCritique",
    "LeakagePatchProposal",
    "LeakageDetectorCritic",
]
