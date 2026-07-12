"""
LearningEventV2 — LEARNING-LOOP-01A Phase 3.

The single immutable event contract every learner (Playbook G V2, Sigma
memory distillation, future model-promotion tribunals) must consume from.
No learner reconstructs its own weaker version of this event.

Design constraints from the governed mission spec:
  - No field may default to "safe". `time_safety` and `leakage_status` are
    required constructor arguments with no default value — a caller must
    make an explicit, evidenced classification for every event.
  - The event is immutable (frozen dataclass) and hashable
    (`event_id`/`consumption_id` are deterministic functions of its
    content, not random UUIDs), so the same reconciled (prediction,
    result) pair always produces the same event id -- reruns are
    idempotent, not duplicate-generating.
  - This module does not read Supabase, does not read local files, and
    does not decide identity or result-source selection itself -- it only
    defines the shape of the event and computes its deterministic ids.
    Callers (Phase 4's corpus builder) are responsible for populating it
    from `identity_resolver` / `result_source_selector` output.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "learning_event_v2.0"

# -- required, no-default-safe time-safety classifications ------------------
TIME_SAFETY_SAFE_PROSPECTIVE = "SAFE_PROSPECTIVE"
TIME_SAFETY_SAFE_FROZEN_REPLAY = "SAFE_FROZEN_REPLAY"
TIME_SAFETY_COUNTERFACTUAL_REPLAY = "CURRENT_CODE_COUNTERFACTUAL_REPLAY"
TIME_SAFETY_EXCLUDED_POST_RACE_LEAKAGE = "EXCLUDED_POST_RACE_LEAKAGE"
TIME_SAFETY_EXCLUDED_UNTIMED_ODDS = "EXCLUDED_UNTIMED_ODDS"
TIME_SAFETY_EXCLUDED_IDENTITY_AMBIGUOUS = "EXCLUDED_IDENTITY_AMBIGUOUS"
TIME_SAFETY_EXCLUDED_INCOMPLETE_RESULT = "EXCLUDED_INCOMPLETE_RESULT"
TIME_SAFETY_EXCLUDED_FEATURE_PROVENANCE_UNKNOWN = "EXCLUDED_FEATURE_PROVENANCE_UNKNOWN"

VALID_TIME_SAFETY = {
    TIME_SAFETY_SAFE_PROSPECTIVE,
    TIME_SAFETY_SAFE_FROZEN_REPLAY,
    TIME_SAFETY_COUNTERFACTUAL_REPLAY,
    TIME_SAFETY_EXCLUDED_POST_RACE_LEAKAGE,
    TIME_SAFETY_EXCLUDED_UNTIMED_ODDS,
    TIME_SAFETY_EXCLUDED_IDENTITY_AMBIGUOUS,
    TIME_SAFETY_EXCLUDED_INCOMPLETE_RESULT,
    TIME_SAFETY_EXCLUDED_FEATURE_PROVENANCE_UNKNOWN,
}

SAFE_TIME_SAFETY_CLASSES = {TIME_SAFETY_SAFE_PROSPECTIVE, TIME_SAFETY_SAFE_FROZEN_REPLAY}

VALID_LEAKAGE_STATUS = {"CLEAN", "SUSPECTED", "CONFIRMED", "UNKNOWN"}


class LearningEventValidationError(ValueError):
    pass


def _sha256_of_obj(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PredictionTruth:
    race_date: str
    race_id: str
    course: str
    off_time: str
    runner_universe: tuple[dict[str, Any], ...]  # full pre-race runner list
    model_scores: dict[str, Any]  # every model/shadow score keyed by name
    rank_order: tuple[str, ...]  # horse_ids in predicted rank order
    top_three: tuple[str, ...]
    odds_value: float | None
    odds_capture_ts: str | None
    source_commit: str | None
    input_card_hash: str
    model_versions: dict[str, str]
    active_components: tuple[str, ...]
    excluded_components: tuple[str, ...]


@dataclass(frozen=True)
class OutcomeTruth:
    result_race_id: str
    runner_positions: dict[str, str]  # horse_id -> finishing position (or "NR")
    non_runners: tuple[str, ...]
    sp_by_horse: dict[str, float]
    bsp_by_horse: dict[str, float]
    winner_horse_id: str | None
    frame_horse_ids: tuple[str, ...]  # placed horses
    result_source_hash: str | None


@dataclass(frozen=True)
class RaceContext:
    race_class: str | None
    race_type: str | None
    field_size: int | None
    going: str | None
    distance_f: float | None
    surface: str | None
    pace_map: dict[str, Any] = field(default_factory=dict)
    draw_by_horse: dict[str, Any] = field(default_factory=dict)
    pre_race_market_rank: dict[str, int] = field(default_factory=dict)
    rpdc_tags: dict[str, Any] = field(default_factory=dict)
    rpd_tags: dict[str, Any] = field(default_factory=dict)
    tie_signals: dict[str, Any] = field(default_factory=dict)
    nds_signals: dict[str, Any] = field(default_factory=dict)
    cashrun_signals: dict[str, Any] = field(default_factory=dict)
    archetype: str | None = None
    playbook_g_state_hash: str | None = None


@dataclass(frozen=True)
class SafetyProvenance:
    race_resolution_method: str
    horse_resolution_methods: dict[str, str]  # horse_id -> method
    ambiguous_join_blocked: bool
    time_safety: str
    leakage_status: str
    learning_allowed: bool
    promotion_eligible: bool
    result_source: str  # RP_LOCAL_JSON | SUPABASE_CANONICAL_RESULT | SUPABASE_LEGACY_RESULT | RESULT_SOURCE_UNAVAILABLE
    result_source_classification: str  # RESULT_SOURCE_* classification from result_source_selector

    def __post_init__(self) -> None:
        if self.time_safety not in VALID_TIME_SAFETY:
            raise LearningEventValidationError(f"Unknown time_safety classification: {self.time_safety!r}")
        if self.leakage_status not in VALID_LEAKAGE_STATUS:
            raise LearningEventValidationError(f"Unknown leakage_status: {self.leakage_status!r}")
        if self.ambiguous_join_blocked and self.learning_allowed:
            raise LearningEventValidationError("An ambiguous-join-blocked event cannot have learning_allowed=True")
        if self.time_safety not in SAFE_TIME_SAFETY_CLASSES and self.promotion_eligible:
            raise LearningEventValidationError(
                f"promotion_eligible=True requires a SAFE_* time_safety classification, got {self.time_safety!r}"
            )


@dataclass(frozen=True)
class LearningEventV2:
    schema_version: str
    prediction: PredictionTruth
    outcome: OutcomeTruth
    context: RaceContext
    safety: SafetyProvenance

    @property
    def event_id(self) -> str:
        """Deterministic id: same reconciled (prediction, outcome) content
        always yields the same id -- reruns upsert, never duplicate."""
        payload = {
            "schema_version": self.schema_version,
            "race_id": self.prediction.race_id,
            "race_date": self.prediction.race_date,
            "input_card_hash": self.prediction.input_card_hash,
            "result_source_hash": self.outcome.result_source_hash,
        }
        return _sha256_of_obj(payload)

    @property
    def consumption_id(self) -> str:
        """Distinct from event_id: identifies one (event, consumer) pairing
        so a learner can mark 'I have consumed this event' without
        blocking a different consumer from processing the same event."""
        payload = {"event_id": self.event_id, "schema_version": self.schema_version}
        return _sha256_of_obj(payload)

    def content_hash(self) -> str:
        return _sha256_of_obj(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["event_id"] = self.event_id
        d["consumption_id"] = self.consumption_id
        return d


def build_learning_event(
    *,
    prediction: PredictionTruth,
    outcome: OutcomeTruth,
    context: RaceContext,
    safety: SafetyProvenance,
) -> LearningEventV2:
    return LearningEventV2(
        schema_version=SCHEMA_VERSION,
        prediction=prediction,
        outcome=outcome,
        context=context,
        safety=safety,
    )
