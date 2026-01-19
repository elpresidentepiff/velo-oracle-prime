"""
VÉLØ V13 - Feature Extractor Critic

Analyzes feature quality and detects issues (missing, redundant, leaked, invalid).

Detection Capabilities:
- Missing critical features (chaos_level, compression, field_size, etc.)
- Redundant features (exact duplicates, high correlation)
- Feature leakage (outcome information, future timestamps)
- Invalid values (NaN, Infinity, out-of-range)

Author: VÉLØ Team
Date: 2026-01-19
Status: LOCKED
Doctrine: DOCTRINE_CRITIC_AUTHORITY, DOCTRINE_FEATURE_FIREWALL
"""

from dataclasses import dataclass
import math
from typing import Any

from ..doctrine import enforce_read_only, enforce_episode_bound
from ..episodes.schema import Episode, EpisodeArtifact, ArtifactType


@dataclass
class FeatureFinding:
    """A single feature quality finding."""
    finding_type: str  # MISSING, REDUNDANT, LEAKED, INVALID
    description: str
    evidence: dict[str, Any]  # Episode artifact citations
    severity: str  # INFO, WARNING, CRITICAL


@dataclass
class FeatureCritique:
    """Result of feature quality critique."""
    episode_id: str
    findings: list[FeatureFinding]
    is_clean: bool
    total_features: int
    missing_features: int
    redundant_features: int
    leaked_features: int
    invalid_features: int


@dataclass
class FeaturePatchProposal:
    """Proposed patch to fix feature issues."""
    episode_id: str
    finding_type: str
    proposed_fix: str
    rationale: str


