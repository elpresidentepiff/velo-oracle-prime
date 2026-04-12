"""
analog_summary.py — Analog Aggregation + Advisory Output
======================================================
Aggregates a list of AnalogMatch into an AnalogSummary
and produces the final AdvisoryOutput for a runner.

Advisory rules (Phase 3.5 aligned):
  - confidence HIGH: analog_count >= 10 AND analog_win_rate >= 0.22 AND analog_ae >= 1.20
  - confidence MEDIUM: analog_count >= 5 AND analog_win_rate >= 0.15
  - confidence LOW: everything else (including low analog count)

Warning flags:
  - low_analog_count: analog_count < 5
  - regime_mismatch: SQPE band not in sweet spot
  - low_similarity: top_similarity < 0.75
  - no_turf_edge: trainer A/E < 1.05
  - market_overlay: SP short (favourite)

Stage gate:
  - shadow_only is always True until Stage 4 promotion
  - No VÉLØ ranking modification
"""

from __future__ import annotations

from typing import List, Optional

from .schema import (
    AdvisoryOutput,
    AnalogMatch,
    AnalogSummary,
    Confidence,
    FingerprintVector,
)


# ─── Thresholds (Phase 3.5 aligned) ──────────────────────────────────────────

ANALOG_COUNT_HIGH   = 10
ANALOG_WIN_RATE_HIGH = 0.22
ANALOG_AE_HIGH      = 1.20

ANALOG_COUNT_MEDIUM = 5
ANALOG_WIN_RATE_MEDIUM = 0.15

MIN_SIMILARITY_WARN = 0.75
TRAINER_AE_MIN      = 1.05


