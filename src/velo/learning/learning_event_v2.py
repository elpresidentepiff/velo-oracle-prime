"""
LearningEventV2 — LEARNING-LOOP-01A Phase 3 (corrected per REQUEST CHANGES
on PR #147: P0-4, P0-5, P0-6).

The single immutable event contract every learner (Playbook G V2, Sigma
memory distillation, future model-promotion tribunals) must consume from.
No learner reconstructs its own weaker version of this event.

Design constraints from the governed mission spec:
  - No field may default to "safe". `time_safety` and `leakage_status` are
    required constructor arguments with no default value.
  - The event is immutable (frozen dataclass).
  - `input_card_hash` is a real SHA-256 of the canonical, stably-ordered
    frozen input card (`compute_input_card_hash`) -- never a bare
    identifier string.
  - `event_key` is the *stable logical identity* of an event (schema,
    race, subject horse, selected prediction run) -- it does NOT change
    when content changes. `event_content_hash` is the full-content hash
    and DOES change whenever any material frozen truth changes (model
    score, rank order, selected run, source commit, model version,
    result position, winner, result source content, safety
    classification -- all of it, because it hashes the entire frozen
    dataclass tree). `event_id` combines both, so a corrected result
    produces a new `event_id` under the same `event_key` rather than
    silently overwriting the old one under an unchanged identity.
  - `consumption_id` is not a bare function of the event -- it requires
    an explicit consumer name, consumer version, and target state, so
    two different learners consuming the same event never collide on
    the same consumption id, and the same learner re-consuming after a
    version bump or state change gets a distinct id.
  - `promotion_eligible=True` requires every promotion gate to hold
    simultaneously (see `SafetyProvenance.__post_init__`) -- it is not a
    label that can be set independently of the evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "learning_event_v2.2"

# -- required, no-default-safe time-safety classifications ------------------
TIME_SAFETY_SAFE_PROSPECTIVE = "SAFE_PROSPECTIVE"
TIME_SAFETY_SAFE_FROZEN_REPLAY = "SAFE_FROZEN_REPLAY"
TIME_SAFETY_COUNTERFACTUAL_REPLAY = "CURRENT_CODE_COUNTERFACTUAL_REPLAY"
TIME_SAFETY_EXCLUDED_POST_RACE_LEAKAGE = "EXCLUDED_POST_RACE_LEAKAGE"
TIME_SAFETY_EXCLUDED_UNTIMED_ODDS = "EXCLUDED_UNTIMED_ODDS"
TIME_SAFETY_EXCLUDED_IDENTITY_AMBIGUOUS = "EXCLUDED_IDENTITY_AMBIGUOUS"
TIME_SAFETY_EXCLUDED_INCOMPLETE_RESULT = "EXCLUDED_INCOMPLETE_RESULT"
TIME_SAFETY_EXCLUDED_FEATURE_PROVENANCE_UNKNOWN = "EXCLUDED_FEATURE_PROVENANCE_UNKNOWN"
TIME_SAFETY_EXCLUDED_TIMEZONE_UNPROVEN = "EXCLUDED_TIMEZONE_UNPROVEN"
TIME_SAFETY_EXCLUDED_PREDICTION_TIME_UNPROVEN = "EXCLUDED_PREDICTION_TIME_UNPROVEN"

VALID_TIME_SAFETY = {
    TIME_SAFETY_SAFE_PROSPECTIVE,
    TIME_SAFETY_SAFE_FROZEN_REPLAY,
    TIME_SAFETY_COUNTERFACTUAL_REPLAY,
    TIME_SAFETY_EXCLUDED_POST_RACE_LEAKAGE,
    TIME_SAFETY_EXCLUDED_UNTIMED_ODDS,
    TIME_SAFETY_EXCLUDED_IDENTITY_AMBIGUOUS,
    TIME_SAFETY_EXCLUDED_INCOMPLETE_RESULT,
    TIME_SAFETY_EXCLUDED_FEATURE_PROVENANCE_UNKNOWN,
    TIME_SAFETY_EXCLUDED_TIMEZONE_UNPROVEN,
    TIME_SAFETY_EXCLUDED_PREDICTION_TIME_UNPROVEN,
}

SAFE_TIME_SAFETY_CLASSES = {TIME_SAFETY_SAFE_PROSPECTIVE, TIME_SAFETY_SAFE_FROZEN_REPLAY}

VALID_LEAKAGE_STATUS = {"CLEAN", "SUSPECTED", "CONFIRMED", "UNKNOWN"}


class LearningEventValidationError(ValueError):
    pass


def _sha256_of_obj(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_input_card_hash(
    *,
    race_id: str,
    subject_horse_id: str,
    prediction_run_id: str | None,
    runner_universe: Any,
    model_scores: Any,
    rank_order: Any,
    top_three: Any,
    model_versions: Any,
    active_components: Any,
    excluded_components: Any,
) -> str:
    """SHA-256 of the canonical, stably-ordered frozen input card. This is
    a real hash of the card content -- never a bare 'race_id:horse_id'
    identifier string."""
    payload = {
        "race_id": race_id,
        "subject_horse_id": subject_horse_id,
        "prediction_run_id": prediction_run_id,
        "runner_universe": runner_universe,
        "model_scores": model_scores,
        "rank_order": rank_order,
        "top_three": top_three,
        "model_versions": model_versions,
        "active_components": active_components,
        "excluded_components": excluded_components,
    }
    return _sha256_of_obj(payload)


def compute_consumption_id(
    *,
    event_id: str,
    consumer_name: str,
    consumer_version: str,
    target_state: str,
) -> str:
    """A consumption is identified by (event, consumer, consumer version,
    target state) -- never by the event alone. Two different learners
    consuming the same event get different ids; the same learner
    re-consuming after a version bump or state change also gets a
    different id."""
    payload = {
        "event_id": event_id,
        "consumer_name": consumer_name,
        "consumer_version": consumer_version,
        "target_state": target_state,
    }
    return _sha256_of_obj(payload)


@dataclass(frozen=True)
class PredictionTruth:
    race_date: str
    race_id: str
    course: str
    off_time: str
    subject_horse_id: str  # the horse this event's prediction/outcome pair is about
    prediction_run_id: str | None  # the single canonical run_id selected for this race
    runner_universe: tuple[dict[str, Any], ...]  # full pre-race runner list of the selected run
    model_scores: dict[str, Any]  # every model/shadow score keyed by name
    rank_order: tuple[str, ...]  # horse_ids in predicted rank order, from the selected run only
    top_three: tuple[str, ...]
    odds_value: float | None
    odds_capture_ts: str | None
    prediction_timestamp: str | None  # when the selected run was created
    source_commit: str | None
    input_card_hash: str  # must be produced by compute_input_card_hash(), not a bare id string
    model_versions: dict[str, str]
    active_components: tuple[str, ...]
    excluded_components: tuple[str, ...]


@dataclass(frozen=True)
class OutcomeTruth:
    result_race_id: str
    runner_positions: dict[str, str]  # horse_id -> finishing position, terminal code, or "NR"/"WD"
    non_runners: tuple[str, ...]
    sp_by_horse: dict[str, float]
    bsp_by_horse: dict[str, float]
    winner_horse_id: str | None
    frame_horse_ids: tuple[str, ...]  # placed horses
    result_source_hash: str | None
    result_universe_complete: bool  # every predicted runner accounted for (position/terminal/NR)

    # -- P0-9: reconciled subject-horse identity, persisted directly so no
    # consumer ever has to rerun identity resolution to learn what
    # happened to THIS event's predicted horse. `resolved_result_horse_id`
    # is the result-side identity that `prediction.subject_horse_id`
    # (prediction-side identity) was reconciled to -- these two ids may
    # differ (numeric prediction id vs rp_ scheme result id, resolved by
    # name), and every subject_* field below is looked up via the
    # resolved id, never the raw prediction id.
    resolved_result_horse_id: str | None
    horse_resolution_method: str
    subject_outcome_status: str  # FINISHED | TERMINAL | NON_RUNNER | UNKNOWN
    subject_finish_position: str | None
    subject_sp: float | None
    subject_bsp: float | None
    subject_is_winner: bool
    subject_is_frame: bool
    subject_is_non_runner: bool


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
    result_source: str  # RP_LOCAL_JSON | SUPABASE_CANONICAL_RESULT | SUPABASE_LEGACY_RESULT | RESULT_SOURCE_UNAVAILABLE
    result_source_classification: str  # RESULT_SOURCE_* classification from result_source_selector
    result_source_complete: bool  # from OutcomeTruth.result_universe_complete, duplicated here for gating

    # -- provenance completeness, each independently checkable ------------
    prediction_timestamp_present: bool
    prediction_timestamp_before_off: bool | None  # None = not provable either way
    odds_timestamp_present: bool
    odds_timestamp_before_off: bool | None
    source_commit_present: bool
    model_versions_present: bool
    input_card_hash_verified: bool  # True only if built via compute_input_card_hash()

    # -- granular allow-flags: do not overload one boolean for all meanings
    analysis_allowed: bool  # may be looked at / reported on, nothing more
    shadow_evaluation_allowed: bool  # may feed a shadow counterfactual score
    state_learning_allowed: bool  # may update Playbook G / learner state
    model_training_allowed: bool  # may enter a training corpus
    promotion_eligible: bool  # may be cited as evidence for a live-weight promotion decision

    def __post_init__(self) -> None:
        if self.time_safety not in VALID_TIME_SAFETY:
            raise LearningEventValidationError(f"Unknown time_safety classification: {self.time_safety!r}")
        if self.leakage_status not in VALID_LEAKAGE_STATUS:
            raise LearningEventValidationError(f"Unknown leakage_status: {self.leakage_status!r}")

        any_allowed = (
            self.analysis_allowed
            or self.shadow_evaluation_allowed
            or self.state_learning_allowed
            or self.model_training_allowed
            or self.promotion_eligible
        )
        if self.ambiguous_join_blocked and any_allowed:
            raise LearningEventValidationError("An ambiguous-join-blocked event cannot have any allow-flag set to True")

        if self.time_safety == TIME_SAFETY_COUNTERFACTUAL_REPLAY and (
            self.state_learning_allowed or self.model_training_allowed or self.promotion_eligible
        ):
            raise LearningEventValidationError(
                "CURRENT_CODE_COUNTERFACTUAL_REPLAY must not be state_learning_allowed, "
                "model_training_allowed, or promotion_eligible"
            )

        if self.time_safety not in SAFE_TIME_SAFETY_CLASSES and self.promotion_eligible:
            raise LearningEventValidationError(
                f"promotion_eligible=True requires a SAFE_* time_safety classification, got {self.time_safety!r}"
            )

        if self.promotion_eligible:
            required = (
                self.state_learning_allowed
                and self.time_safety in SAFE_TIME_SAFETY_CLASSES
                and self.leakage_status == "CLEAN"
                and not self.ambiguous_join_blocked
                and self.result_source_complete
                and self.input_card_hash_verified
                and self.prediction_timestamp_present
                and self.prediction_timestamp_before_off is True
                and self.odds_timestamp_present
                and self.odds_timestamp_before_off is True
                and self.source_commit_present
                and self.model_versions_present
            )
            if not required:
                raise LearningEventValidationError(
                    "promotion_eligible=True requires ALL promotion gates to hold: "
                    "state_learning_allowed, SAFE_* time_safety, leakage_status=CLEAN, "
                    "not ambiguous_join_blocked, result_source_complete, "
                    "input_card_hash_verified, prediction/odds timestamps present and "
                    "before race off, source_commit_present, model_versions_present"
                )


@dataclass(frozen=True)
class LearningEventV2:
    schema_version: str
    prediction: PredictionTruth
    outcome: OutcomeTruth
    context: RaceContext
    safety: SafetyProvenance

    @property
    def event_key(self) -> str:
        """Stable logical identity -- does NOT change when content
        changes. Two events sharing an event_key are different versions
        of "the same slot" (this race, this horse, this selected
        prediction run)."""
        payload = {
            "schema_version": self.schema_version,
            "race_id": self.prediction.race_id,
            "race_date": self.prediction.race_date,
            "subject_horse_id": self.prediction.subject_horse_id,
            "prediction_run_id": self.prediction.prediction_run_id,
        }
        return _sha256_of_obj(payload)

    @property
    def event_content_hash(self) -> str:
        """Full-content hash -- changes whenever ANY material frozen
        truth changes (model score, rank order, result position, winner,
        safety classification, result source content, everything)."""
        return _sha256_of_obj(asdict(self))

    @property
    def event_id(self) -> str:
        """Deterministic combination of the stable logical key and the
        full content hash. Reruns with identical content are idempotent
        (same event_id); a corrected result produces a new event_id
        under the same event_key rather than silently overwriting the
        old one under an unchanged identity."""
        return _sha256_of_obj({"event_key": self.event_key, "event_content_hash": self.event_content_hash})

    def consumption_id(self, *, consumer_name: str, consumer_version: str, target_state: str) -> str:
        return compute_consumption_id(
            event_id=self.event_id,
            consumer_name=consumer_name,
            consumer_version=consumer_version,
            target_state=target_state,
        )

    def content_hash(self) -> str:
        """Backward-compatible alias for event_content_hash."""
        return self.event_content_hash

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["event_key"] = self.event_key
        d["event_content_hash"] = self.event_content_hash
        d["event_id"] = self.event_id
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
