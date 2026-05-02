
"""
VÉLØ Weight Policy Registry
============================

Canonical registry for all VÉLØ scoring policy lanes.
Defines the weights and inclusion logic for ensemble components.

This registry is the Single Source of Truth for how probabilities are
constructed across different environments (Live, Shadow, Research, Paper).
"""

from dataclasses import dataclass, field
from typing import Dict, Set

@dataclass
class WeightPolicy:
    name: str
    status: str
    weights: Dict[str, float]
    gated_weights: Dict[str, Dict] = field(default_factory=dict)
    description: str = ""

# ─── Policy A: LIVE_BASELINE_CURRENT ──────────────────────────────────────────
# Records the current runtime truth as proven by audit.
LIVE_BASELINE_CURRENT = WeightPolicy(
    name="LIVE_BASELINE_CURRENT",
    status="LIVE_CURRENT",
    description="Current runtime truth. Used for operator VP today.",
    weights={
        "sqpe_v17": 0.45,
        "improvement_score": 0.12,
        "release_day_prob": 0.10,
        "market_deception_score": 0.10,
        "place_prob": 0.08,
        "comment_intel_score": 0.08,
    },
    gated_weights={
        "longshot_score": {
            "weight": 0.07,
            "gate": "sp_dec >= 10.0"
        }
    }
)

# ─── Policy B: SHADOW_SAFE_V2 ────────────────────────────────────────────────
# Candidate safer policy based on confluence audit.
# SQPE carries clean value; dangerous/red-flag sidecars removed or reduced.
SHADOW_SAFE_V2 = WeightPolicy(
    name="SHADOW_SAFE_V2",
    status="SHADOW_ONLY",
    description="Safer candidate policy. High SQPE anchor, reduced Improvement risk.",
    weights={
        "sqpe_v17": 0.80,
        "market_deception_score": 0.08,
        "place_prob": 0.06,
        "improvement_score": 0.04,
        "release_day_prob": 0.00,
        "comment_intel_score": 0.00,
        "racing_api_enrichment": 0.00,
        "cashrun": 0.00,
    },
    gated_weights={
        "longshot_score": {
            "weight": 0.02,
            "gate": "sp_dec >= 10.0"
        }
    }
)

# ─── Policy C: SHADOW_FULL_STACK_V1 ──────────────────────────────────────────
# Candidate research lane for testing new enrichment sources.
SHADOW_FULL_STACK_V1 = WeightPolicy(
    name="SHADOW_FULL_STACK_V1",
    status="SHADOW_ONLY_RESEARCH",
    description="Research lane testing Racing API and CASHRUN lift.",
    weights={
        "sqpe_v17": 0.70,
        "market_deception_score": 0.08,
        "place_prob": 0.05,
        "improvement_score": 0.03,
        "racing_api_enrichment": 0.07,
        "cashrun": 0.05,
        "release_day_prob": 0.00,
        "comment_intel_score": 0.00,
    },
    gated_weights={
        "longshot_score": {
            "weight": 0.02,
            "gate": "sp_dec >= 10.0"
        }
    }
)

# ─── Policy D: PAPER_EXECUTION_POLICY ────────────────────────────────────────
# Bridge-only policy for paper tracking.
PAPER_EXECUTION_POLICY = WeightPolicy(
    name="PAPER_EXECUTION_POLICY",
    status="PAPER_ONLY",
    description="No VP weights. Reads bridge directives only.",
    weights={},
    gated_weights={}
)

# Registry Mapping
POLICIES = {
    "LIVE_BASELINE_CURRENT": LIVE_BASELINE_CURRENT,
    "SHADOW_SAFE_V2": SHADOW_SAFE_V2,
    "SHADOW_FULL_STACK_V1": SHADOW_FULL_STACK_V1,
    "PAPER_EXECUTION_POLICY": PAPER_EXECUTION_POLICY,
}

def get_policy(name: str) -> WeightPolicy:
    return POLICIES.get(name, LIVE_BASELINE_CURRENT)
