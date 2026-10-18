"""Deterministic Proposer/Reflector research cycle; no LLM or external effects.

This is the first agent-compatible contract, not automated model evolution.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from src.intelligence.challenger_lab import Observation, evaluate


@dataclass(frozen=True)
class Proposal:
    candidate_id: str
    hypothesis: str
    baseline_ref: str
    research_only: bool = True


def propose_calibration_review(*, baseline_ref: str) -> Proposal:
    """Pre-registered hypothesis, generated independently of held-out outcomes."""
    if not baseline_ref.strip():
        raise ValueError("baseline_ref required")
    hypothesis = "Test whether high predicted win probabilities are overconfident on future held-out racing dates"
    digest = sha256(f"{baseline_ref}:{hypothesis}".encode()).hexdigest()[:16]
    return Proposal(f"calibration-{digest}", hypothesis, baseline_ref)


def reflect(proposal: Proposal, rows: list[Observation], *, min_runners: int = 300) -> dict:
    """Evaluate frozen paired records; never authorize promotion.

    Strictly deterministic output. A proposer cannot inspect these outcomes
    before proposing; caller must enforce a held-out date split and provenance.
    """
    if not proposal.research_only:
        raise ValueError("research-only proposal required")
    result = evaluate(rows, min_runners=min_runners)
    delta = result["brier_delta_challenger_minus_baseline"]
    outcome = "REJECT" if delta >= 0 else "REVIEW_REQUIRED"
    output = {
        "proposal": asdict(proposal),
        "evaluation": result,
        "reflector_decision": outcome,
        "reason": (
            "No Brier improvement observed" if outcome == "REJECT"
            else "Improved Brier on submitted cohort; independent time-split, provenance and stability review still required"
        ),
        "production_authority": False,
    }
    payload = json.dumps(output, sort_keys=True, separators=(",", ":"))
    output["artifact_sha256"] = sha256(payload.encode()).hexdigest()
    return output
