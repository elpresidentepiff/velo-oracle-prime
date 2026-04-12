"""
vector_encoder.py — Fingerprint Vector Encoder
=============================================
Converts CanonicalRaceState into a fixed-length dense vector.

Encoding strategy:
  - Numeric features: min-max normalised to [0.0, 1.0]
  - Categorical features: one-hot with known categories
  - Ordinal features: integer rank scaled to [0.0, 1.0]

Output dimension: 42
  Indices 0-7:   sqpe bins (8 bands)
  Indices 8-14:  sp_band one-hot (7 categories)
  Indices 15-17: trainer_ae bins + null flag (3)
  Index 18:      trainer_signal_type ordinal
  Index 19:      class_movement_subtype ordinal
  Indices 20-24: days_since_run_band one-hot (5)
  Index 25:      run_cycle_position ordinal
  Index 26:      distance_change_band ordinal
  Index 27:      going_band ordinal
  Index 28:      recent_form_state ordinal
  Index 29:      finish_consistency_band ordinal
  Indices 30-41: sqpe raw percentile (12 buckets, 0.0-1.0 from sqpe value)

RULES:
  - No BSQ (bounded sub-quadratic encoding) yet — use simple normalisation
  - All vectors are deterministic (no randomness)
  - Null/missing values encoded as 0.0 with null_flag = 1
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from .schema import (
    CanonicalRaceState,
    FingerprintVector,
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


class VectorEncoder:
    """
    Encodes CanonicalRaceState into a 42-dim FingerprintVector.

    Usage:
        encoder = VectorEncoder()
        fp = encoder.encode(state)
    """

    DIM = 42

    # ─── SQPE band binning ────────────────────────────────────────────────────
    SQPE_EDGES = [0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 1.0]
    # 8 bins for one-hot

    # ─── SP band ordinal mapping ──────────────────────────────────────────────
    SP_BAND_ORDER = {
        SPBand.SHORT:     0,
        SPBand.FAVOURITE: 1,
        SPBand.MID:       2,
        SPBand.LONG:      3,
        SPBand.OUTLIER:   4,
    }

    # ─── Trainer signal ordinal ────────────────────────────────────────────────
    TRAINER_SIGNAL_ORDER = {
        TrainerSignalType.DECLINING:  0,
        TrainerSignalType.UNKNOWN:     1,
        TrainerSignalType.CONSISTENT: 2,
        TrainerSignalType.IMPROVER:   3,
    }

    # ─── Class movement ordinal ────────────────────────────────────────────────
    # DECLINING doesn't exist in ClassMovementSubtype; DROP is the negative signal
    CLASS_MOVEMENT_ORDER = {
        ClassMovementSubtype.DROP:            0,
        ClassMovementSubtype.ENGINEERED_DROP:  1,
        ClassMovementSubtype.UNKNOWN:          2,
        ClassMovementSubtype.SAME:            3,
        ClassMovementSubtype.RISE:            4,
    }

    # ─── Days since run band one-hot (5 categories) ────────────────────────────
    DAYS_BAND_ORDER = [
        DaysSinceRunBand.VERY_QUICK,   # index 0
        DaysSinceRunBand.QUICK_5_7,    # index 1
        DaysSinceRunBand.NORMAL_8_14,  # index 2
        DaysSinceRunBand.LAYOFF_14_30, # index 3
        DaysSinceRunBand.LAYOFF_30PLUS,# index 4
    ]

    # ─── Run cycle ordinal ─────────────────────────────────────────────────────
    RUN_CYCLE_ORDER = {
        RunCyclePosition.DROUGHT:  0,
        RunCyclePosition.LATE:    1,
        RunCyclePosition.MID:     2,
        RunCyclePosition.PEAK:    3,
        RunCyclePosition.EARLY:   4,
    }

    # ─── Distance change ordinal ───────────────────────────────────────────────
    DISTANCE_ORDER = {
        DistanceChangeBand.SAME:            0,
        DistanceChangeBand.DOWN:            1,
        DistanceChangeBand.UP:              2,
        DistanceChangeBand.SIGNIFICANT_DOWN: 3,
        DistanceChangeBand.SIGNIFICANT_UP:   4,
    }

    # ─── Going ordinal ─────────────────────────────────────────────────────────
    GOING_ORDER = {
        GoingBand.FIRM:     0,
        GoingBand.STANDARD: 1,
        GoingBand.SOFT:     2,
        GoingBand.HEAVY:    3,
        GoingBand.UNKNOWN:  4,
    }

    # ─── Recent form ordinal ───────────────────────────────────────────────────
    FORM_ORDER = {
        RecentFormState.DECLINING:  0,
        RecentFormState.MIXED:       1,
        RecentFormState.UNTESTED:    2,
        RecentFormState.CONSISTENT:  3,
        RecentFormState.IMPROVING:   4,
    }

    # ─── Finish consistency ordinal ────────────────────────────────────────────
    FINISH_ORDER = {
        FinishConsistencyBand.VARIABLE:   0,
        FinishConsistencyBand.AVERAGE:     1,
        FinishConsistencyBand.UNTESTED:    2,
        FinishConsistencyBand.CONSISTENT:  3,
    }

    def encode(self, state: CanonicalRaceState) -> FingerprintVector:
        """
        Encode a CanonicalRaceState into a FingerprintVector.

        Returns:
            FingerprintVector with 42-dim vector
        """
        vec = [0.0] * self.DIM

        # ── 0-7: SQPE band one-hot (8 bins) ─────────────────────────────
        sqpe_idx = self._sqpe_bin(float(state.sqpe))
        if 0 <= sqpe_idx < 8:
            vec[sqpe_idx] = 1.0

        # ── 8-14: SP band one-hot (7 categories) ────────────────────────
        sp_idx = self._sp_onehot(state.sp_band)
        if 0 <= sp_idx < 7:
            vec[8 + sp_idx] = 1.0

        # ── 15-17: Trainer A/E bins + null flag ─────────────────────────
        ae_bins = self._trainer_ae_bins(state.trainer_ae)
        vec[15] = ae_bins  # 0.0 = null, else 0.33/0.66/1.0

        # ── 18: Trainer signal type ordinal (normalised) ─────────────────
        vec[18] = self._ordinal(
            state.trainer_signal_type,
            self.TRAINER_SIGNAL_ORDER,
            default=1,
        ) / 3.0

        # ── 19: Class movement ordinal (normalised) ──────────────────────
        vec[19] = self._ordinal(
            state.class_movement_subtype,
            self.CLASS_MOVEMENT_ORDER,
            default=1,
        ) / 4.0

        # ── 20-24: Days since run band one-hot (5) ───────────────────────
        days_idx = self._days_onehot(state.days_since_run_band)
        if 0 <= days_idx < 5:
            vec[20 + days_idx] = 1.0

        # ── 25: Run cycle ordinal ─────────────────────────────────────────
        vec[25] = self._ordinal(
            state.run_cycle_position,
            self.RUN_CYCLE_ORDER,
            default=2,
        ) / 4.0

        # ── 26: Distance change ordinal ───────────────────────────────────
        vec[26] = self._ordinal(
            state.distance_change_band,
            self.DISTANCE_ORDER,
            default=0,
        ) / 4.0

        # ── 27: Going ordinal ─────────────────────────────────────────────
        vec[27] = self._ordinal(
            state.going_band,
            self.GOING_ORDER,
            default=4,
        ) / 4.0

        # ── 28: Recent form ordinal ───────────────────────────────────────
        vec[28] = self._ordinal(
            state.recent_form_state,
            self.FORM_ORDER,
            default=2,
        ) / 4.0

        # ── 29: Finish consistency ordinal ─────────────────────────────────
        vec[29] = self._ordinal(
            state.finish_consistency_band,
            self.FINISH_ORDER,
            default=2,
        ) / 3.0

        # ── 30-41: SQPE raw value percentile (12 buckets) ─────────────────
        sqpe_val = float(state.sqpe)
        for i, (lo, hi) in enumerate(zip(self.SQPE_EDGES[:-1], self.SQPE_EDGES[1:])):
            if lo <= sqpe_val < hi:
                # Normalise position within bucket
                bucket_width = hi - lo
                if bucket_width > 0:
                    vec[30 + i] = (sqpe_val - lo) / bucket_width
                else:
                    vec[30 + i] = 0.5
                break
        else:
            # Edge case: sqpe = 1.0 goes in last bucket
            if sqpe_val >= 1.0:
                vec[41] = 1.0

        return FingerprintVector(
            race_id=state.race_id,
            runner_id=state.runner_id,
            canonical=state,
            vector=vec,
            created_at=datetime.utcnow().isoformat() + "Z",
        )

    @staticmethod
    def _sqpe_bin(sqpe: float) -> int:
        """Map sqpe value to band index 0-7."""
        edges = [0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 1.0]
        for i, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
            if lo <= sqpe < hi:
                return i
        if sqpe >= 1.0:
            return 7
        return 0

    @staticmethod
    def _sp_onehot(sp_band) -> int:
        """Map SP band to one-hot index 0-6."""
        mapping = {
            SPBand.SHORT:     0,
            SPBand.FAVOURITE: 1,
            SPBand.MID:       2,
            SPBand.LONG:      3,
            SPBand.OUTLIER:   4,
        }
        # SPBand.OTHER would be 5, but we only have MID=2 for Phase 3.5
        return mapping.get(sp_band, 2)

    @staticmethod
    def _trainer_ae_bins(ae: float | None) -> float:
        """
        Encode trainer A/E as a scalar in [0.0, 1.0].
        None -> 0.0 (null flag handled separately if needed).
        """
        if ae is None:
            return 0.0
        # 0.70 -> 0.0, 1.05 -> ~0.5, 1.40 -> 1.0
        return max(0.0, min(1.0, (float(ae) - 0.70) / 0.70))

    @staticmethod
    def _ordinal(enum_val, order_map: dict, default: int = 0) -> int:
        """Encode any Enum as ordinal using order_map."""
        if enum_val is None:
            return default
        key = str(enum_val.value) if hasattr(enum_val, "value") else str(enum_val)
        return order_map.get(key, default)

    @staticmethod
    def _days_onehot(band) -> int:
        """Map days_since_run band to one-hot index 0-4."""
        if band is None:
            return 2  # default to NORMAL_8_14
        band_order = [
            DaysSinceRunBand.VERY_QUICK,
            DaysSinceRunBand.QUICK_5_7,
            DaysSinceRunBand.NORMAL_8_14,
            DaysSinceRunBand.LAYOFF_14_30,
            DaysSinceRunBand.LAYOFF_30PLUS,
        ]
        try:
            return band_order.index(band)
        except ValueError:
            return 2
