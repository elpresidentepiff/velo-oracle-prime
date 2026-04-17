"""
Proposal Fingerprinting

Generates deterministic hashes for proposals to detect duplicates across episodes.

Fingerprint includes:
- critic_type (e.g., "LEAKAGE")
- finding_type (e.g., "FUTURE_MARKET_LEAKAGE")
- proposed_change (normalized JSON)

Does NOT include:
- episode_id (same proposal can appear in multiple episodes)
- timestamp (temporal variance irrelevant)
- description (human text may vary)
"""

import hashlib
import json
from typing import Any, Dict


def fingerprint_proposal(
    critic_type: str,
    finding_type: str,
    proposed_change: Dict[str, Any],
) -> str:
    """
    Generate deterministic fingerprint for proposal deduplication.
    
    Args:
        critic_type: Type of critic (LEAKAGE, BIAS, FEATURE, DECISION)
        finding_type: Specific finding type (e.g., FUTURE_MARKET_LEAKAGE)
        proposed_change: Structured patch payload (dict)
    
    Returns:
        SHA256 hex digest (64 characters)
    
    Examples:
        >>> fp1 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "validate_time"})
        >>> fp2 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "validate_time"})
        >>> fp1 == fp2
        True
        
        >>> fp3 = fingerprint_proposal("LEAKAGE", "FUTURE_MARKET", {"rule": "reject_future"})
        >>> fp1 == fp3
        False
    """
    payload = {
        "critic_type": critic_type,
        "finding_type": finding_type,
        "proposed_change": proposed_change,
    }
    
    # Normalize JSON (sorted keys, no whitespace)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    
    # SHA256 hash
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fingerprint_from_dict(proposal_dict: Dict[str, Any]) -> str:
    """
    Convenience wrapper for fingerprinting from proposal dict.
    
    Args:
        proposal_dict: Dict with critic_type, finding_type, proposed_change keys
    
    Returns:
        SHA256 hex digest
    """
    return fingerprint_proposal(
        critic_type=proposal_dict["critic_type"],
        finding_type=proposal_dict["finding_type"],
        proposed_change=proposal_dict["proposed_change"],
    )
