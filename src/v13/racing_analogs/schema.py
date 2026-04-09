"""
schema.py — Canonical state dataclasses
========================================
Defines the canonical race state and all typed output structures
used across the analog sidecar.

All dataclasses are pure data — no logic, no DB access.

Canonical shape
---------------
One CanonicalRaceState represents one runner in one race.
It is the single unified input format consumed by
vector_encoder.py, analog_index.py, and analog_summary.py.

Feature set: LOCKED to fingerprint_v1 (13 features)
- sqpe, sqpe_band, sp_band
- trainer_ae, trainer_ae_band, trainer_signal_type
- class_movement_subtype, days_since_run_band, run_cycle_position
- distance_change_band, going_band
- recent_form_state, finish_consistency_band

Metadata: race_id, runner_id, race_date, course, region
Outcome (optional): win, placed, finish_position, sp, winner_id
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional


# ─── Bands / Enumerated Types ────────────────────────────────────────────────

class SQPEBand(str, Enum):
    VERY_LOW  = "very_low"    # < 0.30
    LOW       = "low"         # 0.30–0.40
    MEDIUM    = "medium"      # 0.40–0.50
    SWEET     = "sweet"        # 0.50–0.60  ← Phase 3.5 confirmed sweet spot
    HIGH      = "high"        # 0.60–0.70
    VERY_HIGH = "very_high"   # > 0.70

    @classmethod
    def from_sqpe(cls, sqpe: float) -> SQPEBand:
        if sqpe < 0.30:  return cls.VERY_LOW
        if sqpe < 0.40:  return cls.LOW
        if sqpe < 0.50:  return cls.MEDIUM
        if sqpe <= 0.60: return cls.SWEET
        if sqpe <= 0.70: return cls.HIGH
        return cls.VERY_HIGH


class SPBand(str, Enum):
    SHORT     = "short"   # < 3.0
    FAVOURITE = "favourite"  # 3.0–5.0
    MID       = "mid"    # 5.0–13.0  ← Phase 3.5 sweet spot
    LONG      = "long"   # 13.0–21.0
    OUTLIER   = "outlier"  # > 21.0

    @classmethod
    def from_sp(cls, sp: float) -> SPBand:
        if sp < 3.0:   return cls.SHORT
        if sp <= 5.0:  return cls.FAVOURITE
        if sp <= 13.0: return cls.MID
        if sp <= 21.0: return cls.LONG
        return cls.OUTLIER


class TrainerSignalType(str, Enum):
    IMPROVER   = "improver"
    CONSISTENT = "consistent"
    DECLINING  = "declining"
    UNKNOWN    = "unknown"


class ClassMovementSubtype(str, Enum):
    RISE             = "rise"
    SAME             = "same"
    DROP             = "drop"
    ENGINEERED_DROP  = "engineered_drop"  # tutor-coded specific pattern
    UNKNOWN          = "unknown"


class DaysSinceRunBand(str, Enum):
    LAYOFF_30PLUS = "layoff_30plus"  # > 30 days — high risk
    LAYOFF_14_30  = "layoff_14_30"
    NORMAL_8_14   = "normal_8_14"     # ← sweet spot
    QUICK_5_7     = "quick_5_7"
    VERY_QUICK    = "very_quick"      # < 5 days

    @classmethod
    def from_days(cls, days: int) -> DaysSinceRunBand:
        if days < 5:   return cls.VERY_QUICK
        if days <= 7:  return cls.QUICK_5_7
        if days <= 14: return cls.NORMAL_8_14
        if days <= 30: return cls.LAYOFF_14_30
        return cls.LAYOFF_30PLUS


class RunCyclePosition(str, Enum):
    EARLY    = "early"   # first run of cycle
    MID      = "mid"     # middle of cycle
    PEAK     = "peak"    # peak fitness window
    LATE     = "late"    # past peak, fitness fading
    DROUGHT  = "drought" # long spell, rusty


class DistanceChangeBand(str, Enum):
    SAME       = "same"
    UP         = "up"
    DOWN       = "down"
    SIGNIFICANT_UP = "significant_up"
    SIGNIFICANT_DOWN = "significant_down"


class GoingBand(str, Enum):
    STANDARD  = "standard"
    FIRM      = "firm"
    SOFT      = "soft"
    HEAVY     = "heavy"
    UNKNOWN   = "unknown"


class RecentFormState(str, Enum):
    IMPROVING   = "improving"
    CONSISTENT  = "consistent"
    DECLINING   = "declining"
    UNTESTED    = "untested"   # maiden or no recent runs
    MIXED       = "mixed"


class FinishConsistencyBand(str, Enum):
    CONSISTENT = "consistent"   # narrow variance in finishing positions
    AVERAGE    = "average"
    VARIABLE   = "variable"    # wide variance — unpredictable
    UNTESTED   = "untested"


class Region(str, Enum):
    UK    = "uk"
    IRELAND = "ireland"
    AW    = "aw"        # All-Weather (UK)
    UAE   = "uae"       # Dubai/Meydan
    HK    = "hk"        # Hong Kong
    USA   = "usa"
    OTHER = "other"


class Outcome(str, Enum):
    WIN     = "WIN"
    PLACED  = "PLACED"
    MISS    = "MISS"
    NR      = "NR"       # non-runner / reserve


class Confidence(str, Enum):
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


# ─── Core Canonical State ────────────────────────────────────────────────────

@dataclass
class CanonicalRaceState:
    """
    Canonical representation of one runner in one race.

    Used as:
    - Input to vector_encoder.py (produces FingerprintVector)
    - Lookup key for analog_index.py
    - Basis for analog_summary.py aggregation
    """
    race_id:          str
    runner_id:        str
    race_date:        date
    course:           str
    region:           Region

    # ── 13 locked fingerprint features ────────────────────────────
    sqpe:                    float    # SQPE probability score
    sqpe_band:               SQPEBand
    sp_band:                 SPBand
    trainer_ae:              float    # trainer A/E (or null if unavailable)
    trainer_ae_band:         str      # banded version of trainer_ae
    trainer_signal_type:     TrainerSignalType
    class_movement_subtype:  ClassMovementSubtype
    days_since_run_band:     DaysSinceRunBand
    run_cycle_position:      RunCyclePosition
    distance_change_band:    DistanceChangeBand
    going_band:              GoingBand
    recent_form_state:       RecentFormState
    finish_consistency_band: FinishConsistencyBand

    # ── Outcome (optional — only populated post-race) ───────────
    win:             Optional[bool]  = None
    placed:          Optional[bool] = None
    finish_position: Optional[int]  = None
    sp:              Optional[float] = None  # Betfair SP decimal
    winner_id:       Optional[str]  = None

    # ── Lineage ──────────────────────────────────────────────────
    feature_version:  str = "fingerprint_v1"
    signal_version:   str = "phase35_locked"

    def to_outcome(self) -> Optional[Outcome]:
        """Derive Outcome enum from post-race data."""
        if self.win is True:
            return Outcome.WIN
        if self.placed is True:
            return Outcome.PLACED
        if self.finish_position is not None:
            return Outcome.MISS
        return Outcome.NR

    def is_bet_candidate(self) -> bool:
        """
        Phase 3.5 signal gate.
        Returns True if runner passes the locked fingerprint filter:
        - sqpe >= 0.50
        - trainer_ae >= 1.05 (if available)
        - sp in [5.0, 13.0]
        """
        if self.sqpe < 0.50:
            return False
        if self.sp_band not in (SPBand.MID,):
            return False
        if self.trainer_ae is not None and self.trainer_ae < 1.05:
            return False
        return True

    def __post_init__(self):
        """Normalise enum fields from strings if needed."""
        def _enum(ecls, val):
            if isinstance(val, ecls):
                return val
            if val is None:
                return None
            try:
                return ecls(val)
            except ValueError:
                return None

        self.sqpe_band              = _enum(SQPEBand, self.sqpe_band)              or SQPEBand.MEDIUM
        self.sp_band                = _enum(SPBand, self.sp_band)                  or SPBand.MID
        self.trainer_signal_type     = _enum(TrainerSignalType, self.trainer_signal_type) or TrainerSignalType.UNKNOWN
        self.class_movement_subtype  = _enum(ClassMovementSubtype, self.class_movement_subtype) or ClassMovementSubtype.UNKNOWN
        self.days_since_run_band     = _enum(DaysSinceRunBand, self.days_since_run_band) or DaysSinceRunBand.NORMAL_8_14
        self.run_cycle_position      = _enum(RunCyclePosition, self.run_cycle_position) or RunCyclePosition.MID
        self.distance_change_band    = _enum(DistanceChangeBand, self.distance_change_band) or DistanceChangeBand.SAME
        self.going_band              = _enum(GoingBand, self.going_band) or GoingBand.UNKNOWN
        self.recent_form_state      = _enum(RecentFormState, self.recent_form_state) or RecentFormState.UNTESTED
        self.finish_consistency_band = _enum(FinishConsistencyBand, self.finish_consistency_band) or FinishConsistencyBand.UNTESTED
        self.region                  = _enum(Region, self.region) or Region.OTHER


# ─── Fingerprint Vector ───────────────────────────────────────────────────────

@dataclass
class FingerprintVector:
    """
    Dense fixed-length vector representation of a CanonicalRaceState.
    Used for nearest-neighbor similarity search.

    Encoding:
    - Numeric features: min-max normalised to [0.0, 1.0]
    - Categorical features: one-hot encoded with known categories

    Vector dimension: 42
      0-7:   sqpe bins (8 bands)
      8-14:  sp_band one-hot (7 categories)
      15-17: trainer_ae bins (low/mid/high + null flag)
      18:    trainer_signal_type ordinal
      19:    class_movement_subtype ordinal
      20-24: days_since_run_band one-hot (5)
      25:    run_cycle_position ordinal
      26:    distance_change_band ordinal
      27:    going_band ordinal
      28:    recent_form_state ordinal
      29:    finish_consistency_band ordinal
      30-41: sqpe raw (12 percentile buckets)
    """
    race_id:        str
    runner_id:      str
    canonical:      CanonicalRaceState
    vector:         List[float]    # length = 42
    created_at:     str             # ISO 8601

    def similarity(self, other: FingerprintVector) -> float:
        """Cosine similarity between two fingerprint vectors."""
        import math
        dot = sum(a * b for a, b in zip(self.vector, other.vector))
        norm_a = math.sqrt(sum(a * a for a in self.vector))
        norm_b = math.sqrt(sum(b * b for b in other.vector))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# ─── Analog Match ─────────────────────────────────────────────────────────────

@dataclass
class AnalogMatch:
    """
    A single historical runner that is similar to the query runner.
    Produced by analog_index.py.
    """
    # Query identity
    race_id:       str
    runner_id:     str

    # Analog identity
    analog_race_id:    str
    analog_runner_id:  str

    # Similarity
    similarity_score: float  # cosine similarity [0.0, 1.0]
    rank:             int   # 1 = closest

    # Analog features (for summary)
    analog_sqpe:      Optional[float] = None
    analog_sqpe_band: Optional[str]   = None
    analog_sp_band:   Optional[str]   = None

    # Outcome
    outcome:          Optional[Outcome]  = None
    analog_win:       Optional[bool]   = None
    analog_placed:    Optional[bool]   = None
    analog_finish:    Optional[int]    = None
    analog_sp:        Optional[float]  = None


# ─── Analog Summary ──────────────────────────────────────────────────────────

@dataclass
class AnalogSummary:
    """
    Aggregated statistics over all analog matches for one runner.
    Produced by analog_summary.py.
    """
    race_id:         str
    runner_id:       str

    analog_count:    int      = 0
    analog_win_rate: float    = 0.0
    analog_place_rate: float  = 0.0
    analog_ae:       float    = 0.0  # actual/expected vs. modelled
    analog_roi:      float    = 0.0  # from SP if tracked
    top_similarity:  float    = 0.0

    # Per-analog outcome detail
    matches:         List[AnalogMatch] = field(default_factory=list)

    def to_signal_summary_dict(self) -> dict:
        """Convert to dict matching fingerprint_signal_summary table columns."""
        return {
            "race_id":          self.race_id,
            "runner_id":        self.runner_id,
            "analog_count":     self.analog_count,
            "analog_win_rate":  round(self.analog_win_rate, 4),
            "analog_place_rate": round(self.analog_place_rate, 4),
            "analog_ae":        round(self.analog_ae, 4),
            "analog_roi":       round(self.analog_roi, 4),
        }


# ─── Advisory Output ─────────────────────────────────────────────────────────

@dataclass
class AdvisoryOutput:
    """
    Final advisory output from the analog sidecar.
    Written to fingerprint_signal_summary by shadow_runner.py.

    This is the ONLY output exposed to VÉLØ at Stage 2+.
    It does NOT change VÉLØ rankings. It is logged and stored only.
    """
    race_id:        str
    runner_id:      str

    # VÉLØ baseline
    velo_sqpe:      float
    velo_prob:      float
    velo_tier:      str    # A | B | C | D | X

    # Analog signal
    analog_count:    int
    analog_win_rate: float
    analog_place_rate: float
    analog_ae:      float
    analog_roi:     float
    top_similarity: float

    # Advisory
    confidence:     Confidence
    warnings:       List[str]
    explanation:    str

    # Gate
    shadow_only:    bool = True   # always True until Stage 4
    feature_version: str = "fingerprint_v1"
    signal_version: str = "phase35_locked"

    def to_db_dict(self) -> dict:
        # Numeric confidence: HIGH=1.0, MEDIUM=0.6, LOW=0.3
        _confidence_map = {"high": 1.0, "medium": 0.6, "low": 0.3}
        confidence_numeric = _confidence_map.get(self.confidence.value, 0.0)
        return {
            "race_id":            self.race_id,
            "runner_id":          self.runner_id,
            "analog_count":       self.analog_count,
            "analog_win_rate":    round(self.analog_win_rate, 4),
            "analog_place_rate":  round(self.analog_place_rate, 4),
            "analog_ae":          round(self.analog_ae, 4),
            "analog_roi":         round(self.analog_roi, 4),
            "confidence_score":   round(confidence_numeric, 4),
            # NOTE: top_similarity NOT included — column does not exist in live table
            "confidence":         self.confidence.value,
            "warnings":          self.warnings,
            "explanation":       self.explanation,
            "shadow_only":       self.shadow_only,
            "feature_version":   self.feature_version,
            "signal_version":    self.signal_version,
        }
