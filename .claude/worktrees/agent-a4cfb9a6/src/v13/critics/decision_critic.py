"""
VÉLØ V13 - Decision Critic

Post-hoc audit of decision rationale (incoherence, narrative drift, rule violations, overreach).

Detection Capabilities:
- Incoherence (decision contradicts internal signals)
- Narrative drift (rationale mentions non-existent features or outcome terms)
- Rule violations (STRIKE in chaos, low confidence STRIKE, missing rationale)
- Overreach (overconfidence, insufficient signal support)
- Missing rationale (no explanation provided)
- Confidence mismatch (stated confidence doesn't match score distribution)

Author: VÉLØ Team
Date: 2026-01-19
Status: LOCKED
Doctrine: DOCTRINE_CRITIC_AUTHORITY
"""

from dataclasses import dataclass
from typing import Any

from ..doctrine import enforce_read_only, enforce_episode_bound
from ..episodes.schema import Episode, EpisodeArtifact, ArtifactType


@dataclass
class DecisionFinding:
    """A single decision rationale finding."""
    finding_type: str  # INCOHERENCE, NARRATIVE_DRIFT, RULE_VIOLATION, etc.
    description: str
    evidence: dict[str, Any]  # Episode artifact citations
    severity: str  # INFO, WARNING, CRITICAL


@dataclass
class DecisionCritique:
    """Result of decision rationale critique."""
    episode_id: str
    findings: list[DecisionFinding]
    is_coherent: bool
    total_issues: int


@dataclass
class DecisionPatchProposal:
    """Proposed patch to fix decision issues."""
    episode_id: str
    finding_type: str
    proposed_fix: str
    rationale: str


