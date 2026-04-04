"""
VÉLØ SQPE_DIRECT Decision Policy
==================================
Bypasses all stub-dependent guards.
Makes decisions using SQPE probability alone.

Thresholds (tunable via env):
  SQPE_WIN_THRESHOLD   — min SQPE prob to fire a WIN_OVERLAY   (default 0.30)
  SQPE_TOP4_THRESHOLD  — min SQPE prob to appear in TOP_4      (default 0.10)

Suppression tracer is always written so every race can be compared to PROD output.
"""

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

WIN_THRESHOLD  = float(os.getenv("SQPE_WIN_THRESHOLD",  "0.30"))
TOP4_THRESHOLD = float(os.getenv("SQPE_TOP4_THRESHOLD", "0.10"))


@dataclass
class DirectDecision:
    mode: str = "sqpe_direct"
    win_selection: str | None = None
    top_4: list[str] = field(default_factory=list)
    win_suppressed: bool = True
    suppression_reason: str = ""
    sqpe_scores: dict[str, float] = field(default_factory=dict)   # runner_id → prob
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "win_selection": self.win_selection,
            "top_4": self.top_4,
            "win_suppressed": self.win_suppressed,
            "suppression_reason": self.suppression_reason,
            "sqpe_scores": self.sqpe_scores,
            "confidence": self.confidence,
        }


def decide_sqpe_direct(runner_sqpe_probs: dict[str, float]) -> DirectDecision:
    """
    Pure SQPE decision.

    Args:
        runner_sqpe_probs: {runner_id: win_probability}  (already normalised 0-1)

    Returns:
        DirectDecision
    """
    if not runner_sqpe_probs:
        return DirectDecision(
            win_suppressed=True,
            suppression_reason="No SQPE scores available",
        )

    # Rank by probability descending
    ranked = sorted(runner_sqpe_probs.items(), key=lambda x: x[1], reverse=True)
    top_runner_id, top_prob = ranked[0]

    # Top-4 by threshold
    top_4 = [rid for rid, p in ranked if p >= TOP4_THRESHOLD][:4]
    if not top_4:
        top_4 = [rid for rid, _ in ranked[:4]]  # fallback: just take top 4

    # Win decision
    if top_prob >= WIN_THRESHOLD:
        return DirectDecision(
            win_selection=top_runner_id,
            top_4=top_4,
            win_suppressed=False,
            sqpe_scores=dict(ranked),
            confidence=top_prob,
        )
    else:
        return DirectDecision(
            win_selection=None,
            top_4=top_4,
            win_suppressed=True,
            suppression_reason=f"SQPE top prob {top_prob:.3f} < threshold {WIN_THRESHOLD}",
            sqpe_scores=dict(ranked),
            confidence=top_prob,
        )
