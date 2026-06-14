"""
Central configuration for Mission Control gate thresholds.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MissionControlConfig:
    # ── Contamination & Flatlines ──────────────────────────────────────────
    CONTAMINATED_RUN_IDS: set[str] = field(default_factory=lambda: {"32cc27f9", "847964a6"})

    # ── Thresholds ──────────────────────────────────────────────────────────
    DEGRADED_VERDICT_THRESHOLD: float = 0.80  # 80% of verdicts degraded blocks learning
    RUNNER_CALIBRATION_THRESHOLD: int = 300
    DECISION_POLICY_GATE_1: int = 150
    DECISION_POLICY_GATE_2: int = 300

    # ── Status Labels ───────────────────────────────────────────────────────
    LEARNING_GATE_OPEN: str = "OPEN"
    LEARNING_GATE_BLOCKED: str = "BLOCKED"
    PROMOTION_GATE_OPEN: str = "OPEN"
    PROMOTION_GATE_BLOCKED: str = "BLOCKED"


MC_CONFIG = MissionControlConfig()
