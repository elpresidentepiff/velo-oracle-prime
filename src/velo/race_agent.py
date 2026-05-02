"""
VeloRaceAgent
=============

Takes a single race verdict dict and runs the full signal intelligence stack:
  - sidecar signal extraction
  - place signal classification (via place_signal_classifier.py)
  - stack membership classification (same logic as sidecar_stack_operator_card.py)
  - macro context
  - execution gate status
  - structured RaceIntelligence output

Classification:
  OPERATOR VISIBILITY ONLY
  NO STAKING. NO EXECUTION.

Import safety:
  Does NOT import from:
    app/agents/betfair_execution_agent.py   (EXECUTION_BETTING_NOT_ACTIVE)
    app/agents/betting_agents.py            (LEGACY_AGENT)
    app/agents/betfair_trading_agents.py    (EXECUTION_BETTING_NOT_ACTIVE)

Usage:
    from src.velo.race_agent import VeloRaceAgent
    agent = VeloRaceAgent(verdict_dict)
    intel = agent.run()
    print(agent.to_operator_card())
    d = agent.to_dict()
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.velo.place_signal_classifier import (
    PlaceSignal,
    VP30_T,
    MDS_HIGH_T,
    IMPROVE_HIGH_T,
    classify_from_verdict,
)

# ── Stack thresholds (same source as sidecar_stack_operator_card.py) ─────────

PLACE_HIGH_T = 0.80


# ── RaceMetadata lightweight stub (avoids Supabase dep in agent) ──────────────

@dataclass
class RaceMetadata:
    """Lightweight race metadata — passed in from caller or extracted from verdict."""
    race_id: str = ""
    horse: str = ""
    horse_id: str = ""
    course: str = ""
    off_time: str = ""
    race_name: str = ""
    date: str = ""


# ── RaceIntelligence output dataclass ────────────────────────────────────────

@dataclass
class RaceIntelligence:
    # Identity
    race_id: str
    horse: str
    horse_id: str
    course: str
    off_time: str
    race_name: str
    date: str

    # Core verdict fields
    tier: str
    velo_prime_prob: float
    confidence_level: str

    # Sidecar signals
    market_deception_score: float
    improvement_score: float
    place_prob: float
    longshot_score: float

    # Place signal classification
    place_signal: PlaceSignal

    # Sidecar stack classification
    stack_label: str        # Primary stack (highest priority one)
    stack_labels: list      # All stacks this runner qualifies for
    stack_badges: list      # Signal badges: TIER_A / VP30 / MDS_HIGH / IMP_HIGH

    # Macro context
    macro_chaos_mode: bool
    macro_regime_label: str
    favourite_trap_risk: str

    # HFS signals (may be None if dark)
    mpi: Optional[float]
    chaos_bloom: Optional[float]

    # Execution gate
    candidate_execution_allowed: bool

    # Status
    signal_contract_version: str
    generated_at: str
    status: str  # always "OPERATOR_VISIBILITY_ONLY"

    def to_dict(self) -> dict:
        return {
            "race_id":                   self.race_id,
            "horse":                     self.horse,
            "horse_id":                  self.horse_id,
            "course":                    self.course,
            "off_time":                  self.off_time,
            "race_name":                 self.race_name,
            "date":                      self.date,
            "tier":                      self.tier,
            "velo_prime_prob":           round(self.velo_prime_prob, 4),
            "confidence_level":          self.confidence_level,
            "market_deception_score":    round(self.market_deception_score, 4),
            "improvement_score":         round(self.improvement_score, 4),
            "place_prob":                round(self.place_prob, 4),
            "longshot_score":            round(self.longshot_score, 4),
            "place_signal":              self.place_signal.to_dict(),
            "stack_label":               self.stack_label,
            "stack_labels":              self.stack_labels,
            "stack_badges":              self.stack_badges,
            "macro_chaos_mode":          self.macro_chaos_mode,
            "macro_regime_label":        self.macro_regime_label,
            "favourite_trap_risk":       self.favourite_trap_risk,
            "mpi":                       self.mpi,
            "chaos_bloom":               self.chaos_bloom,
            "candidate_execution_allowed": self.candidate_execution_allowed,
            "signal_contract_version":   self.signal_contract_version,
            "generated_at":              self.generated_at,
            "status":                    self.status,
        }


# ── Stack classification logic (mirrors sidecar_stack_operator_card.py) ──────

STACK_ORDER = [
    "ELITE_STACK",
    "STRONG_STACK_PLUS",
    "STRONG_STACK",
    "VP30_IMPROVE",
    "VP30_BASE",
    "SUPPRESS",
]

STACK_DEFS = {
    "ELITE_STACK":       "Tier A + VP≥0.30 + MDS>0.50",
    "STRONG_STACK_PLUS": "VP≥0.30 + MDS>0.50 + IMP>0.40",
    "STRONG_STACK":      "VP≥0.30 + MDS>0.50 (no IMP)",
    "VP30_IMPROVE":      "VP≥0.30 + IMP>0.40 (no MDS)",
    "VP30_BASE":         "VP≥0.30 only (no MDS, no IMP)",
    "SUPPRESS":          "Tier B + VP<0.30",
}


def _classify_stacks(vp: float, mds: float, imp: float, tier: str) -> tuple[list[str], list[str]]:
    """
    Returns (stacks, badges).
    Mirrors classify_runner() in sidecar_stack_operator_card.py.
    """
    vp30     = vp  >= VP30_T
    mds_high = mds >  MDS_HIGH_T
    imp_high = imp >  IMPROVE_HIGH_T
    tier_a   = tier == "A"
    tier_b   = tier == "B"

    badges: list[str] = []
    if tier_a:   badges.append("TIER_A")
    if vp30:     badges.append("VP30")
    if mds_high: badges.append("MDS_HIGH")
    if imp_high: badges.append("IMP_HIGH")

    stacks: list[str] = []

    if tier_a and vp30 and mds_high:
        stacks.append("ELITE_STACK")

    if vp30 and mds_high and imp_high:
        stacks.append("STRONG_STACK_PLUS")

    if vp30 and mds_high and not imp_high:
        stacks.append("STRONG_STACK")

    if vp30 and imp_high and not mds_high:
        stacks.append("VP30_IMPROVE")

    if vp30 and not mds_high and not imp_high:
        stacks.append("VP30_BASE")

    if tier_b and not vp30:
        stacks.append("SUPPRESS")

    return stacks, badges


def _extract_top_runner(verdict: dict) -> dict:
    """Pull top-runner fields from full_analysis[0], matching sidecar_stack_operator_card logic."""
    fa = verdict.get("full_analysis") or []
    if isinstance(fa, dict):
        fa = list(fa.values())
    if fa and isinstance(fa, list) and isinstance(fa[0], dict):
        return fa[0]
    return {}


# ── VeloRaceAgent ─────────────────────────────────────────────────────────────

class VeloRaceAgent:
    """
    Takes a single velo_verdicts row (dict) and produces a RaceIntelligence output.

    OPERATOR VISIBILITY ONLY.
    NO STAKING. NO EXECUTION. NO BETFAIR.
    """

    STATUS = "OPERATOR_VISIBILITY_ONLY"
    SIGNAL_CONTRACT = "hfs_signal_contract_v1"

    def __init__(self, verdict: dict, meta: Optional[RaceMetadata] = None):
        self._verdict = verdict
        self._meta = meta
        self._intel: Optional[RaceIntelligence] = None

    # ── Public interface ─────────────────────────────────────────────────────

    def run(self) -> RaceIntelligence:
        """Run all intelligence layers. Returns populated RaceIntelligence."""
        v = self._verdict
        m = self._meta
        top = _extract_top_runner(v)

        # ── Identity ──────────────────────────────────────────────────────
        race_id   = v.get("race_id") or top.get("race_id") or ""
        horse     = top.get("horse") or v.get("horse") or "?"
        horse_id  = top.get("horse_id") or v.get("horse_id") or ""
        course    = (m.course    if m else None) or top.get("course")    or v.get("course")    or "—"
        off_time  = (m.off_time  if m else None) or top.get("off_time")  or v.get("off_time")  or "—"
        race_name = (m.race_name if m else None) or top.get("race_name") or v.get("race_name") or ""
        date      = (m.date      if m else None) or (v.get("generated_at") or "")[:10] or ""

        # ── Core verdict ──────────────────────────────────────────────────
        tier  = str(v.get("decision_tier") or v.get("tier") or "").strip().upper()
        vp    = float(v.get("velo_prime_prob") or top.get("velo_prime_prob") or 0)
        conf  = str(v.get("confidence_level") or "low")

        # ── Sidecar signals ───────────────────────────────────────────────
        mds       = float(v.get("market_deception_score") or top.get("market_deception_score") or 0)
        imp       = float(v.get("improvement_score")      or top.get("improvement_score")      or 0)
        pp        = float(v.get("place_prob")              or top.get("place_prob")              or 0)
        longshot  = float(v.get("longshot_score")          or top.get("longshot_score")          or 0)

        # HFS signals (may be None — signal-dark if not yet backfilled)
        mpi_raw = v.get("mpi") or top.get("mpi")
        cb_raw  = v.get("chaos_bloom") or top.get("chaos_bloom")
        mpi         = float(mpi_raw)  if mpi_raw  is not None else None
        chaos_bloom = float(cb_raw)   if cb_raw   is not None else None

        # ── Place signal classification ───────────────────────────────────
        place_signal = classify_from_verdict(v)

        # ── Stack classification ──────────────────────────────────────────
        stacks, badges = _classify_stacks(vp, mds, imp, tier)
        # Primary stack = first in priority order
        primary_stack = stacks[0] if stacks else "UNCLASSIFIED"

        # ── Macro context ─────────────────────────────────────────────────
        # Lightweight extraction — full macro engine requires DB access.
        # Read from verdict if present, else use safe defaults.
        macro_chaos   = bool(v.get("macro_chaos_mode") or top.get("macro_chaos_mode") or False)
        macro_regime  = str(v.get("macro_regime_label") or top.get("macro_regime_label") or "UNKNOWN")
        fav_trap      = str(v.get("favourite_trap_risk") or top.get("favourite_trap_risk") or "UNKNOWN")

        # ── Execution gate ────────────────────────────────────────────────
        exec_allowed = bool(v.get("execution_allowed") or v.get("candidate_execution_allowed") or False)

        intel = RaceIntelligence(
            race_id=race_id,
            horse=horse,
            horse_id=horse_id,
            course=course,
            off_time=off_time,
            race_name=race_name,
            date=date,
            tier=tier,
            velo_prime_prob=round(vp, 4),
            confidence_level=conf,
            market_deception_score=round(mds, 4),
            improvement_score=round(imp, 4),
            place_prob=round(pp, 4),
            longshot_score=round(longshot, 4),
            place_signal=place_signal,
            stack_label=primary_stack,
            stack_labels=stacks,
            stack_badges=badges,
            macro_chaos_mode=macro_chaos,
            macro_regime_label=macro_regime,
            favourite_trap_risk=fav_trap,
            mpi=mpi,
            chaos_bloom=chaos_bloom,
            candidate_execution_allowed=exec_allowed,
            signal_contract_version=self.SIGNAL_CONTRACT,
            generated_at=datetime.now(timezone.utc).isoformat(),
            status=self.STATUS,
        )
        self._intel = intel
        return intel

    def to_operator_card(self) -> str:
        """Render a compact operator card. Calls run() if not already called."""
        if self._intel is None:
            self.run()
        i = self._intel
        ps = i.place_signal

        mpi_str = f"{i.mpi:.3f}" if i.mpi is not None else "DARK"
        cb_str  = f"{i.chaos_bloom:.3f}" if i.chaos_bloom is not None else "DARK"
        badges_str = " | ".join(i.stack_badges) if i.stack_badges else "NONE"

        WIDTH = 46
        def pad(line: str) -> str:
            return f"║  {line:<{WIDTH - 4}}  ║"

        lines = [
            "╔" + "═" * (WIDTH) + "╗",
            f"║  {'VÉLØ RACE INTELLIGENCE — ' + i.date:<{WIDTH - 4}}  ║",
            "╠" + "═" * (WIDTH) + "╣",
            pad(f"{i.off_time}  {i.course}"),
            pad(f"{i.race_name[:WIDTH - 6]}" if i.race_name else "—"),
            pad(f"{i.horse}"),
            pad(f"Tier {i.tier}  |  VP {i.velo_prime_prob:.3f}  |  {i.confidence_level.upper()}"),
            "╠" + "═" * (WIDTH) + "╣",
            pad("SIGNALS"),
            pad(f"MDS: {i.market_deception_score:.3f}    IMP: {i.improvement_score:.3f}"),
            pad(f"PP:  {i.place_prob:.3f}    MPI: {mpi_str}"),
            pad(f"CB:  {cb_str}    LONG: {i.longshot_score:.3f}"),
            "╠" + "═" * (WIDTH) + "╣",
            pad(f"PLACE: {ps.place_stack_label}"),
            pad(f"STATUS: {ps.place_stack_status}"),
            pad(f"STACK: {i.stack_label}"),
            pad(f"BADGES: {badges_str}"),
            pad(f"EXEC GATE: {'ALLOWED' if i.candidate_execution_allowed else 'BLOCKED'}"),
            "╠" + "═" * (WIDTH) + "╣",
            pad("STATUS: OPERATOR VISIBILITY ONLY"),
            pad("NO STAKING. NO EXECUTION."),
            "╚" + "═" * (WIDTH) + "╝",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Return structured dict for JSON serialisation. Calls run() if needed."""
        if self._intel is None:
            self.run()
        return self._intel.to_dict()


