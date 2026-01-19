"""
VÉLØ V13 - Episode Schema

Defines the episodic memory data model with epistemic time separation.

Key Concepts:
- Episode: A deterministic snapshot of a race analysis decision
- decisionTime: When the decision was made (epistemic time)
- createdAt: When the artifact was written (execution time)
- Artifact: Sparse storage of episode state (PRE_STATE, INFERENCE, OUTCOME, etc.)

Author: VÉLØ Team
Date: 2026-01-19
Status: LOCKED
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ArtifactType(str, Enum):
    """Types of episode artifacts for sparse storage."""
    PRE_STATE = "PRE_STATE"  # Input state before decision
    INFERENCE = "INFERENCE"  # Model inference results
    OUTCOME = "OUTCOME"  # Actual race outcome
    CRITIQUE = "CRITIQUE"  # Post-hoc critic findings
    PATCH = "PATCH"  # Proposed corrections


class EpisodeStatus(str, Enum):
    """Episode lifecycle status."""
    PENDING = "PENDING"  # Created, awaiting outcome
    COMPLETE = "COMPLETE"  # Outcome recorded
    VALIDATED = "VALIDATED"  # Replay integrity confirmed


@dataclass
class Episode:
    """
    Deterministic snapshot of a race analysis decision.
    
    Attributes:
        id: Deterministic ID (SHA256 of race_id + engine_version + timestamp_bucket)
        race_id: External race identifier
        decision_time: When the decision was made (EPISTEMIC TIME)
        created_at: When the artifact was written (EXECUTION TIME)
        engine_version: Code version that produced this episode
        context_hash: Hash of input context for replay validation
        replay_hash: Hash of all artifact checksums (for integrity)
        status: Episode lifecycle status
        regime: Optional regime classification (e.g., "CHAOS", "COMPRESSION")
    """
    id: str
    race_id: str
    decision_time: datetime  # EPISTEMIC TIME - when decision was made
    created_at: datetime  # EXECUTION TIME - when artifact was written
    engine_version: str
    context_hash: str
    replay_hash: Optional[str]
    status: EpisodeStatus
    regime: Optional[str]


@dataclass
class EpisodeArtifact:
    """
    Sparse storage of episode state.
    
    Attributes:
        id: Unique artifact ID
        episode_id: Parent episode ID
        artifact_type: Type of artifact (PRE_STATE, INFERENCE, etc.)
        payload: JSON payload (compressed if large)
        checksum: SHA256 of payload for integrity
        created_at: When artifact was written
        sequence: Ordering within episode (for deterministic replay)
    """
    id: str
    episode_id: str
    artifact_type: ArtifactType
    payload: dict  # JSON payload
    checksum: str  # SHA256 of payload
    created_at: datetime
    sequence: int


@dataclass
class MemoryIndex:
    """
    Fast retrieval index for episode artifacts (Engram-style).
    
    Attributes:
        id: Unique index ID
        episode_id: Parent episode ID
        context_key: Searchable context key (e.g., "track:ascot", "chaos:high")
        artifact_id: Referenced artifact ID
        relevance_score: Optional relevance score for ranking
        created_at: When index entry was created
    """
    id: str
    episode_id: str
    context_key: str
    artifact_id: str
    relevance_score: Optional[float]
    created_at: datetime


@dataclass
class LearningEvent:
    """
    Post-race delta (false anchors, missed releases, etc.).
    
    Attributes:
        id: Unique event ID
        episode_id: Parent episode ID
        event_type: Type of learning event (e.g., "FALSE_ANCHOR", "MISSED_RELEASE")
        description: Human-readable description
        evidence: JSON evidence from episode artifacts
        severity: Severity level (INFO, WARNING, CRITICAL)
        created_at: When event was detected
    """
    id: str
    episode_id: str
    event_type: str
    description: str
    evidence: dict  # JSON evidence
    severity: str  # INFO, WARNING, CRITICAL
    created_at: datetime


# =============================================================================
# DOCTRINE ENFORCEMENT
# =============================================================================

def validate_epistemic_time_separation(
    episode: Episode,
    artifact: EpisodeArtifact
) -> tuple[bool, Optional[str]]:
    """
    Validate that epistemic time (decisionTime) is separated from execution time (createdAt).
    
    Args:
        episode: Episode to validate
        artifact: Artifact to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        
    Doctrine: DOCTRINE_EPISTEMIC_TIME
    """
    # decisionTime must be before or equal to createdAt
    if episode.decision_time > episode.created_at:
        return False, f"decisionTime ({episode.decision_time}) is after createdAt ({episode.created_at})"
    
    # Artifact createdAt must be after episode decisionTime
    if artifact.created_at < episode.decision_time:
        return False, f"Artifact createdAt ({artifact.created_at}) is before episode decisionTime ({episode.decision_time})"
    
    return True, None


def validate_deterministic_id(
    race_id: str,
    engine_version: str,
    timestamp_bucket: str,
    expected_id: str
) -> bool:
    """
    Validate that episode ID is deterministic.
    
    Args:
        race_id: External race identifier
        engine_version: Code version
        timestamp_bucket: Timestamp bucket (e.g., "2026-01-19T12:00:00Z")
        expected_id: Expected deterministic ID
        
    Returns:
        True if ID is deterministic, False otherwise
        
    Doctrine: DOCTRINE_REPLAY_INTEGRITY
    """
    import hashlib
    
    # Compute deterministic ID
    id_input = f"{race_id}:{engine_version}:{timestamp_bucket}"
    computed_id = hashlib.sha256(id_input.encode()).hexdigest()
    
    return computed_id == expected_id


__all__ = [
    "ArtifactType",
    "EpisodeStatus",
    "Episode",
    "EpisodeArtifact",
    "MemoryIndex",
    "LearningEvent",
    "validate_epistemic_time_separation",
    "validate_deterministic_id",
]
