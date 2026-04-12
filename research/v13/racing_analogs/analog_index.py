"""
analog_index.py — Analog Nearest-Neighbor Retrieval
====================================================
Finds the most similar historical runners (analogs) for a query runner.

Modes
-----
  live:
    - Uses real VÉLØ SQPE scores
    - Hard sqpe_band filter enforced
    - Skips runners with sqpe <= 0
    - Min similarity: 0.70

  historical:
    - Uses sqpe_proxy (derived from trainer A/E × base_rate × modifiers)
    - NO hard sqpe_band filter
    - All rows indexed, including sqpe_proxy = 0
    - Soft sqpe proximity scored as 15% weight alongside cosine similarity
    - Percentile normalization applied within the historical population
    - Min combined threshold: 0.55

Stage gates
-----------
  - Stage 1: offline batch on historical data only
  - Stage 2: per-race online lookup (shadow)
  - NOT wired into live VÉLØ ranking

No BSQ optimisation yet — simple cosine on dense vectors.
Index is in-memory during batch; persisted results go to
race_fingerprint_analogs Supabase table.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Callable, List, Optional, Tuple

from .schema import AnalogMatch, CanonicalRaceState, FingerprintVector, Outcome
from .vector_encoder import VectorEncoder


class Mode(str, Enum):
    LIVE = "live"
    HISTORICAL = "historical"


# ─── Score weights ────────────────────────────────────────────────────────────
# historical mode: cosine similarity weighted alongside sqpe proximity
_COSINE_WEIGHT = 0.85
_SQPE_PROXIMITY_WEIGHT = 0.15


class AnalogIndex:
    """
    Nearest-neighbor analog retrieval.

    Two modes:
      - live:       real SQPE + hard band filter (VÉLØ shadow)
      - historical: sqpe_proxy + soft sqpe proximity (Track B backfill)

    Usage:
        idx = AnalogIndex(mode=Mode.HISTORICAL, top_k=20)
        idx.build_index(states)
        matches = idx.query(query_fp)
    """

    def __init__(
        self,
        mode: Mode = Mode.LIVE,
        top_k: int = 20,
        min_similarity: float = 0.70,
    ):
        """
        Args:
            mode:            LIVE or HISTORICAL — changes retrieval behavior
            top_k:           Maximum number of analogs to return per query
            min_similarity:  Minimum combined-score threshold [0.0, 1.0]
        """
        if mode not in (Mode.LIVE, Mode.HISTORICAL):
            raise ValueError(f"mode must be Mode.LIVE or Mode.HISTORICAL, got {mode}")
        self.mode = mode
        self.top_k = top_k
        self.min_similarity = min_similarity
        self._index: List[FingerprintVector] = []
        self._encoder = VectorEncoder()
        # Percentile ranks for sqpe — populated during build_index (historical mode only)
        self._sqpe_percentiles: dict[int, float] = {}

    # ─── Index building ────────────────────────────────────────────────────────

    def build_index(
        self,
        states: List[CanonicalRaceState],
    ) -> int:
        """
        Build the in-memory analog index from a list of CanonicalRaceState.

        Historical mode:
          - All states indexed, including sqpe_proxy = 0
          - Computes sqpe percentile ranks within the population for soft proximity

        Live mode:
          - Skips any state with sqpe <= 0 (no real signal)

        Returns:
            Number of vectors indexed
        """
        self._index = []
        self._sqpe_percentiles = {}

        raw_states = []
        for state in states:
            if self.mode == Mode.LIVE:
                if not state.sqpe or state.sqpe <= 0:
                    continue
            raw_states.append(state)

        for idx, state in enumerate(raw_states):
            fp = self._encoder.encode(state)
            self._index.append(fp)
            # Record sqpe for percentile computation (historical mode)
            if self.mode == Mode.HISTORICAL:
                self._sqpe_percentiles[idx] = state.sqpe

        # Compute percentile ranks for sqpe in historical mode
        if self.mode == Mode.HISTORICAL and self._index:
            self._sqpe_percentiles = self._compute_percentiles(raw_states)

        return len(self._index)

    def _compute_percentiles(
        self, states: List[CanonicalRaceState]
    ) -> dict[int, float]:
        """
        Compute percentile rank of each state's sqpe within the population.

        Returns:
            dict mapping state index → percentile [0.0, 1.0]
        """
        sqpes = [(i, s.sqpe) for i, s in enumerate(states)]
        n = len(sqpes)
        if n == 0:
            return {}

        sorted_sqpes = sorted(sqpes, key=lambda x: x[1])
        percentiles = {}
        for rank, (i, sqpe) in enumerate(sorted_sqpes):
            # percentile = position / n  (0.0 = lowest, 1.0 = highest)
            percentiles[i] = rank / max(n - 1, 1)

        return percentiles

    def index_size(self) -> int:
        return len(self._index)

    # ─── Query ────────────────────────────────────────────────────────────────

    def query(
        self,
        query_fp: FingerprintVector,
        sqpe_band_filter: bool = True,
    ) -> List[AnalogMatch]:
        """
        Find top-k analogs for a query FingerprintVector.

        Mode-specific behavior:

        LIVE:
          - sqpe_band_filter=True enforced (hard filter)
          - cosine similarity only
          - min_similarity threshold applied

        HISTORICAL:
          - sqpe_band_filter ignored (always soft proximity)
          - combined score = 0.85 * cosine + 0.15 * sqpe_proximity
          - sqpe_proximity = 1 - |query_sqpe_percentile - candidate_sqpe_percentile|
          - All candidates considered (no hard band filter)

        Args:
            query_fp:         Encoded query runner
            sqpe_band_filter: Ignored in historical mode; controls filtering in live mode

        Returns:
            List of AnalogMatch (ranked by combined score, descending)
        """
        if not self._index:
            return []

        if self.mode == Mode.LIVE:
            return self._query_live(query_fp, sqpe_band_filter)
        else:
            return self._query_historical(query_fp)

    def _query_live(
        self,
        query_fp: FingerprintVector,
        sqpe_band_filter: bool,
    ) -> List[AnalogMatch]:
        """Live mode query — cosine similarity with optional sqpe band filter."""
        query_band = query_fp.canonical.sqpe_band

        scored = []
        for fp in self._index:
            if sqpe_band_filter and fp.canonical.sqpe_band != query_band:
                continue
            sim = self._cosine(query_fp.vector, fp.vector)
            if sim >= self.min_similarity:
                scored.append((sim, fp))

        scored.sort(key=lambda x: x[0], reverse=True)
        return self._build_matches(query_fp, scored[: self.top_k])

    def _query_historical(
        self,
        query_fp: FingerprintVector,
    ) -> List[AnalogMatch]:
        """
        Historical mode query — cosine + soft sqpe proximity.

        sqpe proximity: closer percentile ranks score higher.
        This means a runner at the 80th percentile sqpe_proxy will match
        other runners near that part of the distribution, regardless of
        their absolute sqpe value.
        """
        # Find query's sqpe percentile
        query_sqpe = query_fp.canonical.sqpe
        query_percentile = self._sqpe_percentile_of_value(query_sqpe)

        scored = []
        for idx, fp in enumerate(self._index):
            cos_sim = self._cosine(query_fp.vector, fp.vector)

            # Soft sqpe proximity (0.0 = farthest, 1.0 = identical percentile)
            if idx in self._sqpe_percentiles and query_percentile is not None:
                cand_percentile = self._sqpe_percentiles[idx]
                sqpe_proximity = 1.0 - abs(query_percentile - cand_percentile)
            else:
                sqpe_proximity = 0.0  # no sqpe data for either side

            # Combined score
            combined = (
                _COSINE_WEIGHT * cos_sim
                + _SQPE_PROXIMITY_WEIGHT * sqpe_proximity
            )

            if combined >= self.min_similarity:
                scored.append((combined, cos_sim, sqpe_proximity, fp))

        scored.sort(key=lambda x: x[0], reverse=True)
        return self._build_matches_historical(scored[: self.top_k])

    def _sqpe_percentile_of_value(self, sqpe: float) -> Optional[float]:
        """Return the percentile rank of a sqpe value within the indexed population."""
        if not self._sqpe_percentiles or sqpe <= 0:
            return None
        # Count how many indexed runners have sqpe <= this value
        le_count = sum(1 for i in self._sqpe_percentiles if self._sqpe_percentiles[i] <= sqpe)
        n = len(self._sqpe_percentiles)
        return le_count / n if n > 0 else None

    def query_from_state(
        self,
        state: CanonicalRaceState,
        sqpe_band_filter: bool = True,
    ) -> List[AnalogMatch]:
        """
        Convenience: query from a CanonicalRaceState directly.
        Encodes then searches.
        """
        fp = self._encoder.encode(state)
        return self.query(fp, sqpe_band_filter=sqpe_band_filter)

    # ─── Match building ───────────────────────────────────────────────────────

    def _build_matches(
        self,
        query_fp: FingerprintVector,
        scored: List[Tuple[float, FingerprintVector]],
    ) -> List[AnalogMatch]:
        matches = []
        for rank, (sim, fp) in enumerate(scored, start=1):
            analog = fp.canonical
            outcome = analog.to_outcome() if analog else None
            matches.append(AnalogMatch(
                race_id=query_fp.race_id,
                runner_id=query_fp.runner_id,
                analog_race_id=analog.race_id,
                analog_runner_id=analog.runner_id,
                similarity_score=round(sim, 4),
                rank=rank,
                analog_sqpe=analog.sqpe if analog else None,
                analog_sqpe_band=analog.sqpe_band.value if analog and analog.sqpe_band else None,
                analog_sp_band=analog.sp_band.value if analog and analog.sp_band else None,
                outcome=outcome,
                analog_win=analog.win if analog else None,
                analog_placed=analog.placed if analog else None,
                analog_finish=analog.finish_position if analog else None,
                analog_sp=analog.sp if analog else None,
            ))
        return matches

    def _build_matches_historical(
        self,
        scored: List[Tuple[float, float, float, FingerprintVector]],
    ) -> List[AnalogMatch]:
        """
        Build AnalogMatch objects from historical mode scored results.
        scored entries: (combined_score, cosine_sim, sqpe_proximity, fp)
        """
        matches = []
        for rank, (combined, cos_sim, sqpe_prox, fp) in enumerate(scored, start=1):
            analog = fp.canonical
            outcome = analog.to_outcome() if analog else None
            matches.append(AnalogMatch(
                race_id=fp.race_id,
                runner_id=fp.runner_id,
                analog_race_id=analog.race_id,
                analog_runner_id=analog.runner_id,
                similarity_score=round(combined, 4),
                rank=rank,
                analog_sqpe=analog.sqpe if analog else None,
                analog_sqpe_band=analog.sqpe_band.value if analog and analog.sqpe_band else None,
                analog_sp_band=analog.sp_band.value if analog and analog.sp_band else None,
                outcome=outcome,
                analog_win=analog.win if analog else None,
                analog_placed=analog.placed if analog else None,
                analog_finish=analog.finish_position if analog else None,
                analog_sp=analog.sp if analog else None,
            ))
        return matches

    # ─── Persistence helpers ──────────────────────────────────────────────────

    @staticmethod
    def cosine_between(a: FingerprintVector, b: FingerprintVector) -> float:
        """Compute cosine similarity between two FingerprintVectors."""
        return AnalogIndex._cosine(a.vector, b.vector)

    @staticmethod
    def _cosine(vec_a: List[float], vec_b: List[float]) -> float:
        """Cosine similarity between two vectors."""
        dot = sum(ac * bc for ac, bc in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(ac * ac for ac in vec_a))
        norm_b = math.sqrt(sum(bc * bc for bc in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)