# ── Smoke test (run directly) ─────────────────────────────────────────────────

if __name__ == "__main__":
    # Smoke test against the inline SSC data (2026-05-02 real data)
    SMOKE_VERDICT = {
        "race_id": "rac_11954163",
        "decision_tier": "A",
        "velo_prime_prob": 0.372,
        "market_deception_score": 0.503,
        "improvement_score": 0.352,
        "place_prob": 0.9775,
        "execution_allowed": False,
        "generated_at": "2026-05-02T14:35:51.823693+00:00",
        "full_analysis": [
            {
                "horse": "Tap Tap Shamie",
                "horse_id": "hrs_41052235",
                "course": "Uttoxeter",
                "off_time": "1:55",
                "race_name": "Support The Stoke City Foundation Maiden Hurdle (Div II)",
                "velo_prime_prob": 0.372,
                "market_deception_score": 0.503,
                "improvement_score": 0.352,
                "place_prob": 0.9775,
            }
        ],
    }

    print("── VeloRaceAgent Smoke Test ─────────────────────────────────────")
    print()

    agent = VeloRaceAgent(SMOKE_VERDICT)
    intel = agent.run()

    print(agent.to_operator_card())
    print()

    import json
    d = agent.to_dict()
    print("to_dict() excerpt:")
    print(f"  race_id:              {d['race_id']}")
    print(f"  horse:                {d['horse']}")
    print(f"  tier:                 {d['tier']}")
    print(f"  velo_prime_prob:      {d['velo_prime_prob']}")
    print(f"  market_deception_score: {d['market_deception_score']}")
    print(f"  improvement_score:    {d['improvement_score']}")
    print(f"  place_signal.label:   {d['place_signal']['place_stack_label']}")
    print(f"  place_signal.status:  {d['place_signal']['place_stack_status']}")
    print(f"  stack_label:          {d['stack_label']}")
    print(f"  stack_labels:         {d['stack_labels']}")
    print(f"  stack_badges:         {d['stack_badges']}")
    print(f"  mpi:                  {d['mpi']}")
    print(f"  chaos_bloom:          {d['chaos_bloom']}")
    print(f"  exec_gate:            {d['candidate_execution_allowed']}")
    print(f"  status:               {d['status']}")
    print()
    print("CONFIRMATION: No scoring/model/SQPE/router/staking/live execution changed.")
    print("STATUS: OPERATOR_VISIBILITY_ONLY")