class AnalogSummaryBuilder:
    """
    Aggregates analog matches into summary statistics
    and produces the AdvisoryOutput for a runner.

    Usage:
        builder = AnalogSummaryBuilder()
        summary = builder.build(query_fp, matches)
        advisory = builder.to_advisory(query_fp, summary)
    """

    def build(
        self,
        query_fp: FingerprintVector,
        matches: List[AnalogMatch],
    ) -> AnalogSummary:
        """
        Build AnalogSummary from query FingerprintVector and its analogs.

        Args:
            query_fp: The query runner's FingerprintVector
            matches: List of AnalogMatch from AnalogIndex.query()
        """
        if not matches:
            return AnalogSummary(
                race_id=query_fp.race_id,
                runner_id=query_fp.runner_id,
                analog_count=0,
                analog_win_rate=0.0,
                analog_place_rate=0.0,
                analog_ae=0.0,
                analog_roi=0.0,
                top_similarity=0.0,
                matches=[],
            )

        n = len(matches)
        wins    = sum(1 for m in matches if m.analog_win is True)
        placed  = sum(1 for m in matches if m.analog_placed is True)

        # A/E: wins / expected_wins
        # Expected wins = n * base_rate (use 0.10 as baseline for racing)
        expected_wins = n * 0.10
        ae = (wins / expected_wins) if expected_wins > 0 else 0.0

        # ROI: assume level-stake from SP (simplified)
        # For placed runners, estimate ROI from SP
        roi = self._estimate_roi(matches)

        win_rate   = wins / n
        place_rate = placed / n
        top_sim    = max(m.similarity_score for m in matches)

        return AnalogSummary(
            race_id=query_fp.race_id,
            runner_id=query_fp.runner_id,
            analog_count=n,
            analog_win_rate=win_rate,
            analog_place_rate=place_rate,
            analog_ae=ae,
            analog_roi=roi,
            top_similarity=top_sim,
            matches=matches,
        )

    def to_advisory(
        self,
        query_fp: FingerprintVector,
        summary: AnalogSummary,
    ) -> AdvisoryOutput:
        """
        Convert AnalogSummary to AdvisoryOutput.

        This is the ONLY output exposed from the sidecar.
        All fields are advisory — VÉLØ rankings are NOT modified.
        """
        velo = query_fp.canonical
        warnings = self._build_warnings(velo, summary)

        confidence = self._classify_confidence(summary)
        explanation = self._explain(velo, summary, warnings)

        return AdvisoryOutput(
            race_id=velo.race_id,
            runner_id=velo.runner_id,
            velo_sqpe=float(velo.sqpe),
            velo_prob=float(velo.sqpe),  # sqpe as prob proxy
            velo_tier=self._velo_tier(velo),
            analog_count=summary.analog_count,
            analog_win_rate=summary.analog_win_rate,
            analog_place_rate=summary.analog_place_rate,
            analog_ae=summary.analog_ae,
            analog_roi=summary.analog_roi,
            top_similarity=summary.top_similarity,
            confidence=confidence,
            warnings=warnings,
            explanation=explanation,
            shadow_only=True,  # Stage 4 unblocks this
            feature_version="fingerprint_v1",
            signal_version="phase35_locked",
        )

    # ─── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _estimate_roi(matches: List[AnalogMatch]) -> float:
        """
        Estimate ROI from analog SP values.
        Level stake: assume 1 unit on each analog.
        """
        if not matches:
            return 0.0
        total_roi = 0.0
        for m in matches:
            if m.analog_sp and m.analog_sp > 0:
                if m.analog_win is True:
                    # Win: returned = sp - 1 (profit) minus stake
                    total_roi += (float(m.analog_sp) - 1.0)
                elif m.analog_placed is True:
                    # Place: typically 1/4 of odds, simplified to 0.2 * (sp-1)
                    total_roi += 0.2 * (float(m.analog_sp) - 1.0)
                else:
                    total_roi -= 1.0  # lost stake
            else:
                total_roi -= 1.0  # assume lost
        return total_roi / len(matches)

    @staticmethod
    def _classify_confidence(summary: AnalogSummary) -> Confidence:
        n = summary.analog_count
        wr = summary.analog_win_rate
        ae = summary.analog_ae

        if n >= ANALOG_COUNT_HIGH and wr >= ANALOG_WIN_RATE_HIGH and ae >= ANALOG_AE_HIGH:
            return Confidence.HIGH
        if n >= ANALOG_COUNT_MEDIUM and wr >= ANALOG_WIN_RATE_MEDIUM:
            return Confidence.MEDIUM
        return Confidence.LOW

    @staticmethod
    def _velo_tier(velo) -> str:
        """Derive VÉLØ tier from sqpe."""
        sqpe = float(velo.sqpe)
        if sqpe >= 0.60:
            return "A"
        if sqpe >= 0.50:
            return "B"
        if sqpe >= 0.40:
            return "C"
        if sqpe >= 0.25:
            return "D"
        return "X"

    @staticmethod
    def _build_warnings(velo, summary: AnalogSummary) -> List[str]:
        warnings = []
        if summary.analog_count < 5:
            warnings.append("low_analog_count")
        if summary.top_similarity < MIN_SIMILARITY_WARN:
            warnings.append("low_similarity")
        if velo.sqpe_band.value not in ("sweet",):
            warnings.append("regime_mismatch")
        if velo.trainer_ae is not None and velo.trainer_ae < TRAINER_AE_MIN:
            warnings.append("no_turf_edge")
        if velo.sp_band.value in ("short", "favourite"):
            warnings.append("market_overlay")
        return warnings

    @staticmethod
    def _explain(velo, summary: AnalogSummary, warnings: List[str]) -> str:
        parts = []
        n = summary.analog_count

        if n == 0:
            return "no_analogs_found"

        if "low_analog_count" in warnings:
            parts.append(f"only_{n}_analogs")

        if "regime_mismatch" in warnings:
            parts.append("sqpe_outside_sweet")

        if "low_similarity" in warnings:
            parts.append(f"top_similarity_{summary.top_similarity:.2f}")

        if summary.analog_win_rate >= 0.25 and summary.analog_ae >= 1.30:
            parts.append("strong_analog_edge")
        elif summary.analog_win_rate >= 0.20:
            parts.append("moderate_analog_edge")

        return "; ".join(parts) if parts else "baseline"
