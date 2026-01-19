"""
VÉLØ V13 - Episode Constructor

Converts engine runs into deterministic episodes with replay integrity.

Key Functions:
- build_episode: Create episode from engine run
- write_episode_artifacts: Persist PRE_STATE, INFERENCE, OUTCOME artifacts
- finalize_episode: Update episode with race outcome
- replay_episode: Generate deterministic replay hash
- validate_episode_integrity: Validate checksums + replay stability

Author: VÉLØ Team
Date: 2026-01-19
Status: LOCKED
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Optional

from .schema import (
    Episode,
    EpisodeArtifact,
    EpisodeStatus,
    ArtifactType,
    validate_epistemic_time_separation,
    validate_deterministic_id,
)


def build_episode(
    race_id: str,
    engine_version: str,
    decision_time: datetime,
    context: dict[str, Any],
) -> Episode:
    """
    Create a deterministic episode from engine run.
    
    Args:
        race_id: External race identifier
        engine_version: Code version that produced this episode
        decision_time: When the decision was made (EPISTEMIC TIME)
        context: Input context for replay validation
        
    Returns:
        Episode with deterministic ID
        
    Doctrine: DOCTRINE_REPLAY_INTEGRITY, DOCTRINE_EPISTEMIC_TIME
    """
    # Bucket timestamp to nearest hour for deterministic ID
    timestamp_bucket = decision_time.replace(minute=0, second=0, microsecond=0).isoformat()
    
    # Generate deterministic episode ID
    id_input = f"{race_id}:{engine_version}:{timestamp_bucket}"
    episode_id = hashlib.sha256(id_input.encode()).hexdigest()
    
    # Generate context hash for replay validation
    context_json = json.dumps(context, sort_keys=True)
    context_hash = hashlib.sha256(context_json.encode()).hexdigest()
    
    return Episode(
        id=episode_id,
        race_id=race_id,
        decision_time=decision_time,  # EPISTEMIC TIME
        created_at=datetime.utcnow(),  # EXECUTION TIME
        engine_version=engine_version,
        context_hash=context_hash,
        replay_hash=None,  # Computed after artifacts are written
        status=EpisodeStatus.PENDING,
        regime=None,  # Optional regime classification
    )


def write_episode_artifacts(
    episode_id: str,
    pre_state: dict[str, Any],
    inference: dict[str, Any],
    outcome: Optional[dict[str, Any]] = None,
) -> list[EpisodeArtifact]:
    """
    Write episode artifacts (PRE_STATE, INFERENCE, OUTCOME).
    
    Args:
        episode_id: Parent episode ID
        pre_state: Input state before decision
        inference: Model inference results
        outcome: Actual race outcome (optional, added later)
        
    Returns:
        List of artifacts with checksums
        
    Doctrine: DOCTRINE_REPLAY_INTEGRITY
    """
    artifacts = []
    
    # PRE_STATE artifact
    pre_state_json = json.dumps(pre_state, sort_keys=True)
    pre_state_checksum = hashlib.sha256(pre_state_json.encode()).hexdigest()
    artifacts.append(EpisodeArtifact(
        id=f"{episode_id}:pre_state",
        episode_id=episode_id,
        artifact_type=ArtifactType.PRE_STATE,
        payload=pre_state,
        checksum=pre_state_checksum,
        created_at=datetime.utcnow(),
        sequence=1,
    ))
    
    # INFERENCE artifact
    inference_json = json.dumps(inference, sort_keys=True)
    inference_checksum = hashlib.sha256(inference_json.encode()).hexdigest()
    artifacts.append(EpisodeArtifact(
        id=f"{episode_id}:inference",
        episode_id=episode_id,
        artifact_type=ArtifactType.INFERENCE,
        payload=inference,
        checksum=inference_checksum,
        created_at=datetime.utcnow(),
        sequence=2,
    ))
    
    # OUTCOME artifact (if provided)
    if outcome:
        outcome_json = json.dumps(outcome, sort_keys=True)
        outcome_checksum = hashlib.sha256(outcome_json.encode()).hexdigest()
        artifacts.append(EpisodeArtifact(
            id=f"{episode_id}:outcome",
            episode_id=episode_id,
            artifact_type=ArtifactType.OUTCOME,
            payload=outcome,
            checksum=outcome_checksum,
            created_at=datetime.utcnow(),
            sequence=3,
        ))
    
    return artifacts


def finalize_episode(
    episode: Episode,
    outcome: dict[str, Any],
) -> tuple[Episode, EpisodeArtifact]:
    """
    Update episode with race outcome and mark as COMPLETE.
    
    Args:
        episode: Episode to finalize
        outcome: Actual race outcome
        
    Returns:
        Tuple of (updated_episode, outcome_artifact)
        
    Doctrine: DOCTRINE_REPLAY_INTEGRITY
    """
    # Create OUTCOME artifact
    outcome_json = json.dumps(outcome, sort_keys=True)
    outcome_checksum = hashlib.sha256(outcome_json.encode()).hexdigest()
    outcome_artifact = EpisodeArtifact(
        id=f"{episode.id}:outcome",
        episode_id=episode.id,
        artifact_type=ArtifactType.OUTCOME,
        payload=outcome,
        checksum=outcome_checksum,
        created_at=datetime.utcnow(),
        sequence=3,
    )
    
    # Update episode status
    episode.status = EpisodeStatus.COMPLETE
    
    return episode, outcome_artifact


def replay_episode(
    episode: Episode,
    artifacts: list[EpisodeArtifact],
) -> str:
    """
    Generate deterministic replay hash from episode artifacts.
    
    Args:
        episode: Episode to replay
        artifacts: All artifacts for this episode
        
    Returns:
        Replay hash (SHA256 of concatenated checksums)
        
    Doctrine: DOCTRINE_REPLAY_INTEGRITY
    """
    # Sort artifacts by sequence for deterministic ordering
    sorted_artifacts = sorted(artifacts, key=lambda a: a.sequence)
    
    # Concatenate checksums
    checksums = [a.checksum for a in sorted_artifacts]
    checksums_str = ":".join(checksums)
    
    # Generate replay hash
    replay_hash = hashlib.sha256(checksums_str.encode()).hexdigest()
    
    return replay_hash


def validate_episode_integrity(
    episode: Episode,
    artifacts: list[EpisodeArtifact],
) -> tuple[bool, list[str]]:
    """
    Validate episode integrity (checksums + replay stability).
    
    Args:
        episode: Episode to validate
        artifacts: All artifacts for this episode
        
    Returns:
        Tuple of (is_valid, violations)
        
    Doctrine: DOCTRINE_REPLAY_INTEGRITY, DOCTRINE_EPISTEMIC_TIME
    """
    violations = []
    
    # Validate epistemic time separation for each artifact
    for artifact in artifacts:
        is_valid, error = validate_epistemic_time_separation(episode, artifact)
        if not is_valid:
            violations.append(f"Epistemic time violation: {error}")
    
    # Validate deterministic ID
    timestamp_bucket = episode.decision_time.replace(minute=0, second=0, microsecond=0).isoformat()
    if not validate_deterministic_id(
        episode.race_id,
        episode.engine_version,
        timestamp_bucket,
        episode.id
    ):
        violations.append(f"Episode ID is not deterministic: {episode.id}")
    
    # Validate artifact checksums
    for artifact in artifacts:
        payload_json = json.dumps(artifact.payload, sort_keys=True)
        computed_checksum = hashlib.sha256(payload_json.encode()).hexdigest()
        if computed_checksum != artifact.checksum:
            violations.append(
                f"Artifact checksum mismatch: {artifact.id} "
                f"(expected {artifact.checksum}, got {computed_checksum})"
            )
    
    # Validate replay hash
    if episode.replay_hash:
        computed_replay_hash = replay_episode(episode, artifacts)
        if computed_replay_hash != episode.replay_hash:
            violations.append(
                f"Replay hash mismatch: "
                f"(expected {episode.replay_hash}, got {computed_replay_hash})"
            )
    
    return len(violations) == 0, violations


__all__ = [
    "build_episode",
    "write_episode_artifacts",
    "finalize_episode",
    "replay_episode",
    "validate_episode_integrity",
]
