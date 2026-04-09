"""
fingerprint_features.py — Feature Extraction
============================================
Builds the 13-feature fingerprint input from CanonicalRaceState.

This module is the ONLY place where feature extraction logic lives.
If the feature spec changes, it changes here and ONLY here.

LOCKED FEATURE SET (fingerprint_v1):
  Core:        sqpe | sqpe_band | sp_band
  Trainer:     trainer_ae | trainer_ae_band | trainer_signal_type
  Setup:       class_movement_subtype | days_since_run_band
               run_cycle_position | distance_change_band | going_band
  Horse state: recent_form_state | finish_consistency_band

RULES:
  - No feature expansion without explicit Phase 3.5 approval
  - All band assignments use Phase 3.5 boundaries only
  - Missing values map to explicit "no_data" tokens — never NaN
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .schema import (
    CanonicalRaceState,
    DaysSinceRunBand,
    DistanceChangeBand,
    FinishConsistencyBand,
    GoingBand,
    RecentFormState,
    Region,
    RunCyclePosition,
    SPBand,
    SQPEBand,
    TrainerSignalType,
    ClassMovementSubtype,
)


class FingerprintFeatureBuilder:
    """
    Extracts the 13 locked fingerprint features from a CanonicalRaceState.

    Usage:
        builder = FingerprintFeatureBuilder()
        features = builder.build(state)  # -> dict
    """

    # Phase 3.5 SQPE bands (boundaries locked)
    SQPE_BOUNDARIES = [0.30, 0.40, 0.50, 0.60, 0.70]

    # Phase 3.5 SP bands
    SP_FAVOURITE_UPPER = 5.0
    SP_MID_UPPER       = 13.0
    SP_LONG_UPPER      = 21.0

    # Phase 3.5 trainer A/E threshold
    TRAINER_AE_THRESHOLD = 1.05

    def build(self, state: CanonicalRaceState) -> Dict[str, Any]:
        """
        Build the 13-feature fingerprint dict.

        Returns:
            dict with keys matching race_fingerprint_vectors columns
        """
        return {
            # Core
            "sqpe":          round(float(state.sqpe), 4),
            "sqpe_band":     state.sqpe_band.value if state.sqpe_band else SQPEBand.MEDIUM.value,
            "sp_band":       state.sp_band.value if state.sp_band else SPBand.MID.value,

            # Trainer
            "trainer_ae":    round(float(state.trainer_ae), 4) if state.trainer_ae is not None else None,
            "trainer_ae_band": str(state.trainer_ae_band) if state.trainer_ae_band else "no_data",
            "trainer_signal_type": state.trainer_signal_type.value if state.trainer_signal_type else TrainerSignalType.UNKNOWN.value,

            # Setup
            "class_movement_subtype": state.class_movement_subtype.value if state.class_movement_subtype else ClassMovementSubtype.UNKNOWN.value,
            "days_since_run_band":   state.days_since_run_band.value if state.days_since_run_band else DaysSinceRunBand.NORMAL_8_14.value,
            "run_cycle_position":    state.run_cycle_position.value if state.run_cycle_position else RunCyclePosition.MID.value,
            "distance_change_band":   state.distance_change_band.value if state.distance_change_band else DistanceChangeBand.SAME.value,
            "going_band":            state.going_band.value if state.going_band else GoingBand.UNKNOWN.value,

            # Horse state
            "recent_form_state":       state.recent_form_state.value if state.recent_form_state else RecentFormState.UNTESTED.value,
            "finish_consistency_band":  state.finish_consistency_band.value if state.finish_consistency_band else FinishConsistencyBand.UNTESTED.value,

            # Lineage
            "feature_version": state.feature_version,
            "signal_version":  state.signal_version,
        }

    def is_bet_candidate(self, state: CanonicalRaceState) -> bool:
        """
        Phase 3.5 signal gate (same as CanonicalRaceState.is_bet_candidate).

        Applies the three hard filters:
          1. sqpe >= 0.50
          2. trainer_ae >= 1.05 (if available)
          3. sp_band in [mid] i.e. SP 5-13
        """
        if state.sqpe < 0.50:
            return False
        if state.sp_band not in (SPBand.MID,):
            return False
        if state.trainer_ae is not None and state.trainer_ae < self.TRAINER_AE_THRESHOLD:
            return False
        return True

    def sqpe_threshold(self) -> float:
        return 0.50

    def trainer_ae_threshold(self) -> float:
        return self.TRAINER_AE_THRESHOLD

    def sp_range(self) -> tuple[float, float]:
        return (5.0, 13.0)
