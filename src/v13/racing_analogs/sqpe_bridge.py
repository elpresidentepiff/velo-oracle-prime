"""
sqpe_bridge.py — Live SQPE Bridge for the Analog Sidecar
=========================================================
Extracts and enriches live VELØ SQPE signals for the analog sidecar.

Architecture
-----------
The VELØ pipeline computes two SQPE-related signals:

  1. sqpe_v17_prob  — ML model probability (isotonic-calibrated).
     Stored in velo_verdicts.full_analysis[runner].sqpe_v17_prob.
     Weight in ensemble: 0.45 (strongest single signal).

  2. velo_prime_prob — final weighted ensemble output.
     Stored in velo_verdicts.full_analysis[runner].velo_prime_prob.
     Combines sqpe_v17 (0.45) + market_deception (0.10) + place_prob (0.08) + ...

The RAW Phase 3.5 SQPE score is computed in-memory only and NOT persisted.
This bridge reads sqpe_v17_prob as the live SQPE signal with honest sqpe_source tagging.

Dual SQPE Mode
--------------
  HISTORICAL: sqpe_proxy (1/SP x modifiers) — sqpe_source=historical_proxy
  LIVE BRIDGE: sqpe_v17_prob — sqpe_source=live_sqpe_v17_prob

Files
-----
  - src/v13/racing_analogs/sqpe_bridge.py    (NEW)
  - src/v13/racing_analogs/extended_shadow.py (updated to use bridge)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from .schema import SQPEBand


class SQPEBandSource(str, Enum):
    """Labels which SQPE signal is being used."""
    LIVE_SQPE_V17_PROB = "live_sqpe_v17_prob"
    LIVE_VELO_PRIME_PROB = "live_velo_prime_prob"
    HISTORICAL_PROXY = "historical_proxy"
    UNKNOWN = "unknown"


@dataclass
class LiveSQPERecord:
    """
    A single runner's live SQPE signal from velo_verdicts.

    Two distinct live signals:
      - sqpe_v17_prob: ML model calibrated probability (primary SQPE signal)
      - velo_prime_prob: Full ensemble output
    """
    race_id: str
    runner_id: str
    horse: str

    # Primary signals from velo_verdicts
    sqpe_v17_prob: Optional[float] = None
    velo_prime_prob: Optional[float] = None
    rpd_tag: Optional[str] = None
    top_rank: bool = False

    # Derived bands
    sqpe_v17_band: Optional[SQPEBand] = None
    velo_prime_band: Optional[SQPEBand] = None

    # Bridge output
    sqpe_source: SQPEBandSource = SQPEBandSource.UNKNOWN
    primary_sqpe: Optional[float] = None
    primary_sqpe_band: Optional[SQPEBand] = None

    # Signal quality
    signal_quality: str = "UNKNOWN"

    # Disagreement
    disagreement_flag: bool = False
    disagreement_note: Optional[str] = None

    @classmethod
    def from_runner(
        cls,
        runner_data: Dict[str, Any],
        top_rank_horse_id: Optional[str],
    ) -> "LiveSQPERecord":
        """Extract and derive live SQPE from a runner dict in full_analysis."""
        race_id = runner_data.get("race_id", "")
        horse_id = str(runner_data.get("horse_id", ""))
        horse = runner_data.get("horse", "?")

        sqpe_v17 = None
        if runner_data.get("sqpe_v17_prob") is not None:
            sqpe_v17 = float(runner_data["sqpe_v17_prob"])

        vp = None
        if runner_data.get("velo_prime_prob") is not None:
            vp = float(runner_data["velo_prime_prob"])

        rpd_tag = runner_data.get("rpd_tag")
        is_top = (horse_id == top_rank_horse_id)

        sqpe17_band = SQPEBand.from_sqpe(sqpe_v17) if sqpe_v17 else None
        vp_band = SQPEBand.from_sqpe(vp) if vp else None

        if sqpe_v17 is not None:
            primary = sqpe_v17
            primary_band = sqpe17_band
            source = SQPEBandSource.LIVE_SQPE_V17_PROB
        elif vp is not None:
            primary = vp
            primary_band = vp_band
            source = SQPEBandSource.LIVE_VELO_PRIME_PROB
        else:
            primary = None
            primary_band = None
            source = SQPEBandSource.UNKNOWN

        quality = _assess_quality(sqpe_v17, vp, sqpe17_band)

        disagree = False
        disagree_note = None
        if sqpe_v17 is not None and vp is not None:
            diff = abs(vp - sqpe_v17)
            if diff > 0.10:
                disagree = True
                disagree_note = f"sqpe_v17={sqpe_v17:.4f} vs vp={vp:.4f} (diff={diff:.4f})"

        return cls(
            race_id=race_id,
            runner_id=horse_id,
            horse=horse,
            sqpe_v17_prob=sqpe_v17,
            velo_prime_prob=vp,
            rpd_tag=rpd_tag,
            top_rank=is_top,
            sqpe_v17_band=sqpe17_band,
            velo_prime_band=vp_band,
            sqpe_source=source,
            primary_sqpe=primary,
            primary_sqpe_band=primary_band,
            signal_quality=quality,
            disagreement_flag=disagree,
            disagreement_note=disagree_note,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "race_id": self.race_id,
            "runner_id": self.runner_id,
            "horse": self.horse,
            "sqpe_v17_prob": round(self.sqpe_v17_prob, 4) if self.sqpe_v17_prob else None,
            "velo_prime_prob": round(self.velo_prime_prob, 4) if self.velo_prime_prob else None,
            "sqpe_v17_band": self.sqpe_v17_band.value if self.sqpe_v17_band else None,
            "velo_prime_band": self.velo_prime_band.value if self.velo_prime_band else None,
            "primary_sqpe": round(self.primary_sqpe, 4) if self.primary_sqpe else None,
            "primary_sqpe_band": self.primary_sqpe_band.value if self.primary_sqpe_band else None,
            "sqpe_source": self.sqpe_source.value,
            "signal_quality": self.signal_quality,
            "top_rank": self.top_rank,
            "disagreement_flag": self.disagreement_flag,
            "disagreement_note": self.disagreement_note,
        }

    def summary_line(self) -> str:
        src = self.sqpe_source.value
        sq17 = f"{self.sqpe_v17_prob:.4f}" if self.sqpe_v17_prob else "N/A"
        vp = f"{self.velo_prime_prob:.4f}" if self.velo_prime_prob else "N/A"
        band17 = self.sqpe_v17_band.value if self.sqpe_v17_band else "?"
        top = "★" if self.top_rank else " "
        disc = " [!DISAGREE]" if self.disagreement_flag else ""
        return (
            f"{self.horse[:20]:20s} | sqpe_v17={sq17}({band17}) "
            f"vp={vp}{disc} | top={top} qual={self.signal_quality}"
        )


def _assess_quality(
    sqpe_v17: Optional[float],
    vp: Optional[float],
    sqpe17_band: Optional[SQPEBand],
) -> str:
    if sqpe_v17 is None and vp is None:
        return "UNUSABLE"
    if sqpe_v17 is None:
        sqpe_v17 = 0.0
        sqpe17_band = SQPEBand.VERY_LOW
    if sqpe17_band is None:
        sqpe17_band = SQPEBand.from_sqpe(sqpe_v17)

    if sqpe_v17 is not None and vp is not None and abs(vp - sqpe_v17) > 0.15:
        return "LOW"

    if sqpe17_band == SQPEBand.SWEET:
        if vp is not None and abs(vp - sqpe_v17) < 0.10:
            return "HIGH"
        return "MEDIUM"
    elif sqpe17_band in (SQPEBand.LOW, SQPEBand.MEDIUM, SQPEBand.HIGH, SQPEBand.VERY_HIGH):
        return "MEDIUM"
    else:
        if vp is not None and vp > 0.20:
            return "MEDIUM"
        return "LOW"


class LiveSQPEBridge:
    """Extract live SQPE records from velo_verdict rows."""

    def extract(self, verdict_rows: List[Dict[str, Any]]) -> List[LiveSQPERecord]:
        records = []
        for row in verdict_rows:
            top_id = row.get("top_rank_horse_id")
            fa_raw = row.get("full_analysis", [])
            if isinstance(fa_raw, str):
                try:
                    fa_raw = json.loads(fa_raw)
                except Exception:
                    fa_raw = []
            if not fa_raw:
                continue
            for rd in fa_raw:
                try:
                    rec = LiveSQPERecord.from_runner(rd, top_id)
                    records.append(rec)
                except Exception:
                    continue
        return records

    def report(self, records: List[LiveSQPERecord]) -> str:
        if not records:
            return "No records."
        total = len(records)
        sq17_pop = sum(1 for r in records if r.sqpe_v17_prob is not None)
        vp_pop = sum(1 for r in records if r.velo_prime_prob is not None)
        disc = sum(1 for r in records if r.disagreement_flag)
        top = sum(1 for r in records if r.top_rank)
        qdist = {}
        for r in records:
            qdist[r.signal_quality] = qdist.get(r.signal_quality, 0) + 1
        bdist = {}
        for r in records:
            if r.sqpe_v17_band:
                bdist[r.sqpe_v17_band.value] = bdist.get(r.sqpe_v17_band.value, 0) + 1

        lines = [
            f"\n{'='*70}",
            f"LIVE SQPE BRIDGE REPORT — {total} runners",
            f"{'='*70}",
            f"  sqpe_v17_prob populated:   {sq17_pop}/{total} ({100*sq17_pop/total:.1f}%)",
            f"  velo_prime_prob populated: {vp_pop}/{total} ({100*vp_pop/total:.1f}%)",
            f"  Disagreement (diff>0.10):  {disc}/{total} ({100*disc/total:.1f}%)",
            f"  Top-ranked horses:         {top}/{total} ({100*top/total:.1f}%)",
            f"\n  Signal Quality:",
        ]
        for q, cnt in sorted(qdist.items()):
            lines.append(f"    {q:12s}: {cnt:5d} ({100*cnt/total:.1f}%)")
        lines.append(f"\n  sqpe_v17 band distribution:")
        for b, cnt in sorted(bdist.items(), key=lambda x: -x[1]):
            lines.append(f"    {b:12s}: {cnt:5d} ({100*cnt/total:.1f}%)")
        lines.append(f"\n  Disagreement cases:")
        for r in [x for x in records if x.disagreement_flag][:5]:
            lines.append(f"    {r.summary_line()}")
        return "\n".join(lines)