class FeatureExtractorCritic:
    """
    Read-only critic that analyzes feature quality.
    
    Doctrine:
    - Read-only (no state mutation)
    - Episode-bound (all findings cite artifacts)
    - No auto-apply (emits proposals only)
    - Anchored to decisionTime (for leakage detection)
    - DOCTRINE_FEATURE_FIREWALL: No feature enters model without passing
    """
    
    # Critical features that must be present
    CRITICAL_FEATURES = [
        "chaos_level",
        "compression",
        "field_size",
        "distance_yards",
        "going",
    ]
    
    # Outcome features that indicate leakage
    OUTCOME_FEATURES = [
        "isp", "finishing_position", "winner", "result", "actual_time"
    ]
    
    @enforce_read_only
    @enforce_episode_bound
    def critique(
        self,
        episode: Episode,
        artifacts: list[EpisodeArtifact],
    ) -> FeatureCritique:
        """
        Analyze feature quality in episode artifacts.
        
        Args:
            episode: Episode to critique
            artifacts: All artifacts for this episode
            
        Returns:
            FeatureCritique with findings
            
        Doctrine: DOCTRINE_CRITIC_AUTHORITY, DOCTRINE_FEATURE_FIREWALL
        """
        findings: list[FeatureFinding] = []
        
        # Get PRE_STATE artifact
        pre_state_artifact = next(
            (a for a in artifacts if a.artifact_type == ArtifactType.PRE_STATE),
            None
        )
        
        if not pre_state_artifact:
            return FeatureCritique(
                episode_id=episode.id,
                findings=[],
                is_clean=True,
                total_features=0,
                missing_features=0,
                redundant_features=0,
                leaked_features=0,
                invalid_features=0,
            )
        
        pre_state = pre_state_artifact.payload
        features = pre_state.get("features", {})
        
        # Check for missing critical features
        missing_findings = self._detect_missing_features(
            episode, pre_state_artifact, features
        )
        findings.extend(missing_findings)
        
        # Check for redundant features
        redundant_findings = self._detect_redundant_features(
            episode, pre_state_artifact, features
        )
        findings.extend(redundant_findings)
        
        # Check for feature leakage
        leaked_findings = self._detect_feature_leakage(
            episode, pre_state_artifact, features
        )
        findings.extend(leaked_findings)
        
        # Check for invalid values
        invalid_findings = self._detect_invalid_values(
            episode, pre_state_artifact, features
        )
        findings.extend(invalid_findings)
        
        return FeatureCritique(
            episode_id=episode.id,
            findings=findings,
            is_clean=len([f for f in findings if f.severity == "CRITICAL"]) == 0,
            total_features=len(features),
            missing_features=len(missing_findings),
            redundant_features=len(redundant_findings),
            leaked_features=len(leaked_findings),
            invalid_features=len(invalid_findings),
        )
    
    def _detect_missing_features(
        self,
        episode: Episode,
        artifact: EpisodeArtifact,
        features: dict[str, Any],
    ) -> list[FeatureFinding]:
        """Detect missing critical features."""
        findings = []
        
        for critical_feature in self.CRITICAL_FEATURES:
            if critical_feature not in features:
                findings.append(FeatureFinding(
                    finding_type="MISSING",
                    description=f"Critical feature '{critical_feature}' is missing",
                    evidence={
                        "artifact_id": artifact.id,
                        "missing_feature": critical_feature,
                    },
                    severity="CRITICAL",
                ))
        
        return findings
    
    def _detect_redundant_features(
        self,
        episode: Episode,
        artifact: EpisodeArtifact,
        features: dict[str, Any],
    ) -> list[FeatureFinding]:
        """Detect redundant features (exact duplicates)."""
        findings = []
        
        # Check for exact duplicate values
        value_to_features: dict[Any, list[str]] = {}
        
        for feature_name, feature_value in features.items():
            # Skip non-numeric features
            if not isinstance(feature_value, (int, float)):
                continue
            
            # Group features by value
            if feature_value not in value_to_features:
                value_to_features[feature_value] = []
            value_to_features[feature_value].append(feature_name)
        
        # Report duplicates
        for value, feature_names in value_to_features.items():
            if len(feature_names) > 1:
                findings.append(FeatureFinding(
                    finding_type="REDUNDANT",
                    description=f"Features {feature_names} have identical values ({value})",
                    evidence={
                        "artifact_id": artifact.id,
                        "redundant_features": feature_names,
                        "value": value,
                    },
                    severity="WARNING",
                ))
        
        return findings
    
    def _detect_feature_leakage(
        self,
        episode: Episode,
        artifact: EpisodeArtifact,
        features: dict[str, Any],
    ) -> list[FeatureFinding]:
        """Detect outcome information in features."""
        findings = []
        
        # Check for outcome features
        for outcome_feature in self.OUTCOME_FEATURES:
            if outcome_feature in features:
                findings.append(FeatureFinding(
                    finding_type="LEAKED",
                    description=f"Outcome feature '{outcome_feature}' found in features",
                    evidence={
                        "artifact_id": artifact.id,
                        "leaked_feature": outcome_feature,
                        "value": features[outcome_feature],
                    },
                    severity="CRITICAL",
                ))
        
        # Check for features with "outcome" or "result" in name
        for feature_name in features.keys():
            if any(word in feature_name.lower() for word in ["outcome", "result", "winner", "final"]):
                findings.append(FeatureFinding(
                    finding_type="LEAKED",
                    description=f"Feature name '{feature_name}' suggests outcome information",
                    evidence={
                        "artifact_id": artifact.id,
                        "leaked_feature": feature_name,
                    },
                    severity="WARNING",
                ))
        
        return findings
    
    def _detect_invalid_values(
        self,
        episode: Episode,
        artifact: EpisodeArtifact,
        features: dict[str, Any],
    ) -> list[FeatureFinding]:
        """Detect invalid feature values (NaN, Infinity, out-of-range)."""
        findings = []
        
        for feature_name, feature_value in features.items():
            # Skip non-numeric features
            if not isinstance(feature_value, (int, float)):
                continue
            
            # Check for NaN
            if math.isnan(feature_value):
                findings.append(FeatureFinding(
                    finding_type="INVALID",
                    description=f"Feature '{feature_name}' has NaN value",
                    evidence={
                        "artifact_id": artifact.id,
                        "invalid_feature": feature_name,
                        "value": "NaN",
                    },
                    severity="CRITICAL",
                ))
            
            # Check for Infinity
            elif math.isinf(feature_value):
                findings.append(FeatureFinding(
                    finding_type="INVALID",
                    description=f"Feature '{feature_name}' has Infinity value",
                    evidence={
                        "artifact_id": artifact.id,
                        "invalid_feature": feature_name,
                        "value": "Infinity",
                    },
                    severity="CRITICAL",
                ))
            
            # Check for out-of-range values (probabilities should be [0, 1])
            elif "probability" in feature_name.lower() or "confidence" in feature_name.lower():
                if feature_value < 0 or feature_value > 1:
                    findings.append(FeatureFinding(
                        finding_type="INVALID",
                        description=f"Probability feature '{feature_name}' is out of range [0, 1]: {feature_value}",
                        evidence={
                            "artifact_id": artifact.id,
                            "invalid_feature": feature_name,
                            "value": feature_value,
                        },
                        severity="WARNING",
                    ))
        
        return findings
    
    def propose_patch(
        self,
        critique: FeatureCritique,
    ) -> list[FeaturePatchProposal]:
        """
        Propose patches to fix feature issues.
        
        Args:
            critique: Feature critique with findings
            
        Returns:
            List of patch proposals
            
        Doctrine: DOCTRINE_CRITIC_AUTHORITY (no auto-apply)
        """
        proposals = []
        
        for finding in critique.findings:
            if finding.finding_type == "MISSING":
                proposals.append(FeaturePatchProposal(
                    episode_id=critique.episode_id,
                    finding_type=finding.finding_type,
                    proposed_fix=f"Add missing critical feature '{finding.evidence.get('missing_feature')}'",
                    rationale="Critical features are required for model integrity",
                ))
            
            elif finding.finding_type == "REDUNDANT":
                proposals.append(FeaturePatchProposal(
                    episode_id=critique.episode_id,
                    finding_type=finding.finding_type,
                    proposed_fix=f"Remove redundant features: {finding.evidence.get('redundant_features')}",
                    rationale="Redundant features add noise without information",
                ))
            
            elif finding.finding_type == "LEAKED":
                proposals.append(FeaturePatchProposal(
                    episode_id=critique.episode_id,
                    finding_type=finding.finding_type,
                    proposed_fix=f"Remove leaked feature '{finding.evidence.get('leaked_feature')}'",
                    rationale="Outcome information must not appear in features",
                ))
            
            elif finding.finding_type == "INVALID":
                proposals.append(FeaturePatchProposal(
                    episode_id=critique.episode_id,
                    finding_type=finding.finding_type,
                    proposed_fix=f"Fix invalid value in feature '{finding.evidence.get('invalid_feature')}'",
                    rationale="Invalid values (NaN, Infinity, out-of-range) corrupt model",
                ))
        
        return proposals


__all__ = [
    "FeatureFinding",
    "FeatureCritique",
    "FeaturePatchProposal",
    "FeatureExtractorCritic",
]
