"""
VÉLØ V13 - Cognitive Bias Critic

Detects cognitive biases in decision-making without agency.

Bias Types:
- Anchoring bias (over-reliance on first information)
- Confirmation bias (seeking confirming evidence)
- Recency bias (over-weighting recent events)
- Overconfidence (unjustified high confidence)
- Herd mentality (following market consensus)
- Gambler's fallacy (expecting pattern reversal)

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
class BiasFinding:
    """A single cognitive bias detection finding."""
    bias_type: str  # ANCHORING, CONFIRMATION, RECENCY, etc.
    description: str
    evidence: dict[str, Any]  # Episode artifact citations
    severity: str  # INFO, WARNING, CRITICAL


@dataclass
class BiasCritique:
    """Result of cognitive bias critique."""
    episode_id: str
    findings: list[BiasFinding]
    is_clean: bool
    total_biases: int


@dataclass
class BiasPatchProposal:
    """Proposed patch to mitigate bias."""
    episode_id: str
    bias_type: str
    proposed_fix: str
    rationale: str


class CognitiveBiasCritic:
    """
    Read-only critic that detects cognitive biases.
    
    Doctrine:
    - Read-only (no state mutation)
    - Episode-bound (all findings cite artifacts)
    - No auto-apply (emits proposals only)
    - Post-hoc audit only
    """
    
    @enforce_read_only
    @enforce_episode_bound
    def critique(
        self,
        episode: Episode,
        artifacts: list[EpisodeArtifact],
    ) -> BiasCritique:
        """
        Detect cognitive biases in episode artifacts.
        
        Args:
            episode: Episode to critique
            artifacts: All artifacts for this episode
            
        Returns:
            BiasCritique with findings
            
        Doctrine: DOCTRINE_CRITIC_AUTHORITY
        """
        findings: list[BiasFinding] = []
        
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
            return BiasCritique(
                episode_id=episode.id,
                findings=[],
                is_clean=True,
                total_biases=0,
            )
        
        pre_state = pre_state_artifact.payload
        inference = inference_artifact.payload
        
        # Check for anchoring bias
        findings.extend(self._detect_anchoring_bias(
            episode, pre_state_artifact, inference_artifact, pre_state, inference
        ))
        
        # Check for confirmation bias
        findings.extend(self._detect_confirmation_bias(
            episode, pre_state_artifact, inference_artifact, pre_state, inference
        ))
        
        # Check for recency bias
        findings.extend(self._detect_recency_bias(
            episode, pre_state_artifact, inference_artifact, pre_state, inference
        ))
        
        # Check for overconfidence
        findings.extend(self._detect_overconfidence(
            episode, pre_state_artifact, inference_artifact, pre_state, inference
        ))
        
        # Check for herd mentality
        findings.extend(self._detect_herd_mentality(
            episode, pre_state_artifact, inference_artifact, pre_state, inference
        ))
        
        # Check for gambler's fallacy
        findings.extend(self._detect_gamblers_fallacy(
            episode, pre_state_artifact, inference_artifact, pre_state, inference
        ))
        
        return BiasCritique(
            episode_id=episode.id,
            findings=findings,
            is_clean=len(findings) == 0,
            total_biases=len(findings),
        )
    
    def _detect_anchoring_bias(
        self,
        episode: Episode,
        pre_state_artifact: EpisodeArtifact,
        inference_artifact: EpisodeArtifact,
        pre_state: dict[str, Any],
        inference: dict[str, Any],
    ) -> list[BiasFinding]:
        """Detect over-reliance on first information (e.g., morning odds)."""
        findings = []
        
        # Check if morning odds heavily influence final prediction
        if "morning_odds" in pre_state and "predictions" in inference:
            morning_odds = pre_state.get("morning_odds", {})
            predictions = inference.get("predictions", [])
            
            # Check if top prediction matches morning favorite
            if morning_odds and predictions:
                morning_favorite = min(morning_odds.items(), key=lambda x: x[1])[0]
                top_prediction = predictions[0].get("runner_name") if predictions else None
                
                if morning_favorite == top_prediction:
                    findings.append(BiasFinding(
                        bias_type="ANCHORING",
                        description="Top prediction matches morning favorite (possible anchoring bias)",
                        evidence={
                            "pre_state_artifact_id": pre_state_artifact.id,
                            "inference_artifact_id": inference_artifact.id,
                            "morning_favorite": morning_favorite,
                            "top_prediction": top_prediction,
                        },
                        severity="WARNING",
                    ))
        
        return findings
    
    def _detect_confirmation_bias(
        self,
        episode: Episode,
        pre_state_artifact: EpisodeArtifact,
        inference_artifact: EpisodeArtifact,
        pre_state: dict[str, Any],
        inference: dict[str, Any],
    ) -> list[BiasFinding]:
        """Detect seeking confirming evidence."""
        findings = []
        
        # Check if rationale only mentions supporting evidence
        if "rationale" in inference:
            rationale = inference["rationale"].lower()
            
            # Look for one-sided language
            confirming_words = ["confirms", "supports", "validates", "proves"]
            disconfirming_words = ["contradicts", "challenges", "questions", "opposes"]
            
            confirming_count = sum(1 for word in confirming_words if word in rationale)
            disconfirming_count = sum(1 for word in disconfirming_words if word in rationale)
            
            if confirming_count > 0 and disconfirming_count == 0:
                findings.append(BiasFinding(
                    bias_type="CONFIRMATION",
                    description="Rationale only mentions confirming evidence (possible confirmation bias)",
                    evidence={
                        "inference_artifact_id": inference_artifact.id,
                        "confirming_count": confirming_count,
                        "disconfirming_count": disconfirming_count,
                    },
                    severity="INFO",
                ))
        
        return findings
    
    def _detect_recency_bias(
        self,
        episode: Episode,
        pre_state_artifact: EpisodeArtifact,
        inference_artifact: EpisodeArtifact,
        pre_state: dict[str, Any],
        inference: dict[str, Any],
    ) -> list[BiasFinding]:
        """Detect over-weighting recent events."""
        findings = []
        
        # Check if rationale heavily emphasizes recent form
        if "rationale" in inference:
            rationale = inference["rationale"].lower()
            
            # Look for recency language
            recency_words = ["recent", "last race", "latest", "just", "yesterday"]
            recency_count = sum(1 for word in recency_words if word in rationale)
            
            if recency_count >= 2:
                findings.append(BiasFinding(
                    bias_type="RECENCY",
                    description="Rationale heavily emphasizes recent events (possible recency bias)",
                    evidence={
                        "inference_artifact_id": inference_artifact.id,
                        "recency_count": recency_count,
                    },
                    severity="INFO",
                ))
        
        return findings
    
    def _detect_overconfidence(
        self,
        episode: Episode,
        pre_state_artifact: EpisodeArtifact,
        inference_artifact: EpisodeArtifact,
        pre_state: dict[str, Any],
        inference: dict[str, Any],
    ) -> list[BiasFinding]:
        """Detect unjustified high confidence."""
        findings = []
        
        # Check for high confidence with low signal
        if "confidence" in inference and "signal_strength" in inference:
            confidence = inference["confidence"]
            signal_strength = inference["signal_strength"]
            
            if confidence > 0.8 and signal_strength < 0.5:
                findings.append(BiasFinding(
                    bias_type="OVERCONFIDENCE",
                    description=f"High confidence ({confidence:.2f}) with low signal ({signal_strength:.2f})",
                    evidence={
                        "inference_artifact_id": inference_artifact.id,
                        "confidence": confidence,
                        "signal_strength": signal_strength,
                    },
                    severity="WARNING",
                ))
        
        return findings
    
    def _detect_herd_mentality(
        self,
        episode: Episode,
        pre_state_artifact: EpisodeArtifact,
        inference_artifact: EpisodeArtifact,
        pre_state: dict[str, Any],
        inference: dict[str, Any],
    ) -> list[BiasFinding]:
        """Detect following market consensus."""
        findings = []
        
        # Check if prediction matches market favorite
        if "market_favorite" in pre_state and "predictions" in inference:
            market_favorite = pre_state.get("market_favorite")
            predictions = inference.get("predictions", [])
            
            if predictions:
                top_prediction = predictions[0].get("runner_name")
                
                if market_favorite == top_prediction:
                    findings.append(BiasFinding(
                        bias_type="HERD_MENTALITY",
                        description="Top prediction matches market favorite (possible herd mentality)",
                        evidence={
                            "pre_state_artifact_id": pre_state_artifact.id,
                            "inference_artifact_id": inference_artifact.id,
                            "market_favorite": market_favorite,
                            "top_prediction": top_prediction,
                        },
                        severity="INFO",
                    ))
        
        return findings
    
    def _detect_gamblers_fallacy(
        self,
        episode: Episode,
        pre_state_artifact: EpisodeArtifact,
        inference_artifact: EpisodeArtifact,
        pre_state: dict[str, Any],
        inference: dict[str, Any],
    ) -> list[BiasFinding]:
        """Detect expecting pattern reversal."""
        findings = []
        
        # Check if rationale mentions "due" or "overdue"
        if "rationale" in inference:
            rationale = inference["rationale"].lower()
            
            fallacy_words = ["due", "overdue", "turn", "bound to", "must happen"]
            fallacy_count = sum(1 for word in fallacy_words if word in rationale)
            
            if fallacy_count > 0:
                findings.append(BiasFinding(
                    bias_type="GAMBLERS_FALLACY",
                    description="Rationale suggests expecting pattern reversal (gambler's fallacy)",
                    evidence={
                        "inference_artifact_id": inference_artifact.id,
                        "fallacy_words_found": [w for w in fallacy_words if w in rationale],
                    },
                    severity="WARNING",
                ))
        
        return findings
    
    def propose_patch(
        self,
        critique: BiasCritique,
    ) -> list[BiasPatchProposal]:
        """
        Propose patches to mitigate detected biases.
        
        Args:
            critique: Bias critique with findings
            
        Returns:
            List of patch proposals
            
        Doctrine: DOCTRINE_CRITIC_AUTHORITY (no auto-apply)
        """
        proposals = []
        
        for finding in critique.findings:
            if finding.bias_type == "ANCHORING":
                proposals.append(BiasPatchProposal(
                    episode_id=critique.episode_id,
                    bias_type=finding.bias_type,
                    proposed_fix="Consider multiple information sources, not just morning odds",
                    rationale="Anchoring bias leads to over-reliance on first information",
                ))
            
            elif finding.bias_type == "CONFIRMATION":
                proposals.append(BiasPatchProposal(
                    episode_id=critique.episode_id,
                    bias_type=finding.bias_type,
                    proposed_fix="Actively seek disconfirming evidence in rationale",
                    rationale="Confirmation bias leads to one-sided analysis",
                ))
            
            elif finding.bias_type == "RECENCY":
                proposals.append(BiasPatchProposal(
                    episode_id=critique.episode_id,
                    bias_type=finding.bias_type,
                    proposed_fix="Balance recent form with historical performance",
                    rationale="Recency bias over-weights recent events",
                ))
            
            elif finding.bias_type == "OVERCONFIDENCE":
                proposals.append(BiasPatchProposal(
                    episode_id=critique.episode_id,
                    bias_type=finding.bias_type,
                    proposed_fix="Calibrate confidence to match signal strength",
                    rationale="Overconfidence leads to unjustified certainty",
                ))
            
            elif finding.bias_type == "HERD_MENTALITY":
                proposals.append(BiasPatchProposal(
                    episode_id=critique.episode_id,
                    bias_type=finding.bias_type,
                    proposed_fix="Develop independent analysis, not just follow market",
                    rationale="Herd mentality reduces edge and increases correlation",
                ))
            
            elif finding.bias_type == "GAMBLERS_FALLACY":
                proposals.append(BiasPatchProposal(
                    episode_id=critique.episode_id,
                    bias_type=finding.bias_type,
                    proposed_fix="Remove language suggesting pattern reversal expectations",
                    rationale="Gambler's fallacy assumes independent events are correlated",
                ))
        
        return proposals


__all__ = [
    "BiasFinding",
    "BiasCritique",
    "BiasPatchProposal",
    "CognitiveBiasCritic",
]
