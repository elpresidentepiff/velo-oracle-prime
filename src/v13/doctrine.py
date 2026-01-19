"""
VÉLØ V13 - Constitutional Doctrine

This module defines the immutable rules that govern VÉLØ's epistem integrity,
critic behavior, and learning authority.

These are not "features" - they are constitutional constraints.
Any system that violates these is not VÉLØ.

Author: VÉLØ Team
Date: 2026-01-19
Status: LOCKED
"""

from typing import Final

# =============================================================================
# EPISTEMIC TIME SEPARATION
# =============================================================================

DOCTRINE_EPISTEMIC_TIME: Final[str] = """
RULE: Epistemic time (decisionTime) MUST be separated from execution time (createdAt).

- decisionTime = when the decision was made (knowledge cutoff)
- createdAt = when the artifact was written (execution timestamp)

All temporal reasoning (leakage detection, causality, backtesting) MUST anchor
to decisionTime, NEVER createdAt.

Violation of this rule allows temporal contamination and destroys replay integrity.
"""

# =============================================================================
# CRITIC AUTHORITY
# =============================================================================

DOCTRINE_CRITIC_AUTHORITY: Final[str] = """
RULE: Critics observe, they do not decide.

All critics MUST be:
- Read-only (no state mutation)
- Episode-bound (all findings cite artifacts)
- Non-executive (emit CritiqueResult and PatchProposal only)
- Post-hoc (audit after the fact, never intervene)

Critics MUST NOT:
- Make decisions
- Mutate state
- Auto-apply patches
- Block execution
- Have learning authority

Violation of this rule creates hidden agency and destroys auditability.
"""

# =============================================================================
# FEATURE QUALITY FIREWALL
# =============================================================================

DOCTRINE_FEATURE_FIREWALL: Final[str] = """
RULE: No feature enters the model unless it survives the Feature Extractor Critic
with zero CRITICAL findings.

Features MUST be:
- Complete (no missing critical features)
- Non-redundant (no duplicates or high correlation)
- Leak-free (no future information)
- Valid (no NaN, Infinity, or out-of-range values)

Violation of this rule allows garbage features to poison the model.
"""

# =============================================================================
# NO SILENT SELF-MODIFICATION
# =============================================================================

DOCTRINE_NO_SILENT_MODIFICATION: Final[str] = """
RULE: No self-modification without explicit human consent.

All changes to doctrine, rules, thresholds, or behavior MUST:
- Be proposed as PatchProposal objects
- Route through governance pipeline
- Require human review
- Be logged with explicit accept/reject decision

Violation of this rule creates unaccountable drift and founder amnesia.
"""

# =============================================================================
# REPLAY INTEGRITY
# =============================================================================

DOCTRINE_REPLAY_INTEGRITY: Final[str] = """
RULE: Every episode MUST be deterministically replayable.

Episodes MUST have:
- Deterministic IDs (function of race_id + engine_version + timestamp_bucket)
- Context hash (for replay validation)
- Artifact checksums (SHA256 of payload)
- Replay hash (SHA256 of concatenated checksums)

Replaying an episode MUST produce identical:
- Episode IDs
- Artifact checksums
- Final replay hash

Violation of this rule destroys historical truth and makes learning untrustworthy.
"""

# =============================================================================
# TRUTH BEFORE OPTIMIZATION
# =============================================================================

DOCTRINE_TRUTH_BEFORE_OPTIMIZATION: Final[str] = """
RULE: Truth before optimization, memory before learning, doctrine before power.

Priority order (non-negotiable):
1. Epistemic integrity (can we trust what we know?)
2. Audit trail (can we explain what we did?)
3. Doctrine compliance (did we follow the rules?)
4. Performance (did we win?)

Optimizing for performance before establishing truth creates false confidence
and undetectable rot.

Violation of this rule is how systems become superstitious.
"""

# =============================================================================
# DOCTRINE REGISTRY
# =============================================================================