class DecisionCritic:
    """
    Read-only critic that audits decision rationale.
    
    Doctrine:
    - Read-only (no state mutation)
    - Episode-bound (all findings cite artifacts)
    - No auto-apply (emits proposals only)
    - Post-hoc audit only (never intervenes)
    - Zero action authority
    """
    
    @enforce_read_only
    @enforce_episode_bound
    def critique(
        self,
        episode: Episode,
        artifacts: list[EpisodeArtifact],
    ) -> DecisionCritique:
        """
        Audit decision rationale in episode artifacts.
        
        Args:
            episode: Episode to critique
            artifacts: All artifacts for this episode
            
        Returns:
            DecisionCritique with findings
            
        Doctrine: DOCTRINE_CRITIC_AUTHORITY
        """
        findings: list[DecisionFinding] = []
        
        # Get PRE_STATE and INFERENCE artifacts
        pre_state_artifact = next(
            (a for a in artifacts if a.artifact_type == ArtifactType.PRE_STATE),
            None
        )
        inference_artifact = next(
            (a for a in artifacts if a.artifact_type == ArtifactType.INFERENCE),
            None
        )
        
        if not pre_state_artifact or not inference_artifact:
            return DecisionCritique(
                episode_id=episode.id,
                findings=[],
                is_coherent=True,
                total_issues=0,
            )
        
        pre_state = pre_state_artifact.payload
        inference = inference_artifact.payload
        
        # Check for incoherence
        findings.extend(self._detect_incoherence(
            episode, pre_state_artifact, inference_artifact, pre_state, inference
        ))
        
        # Check for narrative drift
        findings.extend(self._detect_narrative_drift(
            episode, pre_state_artifact, inference_artifact, pre_state, inference
        ))
        
        # Check for rule violations
        findings.extend(self._detect_rule_violations(
            episode, pre_state_artifact, inference_artifact, pre_state, inference
        ))
        
        # Check for overreach
        findings.extend(self._detect_overreach(
            episode, pre_state_artifact, inference_artifact, pre_state, inference
        ))
        
        # Check for missing rationale
        findings.extend(self._detect_missing_rationale(
            episode, inference_artifact, inference
        ))
        
        # Check for confidence mismatch
        findings.extend(self._detect_confidence_mismatch(
            episode, inference_artifact, inference
        ))
        
        return DecisionCritique(
            episode_id=episode.id,
            findings=findings,
            is_coherent=len([f for f in findings if f.severity == "CRITICAL"]) == 0,
            total_issues=len(findings),
        )
    
    def _detect_incoherence(
        self,
        episode: Episode,
        pre_state_artifact: EpisodeArtifact,
        inference_artifact: EpisodeArtifact,
        pre_state: dict[str, Any],
        inference: dict[str, Any],
    ) -> list[DecisionFinding]:
        """Detect decision contradicting internal signals."""
        findings = []
        
        # Check if STRIKE decision contradicts internal signals
        if inference.get("verdict") == "STRIKE":
            internal_signals = inference.get("internal_signals", {})
            
            # Check for chaos warning
            if internal_signals.get("chaos_warning") == True:
                findings.append(DecisionFinding(
                    finding_type="INCOHERENCE",
                    description="STRIKE decision despite chaos warning",
                    evidence={
                        "pre_state_artifact_id": pre_state_artifact.id,
                        "inference_artifact_id": inference_artifact.id,
                        "verdict": "STRIKE",
                        "chaos_warning": True,
                    },
                    severity="WARNING",
                ))
            
            # Check for leakage detected
            if internal_signals.get("leakage_detected") == True:
                findings.append(DecisionFinding(
                    finding_type="INCOHERENCE",
                    description="STRIKE decision despite leakage detection",
                    evidence={
                        "pre_state_artifact_id": pre_state_artifact.id,
                        "inference_artifact_id": inference_artifact.id,
                        "verdict": "STRIKE",
                        "leakage_detected": True,
                    },
                    severity="CRITICAL",
                ))
        
        return findings
    
    def _detect_narrative_drift(
        self,
        episode: Episode,
        pre_state_artifact: EpisodeArtifact,
        inference_artifact: EpisodeArtifact,
        pre_state: dict[str, Any],
        inference: dict[str, Any],
    ) -> list[DecisionFinding]:
        """Detect rationale mentioning non-existent features or outcome terms."""
        findings = []
        
        if "rationale" not in inference:
            return findings
        
        rationale = inference["rationale"].lower()
        features = pre_state.get("features", {})
        
        # Check for outcome terms in rationale
        outcome_terms = ["winner", "result", "finishing position", "actual time", "isp"]
        for term in outcome_terms:
            if term in rationale:
                findings.append(DecisionFinding(
                    finding_type="NARRATIVE_DRIFT",
                    description=f"Rationale mentions outcome term '{term}'",
                    evidence={
                        "inference_artifact_id": inference_artifact.id,
                        "outcome_term": term,
                    },
                    severity="WARNING",
                ))
        
        # Check for non-existent features mentioned in rationale
        # (This is a simplified check - in production, use NER or feature extraction)
        feature_names = set(features.keys())
        mentioned_features = [word for word in rationale.split() if word in feature_names]
        
        if len(mentioned_features) == 0 and len(features) > 0:
            findings.append(DecisionFinding(
                finding_type="NARRATIVE_DRIFT",
                description="Rationale does not reference any actual features",
                evidence={
                    "inference_artifact_id": inference_artifact.id,
                    "total_features": len(features),
                    "mentioned_features": 0,
                },
                severity="INFO",
            ))
        
        return findings
    
    def _detect_rule_violations(
        self,
        episode: Episode,
        pre_state_artifact: EpisodeArtifact,
        inference_artifact: EpisodeArtifact,
        pre_state: dict[str, Any],
        inference: dict[str, Any],
    ) -> list[DecisionFinding]:
        """Detect rule violations (STRIKE in chaos, low confidence STRIKE, etc.)."""
        findings = []
        
        verdict = inference.get("verdict")
        confidence = inference.get("confidence", 0)
        chaos_level = pre_state.get("chaos_level", 0)
        
        # Rule: No STRIKE in high chaos
        if verdict == "STRIKE" and chaos_level > 0.7:
            findings.append(DecisionFinding(
                finding_type="RULE_VIOLATION",
                description=f"STRIKE decision in high chaos environment (chaos_level={chaos_level:.2f})",
                evidence={
                    "pre_state_artifact_id": pre_state_artifact.id,
                    "inference_artifact_id": inference_artifact.id,
                    "verdict": "STRIKE",
                    "chaos_level": chaos_level,
                },
                severity="CRITICAL",
            ))
        
        # Rule: No STRIKE with low confidence
        if verdict == "STRIKE" and confidence < 0.6:
            findings.append(DecisionFinding(
                finding_type="RULE_VIOLATION",
                description=f"STRIKE decision with low confidence ({confidence:.2f})",
                evidence={
                    "inference_artifact_id": inference_artifact.id,
                    "verdict": "STRIKE",
                    "confidence": confidence,
                },
                severity="CRITICAL",
            ))
        
        return findings
    
    def _detect_overreach(
        self,
        episode: Episode,
        pre_state_artifact: EpisodeArtifact,
        inference_artifact: EpisodeArtifact,
        pre_state: dict[str, Any],
        inference: dict[str, Any],
    ) -> list[DecisionFinding]:
        """Detect overconfidence or insufficient signal support."""
        findings = []
        
        confidence = inference.get("confidence", 0)
        signal_strength = inference.get("signal_strength", 0)
        
        # Check for overconfidence (>0.95)
        if confidence > 0.95:
            findings.append(DecisionFinding(
                finding_type="OVERREACH",
                description=f"Overconfidence detected ({confidence:.2f})",
                evidence={
                    "inference_artifact_id": inference_artifact.id,
                    "confidence": confidence,
                },
                severity="WARNING",
            ))
        
        # Check for insufficient signal support
        if confidence > 0.8 and signal_strength < 0.5:
            findings.append(DecisionFinding(
                finding_type="OVERREACH",
                description=f"High confidence ({confidence:.2f}) with low signal ({signal_strength:.2f})",
                evidence={
                    "inference_artifact_id": inference_artifact.id,
                    "confidence": confidence,
                    "signal_strength": signal_strength,
                },
                severity="WARNING",
            ))
        
        return findings
    
    def _detect_missing_rationale(
        self,
        episode: Episode,
        inference_artifact: EpisodeArtifact,
        inference: dict[str, Any],
    ) -> list[DecisionFinding]:
        """Detect missing rationale."""
        findings = []
        
        if "rationale" not in inference or not inference["rationale"]:
            findings.append(DecisionFinding(
                finding_type="MISSING_RATIONALE",
                description="No rationale provided for decision",
                evidence={
                    "inference_artifact_id": inference_artifact.id,
                },
                severity="CRITICAL",
            ))
        
        return findings
    
    def _detect_confidence_mismatch(
        self,
        episode: Episode,
        inference_artifact: EpisodeArtifact,
        inference: dict[str, Any],
    ) -> list[DecisionFinding]:
        """Detect stated confidence not matching score distribution."""
        findings = []
        
        confidence = inference.get("confidence", 0)
        predictions = inference.get("predictions", [])
        
        if len(predictions) >= 2:
            # Calculate score spread (top score - second score)
            top_score = predictions[0].get("score", 0)
            second_score = predictions[1].get("score", 0)
            score_spread = top_score - second_score
            
            # High confidence should have high score spread
            if confidence > 0.8 and score_spread < 0.1:
                findings.append(DecisionFinding(
                    finding_type="CONFIDENCE_MISMATCH",
                    description=f"High confidence ({confidence:.2f}) but low score spread ({score_spread:.2f})",
                    evidence={
                        "inference_artifact_id": inference_artifact.id,
                        "confidence": confidence,
                        "score_spread": score_spread,
                    },
                    severity="WARNING",
                ))
        
        return findings
    
    def propose_patch(
        self,
        critique: DecisionCritique,
    ) -> list[DecisionPatchProposal]:
        """
        Propose patches to fix decision issues.
        
        Args:
            critique: Decision critique with findings
            
        Returns:
            List of patch proposals
            
        Doctrine: DOCTRINE_CRITIC_AUTHORITY (no auto-apply)
        """
        proposals = []
        
        for finding in critique.findings:
            if finding.finding_type == "INCOHERENCE":
                proposals.append(DecisionPatchProposal(
                    episode_id=critique.episode_id,
                    finding_type=finding.finding_type,
                    proposed_fix="Revise decision to align with internal signals",
                    rationale="Incoherent decisions undermine system trust",
                ))
            
            elif finding.finding_type == "NARRATIVE_DRIFT":
                proposals.append(DecisionPatchProposal(
                    episode_id=critique.episode_id,
                    finding_type=finding.finding_type,
                    proposed_fix="Rewrite rationale to reference actual features only",
                    rationale="Narrative drift creates false explanations",
                ))
            
            elif finding.finding_type == "RULE_VIOLATION":
                proposals.append(DecisionPatchProposal(
                    episode_id=critique.episode_id,
                    finding_type=finding.finding_type,
                    proposed_fix="Change verdict to comply with doctrine rules",
                    rationale="Rule violations compromise system integrity",
                ))
            
            elif finding.finding_type == "OVERREACH":
                proposals.append(DecisionPatchProposal(
                    episode_id=critique.episode_id,
                    finding_type=finding.finding_type,
                    proposed_fix="Calibrate confidence to match signal strength",
                    rationale="Overreach leads to unjustified risk-taking",
                ))
            
            elif finding.finding_type == "MISSING_RATIONALE":
                proposals.append(DecisionPatchProposal(
                    episode_id=critique.episode_id,
                    finding_type=finding.finding_type,
                    proposed_fix="Add rationale explaining decision logic",
                    rationale="Missing rationale makes decisions unauditable",
                ))
            
            elif finding.finding_type == "CONFIDENCE_MISMATCH":
                proposals.append(DecisionPatchProposal(
                    episode_id=critique.episode_id,
                    finding_type=finding.finding_type,
                    proposed_fix="Adjust confidence to match score distribution",
                    rationale="Confidence mismatch creates false certainty",
                ))
        
        return proposals


__all__ = [
    "DecisionFinding",
    "DecisionCritique",
    "DecisionPatchProposal",
    "DecisionCritic",
]