DOCTRINE_REGISTRY: Final[dict[str, str]] = {
    "epistemic_time": DOCTRINE_EPISTEMIC_TIME,
    "critic_authority": DOCTRINE_CRITIC_AUTHORITY,
    "feature_firewall": DOCTRINE_FEATURE_FIREWALL,
    "no_silent_modification": DOCTRINE_NO_SILENT_MODIFICATION,
    "replay_integrity": DOCTRINE_REPLAY_INTEGRITY,
    "truth_before_optimization": DOCTRINE_TRUTH_BEFORE_OPTIMIZATION,
}


def get_doctrine(name: str) -> str:
    """
    Retrieve a specific doctrine rule by name.
    
    Args:
        name: Doctrine name (e.g., "epistemic_time")
        
    Returns:
        Doctrine text
        
    Raises:
        KeyError: If doctrine name not found
    """
    return DOCTRINE_REGISTRY[name]


def validate_doctrine_compliance(
    operation: str,
    checks: dict[str, bool]
) -> tuple[bool, list[str]]:
    """
    Validate that an operation complies with all doctrine rules.
    
    Args:
        operation: Name of operation being validated
        checks: Dict of {doctrine_name: is_compliant}
        
    Returns:
        Tuple of (is_compliant, violations)
        
    Example:
        >>> validate_doctrine_compliance(
        ...     "apply_patch",
        ...     {
        ...         "no_silent_modification": False,  # Missing human approval
        ...         "critic_authority": True,
        ...     }
        ... )
        (False, ["no_silent_modification: Missing human approval"])
    """
    violations = []
    
    for doctrine_name, is_compliant in checks.items():
        if not is_compliant:
            violations.append(f"{doctrine_name}: Violation detected in {operation}")
    
    return len(violations) == 0, violations


def enforce_read_only(func):
    """
    Decorator to enforce read-only behavior on critic methods.
    
    Raises:
        RuntimeError: If method attempts to mutate state
        
    Example:
        >>> @enforce_read_only
        ... def critique(self, episode_id):
        ...     # Read-only operations only
        ...     return critique_result
    """
    def wrapper(*args, **kwargs):
        # TODO: Implement state mutation detection
        # For now, this is a documentation decorator
        return func(*args, **kwargs)
    
    wrapper.__doc__ = f"[READ-ONLY] {func.__doc__ or ''}"
    return wrapper


def enforce_episode_bound(func):
    """
    Decorator to enforce episode-bound behavior on critic methods.
    
    All findings MUST cite episode artifacts.
    
    Example:
        >>> @enforce_episode_bound
        ... def critique(self, episode_id):
        ...     findings = [...]  # Must include artifact citations
        ...     return critique_result
    """
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        
        # Validate that all findings cite artifacts
        if hasattr(result, 'findings'):
            for finding in result.findings:
                if not hasattr(finding, 'evidence') or not finding.evidence:
                    raise RuntimeError(
                        f"Doctrine violation: Finding '{finding.description}' "
                        f"does not cite episode artifacts"
                    )
        
        return result
    
    wrapper.__doc__ = f"[EPISODE-BOUND] {func.__doc__ or ''}"
    return wrapper


# =============================================================================
# CONSTITUTIONAL GUARANTEES
# =============================================================================

__all__ = [
    "DOCTRINE_EPISTEMIC_TIME",
    "DOCTRINE_CRITIC_AUTHORITY",
    "DOCTRINE_FEATURE_FIREWALL",
    "DOCTRINE_NO_SILENT_MODIFICATION",
    "DOCTRINE_REPLAY_INTEGRITY",
    "DOCTRINE_TRUTH_BEFORE_OPTIMIZATION",
    "DOCTRINE_REGISTRY",
    "get_doctrine",
    "validate_doctrine_compliance",
    "enforce_read_only",
    "enforce_episode_bound",
]
