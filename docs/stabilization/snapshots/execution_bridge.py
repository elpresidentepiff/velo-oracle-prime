"""
VeloExecutionBridge — Simulation / Paper Only
==============================================
Reads VÉLØ's persisted verdicts and emits ExecutionDirectives for
simulation and audit. This module never places real orders, never calls
BetfairClient.place_order, never sends Telegram alerts, never stakes.

HARD GATES:
  - VELO_EXECUTION_MODE must be SIM or PAPER (default: SIM)
  - LIVE raises RuntimeError
  - BETFAIR_MODE=LIVE raises RuntimeError
  - suggested_stake and max_liability are always null
  - simulation_only is always True

Directive types (priority order):
  BLOCKED               — hard block (missing data, mode violation)
  CHAOS_CONTAINMENT_MODE— archetype suppression or chaos race type
  POWER_ANCHOR_MODE     — Tier A, VP≥0.40, execution gate clear
  FAVOURITE_LIABILITY_MODE — MDS≥0.50, VP≥0.30, Tier A/B
  MULTI_THREAT_ZONE_MODE— VP≥0.30, improvement_score≥0.40
  WATCH_ONLY            — VP≥0.30 but below execution threshold
  BLOCKED               — sub-threshold fallthrough

Usage:
    from src.velo.execution_bridge import VeloExecutionBridge, enrich_from_shadow_ledger
    bridge = VeloExecutionBridge()
    directives = bridge.generate_directives(verdicts)
    added, skipped = bridge.append_to_paper_ledger(directives)
"""
from __future__ import annotations

import csv
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent.parent

SOURCE = "VELO_EXECUTION_BRIDGE_V1"
DEFAULT_PAPER_LEDGER = ROOT / "data" / "velo_execution_bridge_paper_ledger.csv"

_ACCEPTED_MODES = {"OFF", "SIM", "PAPER"}

_PAPER_LEDGER_HEADER = [
    "date",
    "race_id",
    "horse_id",
    "horse",
    "course",
    "off_time",
    "directive_type",
    "confidence",
    "reason_codes",
    "velo_prime_prob",
    "tier",
    "router_shadow_lane",
    "candidate_execution_allowed",
    "execution_allowed",
    "assigned_product",
    "market_deception_score",
    "improvement_score",
    "rpdc_release_score",
    "place_prob",
    "race_archetype",
    "archetype_suppression",
    "racing_api_enrichment_shadow_score",
    "simulation_only",
    "execution_blocked_reason",
    "recommended_bet_type",
    "result_position",
    "won",
    "placed",
    "sp_decimal",
    "paper_profit_loss",
    "created_at",
    "source",
]

_DEDUP_FIELDS = ("date", "race_id", "horse_id", "directive_type", "source")


# ── Safety ───────────────────────────────────────────────────────────────────

def _check_execution_mode(mode: str) -> None:
    """Raise RuntimeError for any forbidden mode configuration."""
    if mode == "LIVE":
        raise RuntimeError(
            "VELO_EXECUTION_MODE=LIVE is not implemented. "
            "VeloExecutionBridge is SIMULATION/PAPER ONLY. "
            "Set VELO_EXECUTION_MODE to SIM or PAPER."
        )
    if mode not in _ACCEPTED_MODES:
        raise RuntimeError(
            f"Invalid VELO_EXECUTION_MODE={mode!r}. Accepted values: {sorted(_ACCEPTED_MODES)}"
        )
    if os.getenv("BETFAIR_MODE", "SIM").upper() == "LIVE":
        raise RuntimeError(
            "BETFAIR_MODE=LIVE detected. VeloExecutionBridge refuses to run. "
            "Set BETFAIR_MODE=SIM for paper trading."
        )


def _resolve_mode() -> str:
    mode = os.getenv("VELO_EXECUTION_MODE", "SIM").upper()
    _check_execution_mode(mode)
    return mode


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class ExecutionDirective:
    """
    A single execution directive emitted by VeloExecutionBridge.
    simulation_only is always True — this is never a betting instruction.
    suggested_stake and max_liability are always None.
    """
    race_id: str
    horse_id: str
    horse: str
    directive_type: str
    confidence: float
    reason_codes: list[str]
    velo_prime_prob: float
    tier: str
    router_shadow_lane: str
    candidate_execution_allowed: bool
    execution_allowed: bool
    simulation_only: bool = True          # HARD: always True
    suggested_stake: None = None          # HARD: always None
    max_liability: None = None            # HARD: always None
    execution_blocked_reason: str = ""
    recommended_bet_type: str = ""
    source: str = SOURCE
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Enrichment context
    date: str = ""
    course: str = ""
    off_time: str = ""
    assigned_product: str = ""
    market_deception_score: float = 0.0
    improvement_score: float = 0.0
    rpdc_release_score: float = 0.0
    place_prob: float = 0.0
    race_archetype: str = ""
    archetype_suppression: bool = False
    racing_api_enrichment_shadow_score: float | None = None
    racing_api_connection_shadow_score: float | None = None
    racing_api_course_shadow_score: float | None = None
    racing_api_distance_shadow_score: float | None = None


# ── Field helpers ─────────────────────────────────────────────────────────────

def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (ValueError, TypeError):
        return default


def _b(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes")
    return bool(v) if v is not None else False


def _s(v: Any, default: str = "") -> str:
    return str(v).strip() if v is not None else default


def _extract_top_runner(full_analysis: Any) -> dict:
    """
    Extract top runner dict from full_analysis regardless of format.

    Handles:
      - New format: {"predictions": [...], "plot_intel": {...}, ...}
      - Old format: [runner_dict, ...]
    """
    if not full_analysis:
        return {}
    if isinstance(full_analysis, list):
        return full_analysis[0] if full_analysis else {}
    if isinstance(full_analysis, dict):
        preds = full_analysis.get("predictions") or []
        if preds:
            return preds[0] if isinstance(preds, list) else {}
        # fallback: top-level keys might be runner fields
        if "horse" in full_analysis or "velo_prime_prob" in full_analysis:
            return full_analysis
    return {}


# ── Shadow ledger join ────────────────────────────────────────────────────────

def enrich_from_shadow_ledger(
    verdicts: list[dict],
    ledger_path: Path | None = None,
) -> list[dict]:
    """
    Left-join verdicts with the Racing API shadow ledger on race_id.

    Injects per-verdict:
      - candidate_execution_allowed
      - router_shadow_lane (candidate_execution_lane)
      - racing_api_*_shadow_score
      - horse_id, horse, course, off_time, date (from ledger if missing)

    Non-destructive: verdicts that have no ledger match are returned unchanged.
    """
    path = ledger_path or (ROOT / "data" / "racing_api_shadow_forward_ledger.csv")
    if not path.exists():
        log.debug("Shadow ledger not found at %s — skipping enrichment", path)
        return verdicts

    # Build lookup by race_id (last row wins — same dedup semantics as audit)
    ledger_map: dict[str, dict] = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ledger_map[row.get("race_id", "")] = row

    enriched = []
    for v in verdicts:
        rid = v.get("race_id", "")
        if rid in ledger_map:
            lrow = ledger_map[rid]
            merged = dict(v)  # shallow copy — never mutate original
            # Only inject if not already populated in the verdict
            for src_key, dst_key in [
                ("candidate_execution_allowed", "candidate_execution_allowed"),
                ("router_shadow_lane",          "router_shadow_lane"),
                ("racing_api_enrichment_shadow_score",  "racing_api_enrichment_shadow_score"),
                ("racing_api_connection_shadow_score",  "racing_api_connection_shadow_score"),
                ("racing_api_course_shadow_score",      "racing_api_course_shadow_score"),
                ("racing_api_distance_shadow_score",    "racing_api_distance_shadow_score"),
            ]:
                if dst_key not in merged or merged[dst_key] is None:
                    val = lrow.get(src_key)
                    if val and val.strip() not in ("", "None", "null"):
                        merged[dst_key] = val
            # Propagate identifiers from ledger if missing in verdict
            for lkey, vkey in [("horse", "horse"), ("horse_id", "horse_id"),
                                ("course", "course"), ("off_time", "off_time"),
                                ("date", "date")]:
                if not merged.get(vkey) and lrow.get(lkey):
                    merged[vkey] = lrow[lkey]
            enriched.append(merged)
        else:
            enriched.append(v)
    return enriched


# ── Bridge ────────────────────────────────────────────────────────────────────

class VeloExecutionBridge:
    """
    Translates VÉLØ verdicts into ExecutionDirectives for simulation/audit.

    Never places real orders. Never stakes. Never calls BetfairClient.place_order.
    """

    def __init__(self, mode: str | None = None) -> None:
        raw = (mode or os.getenv("VELO_EXECUTION_MODE", "SIM")).upper()
        _check_execution_mode(raw)
        self.mode = raw

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_directives(self, verdicts: list[dict]) -> list[ExecutionDirective]:
        """Map a list of VÉLØ verdict dicts to ExecutionDirectives. Never raises."""
        out: list[ExecutionDirective] = []
        for v in verdicts:
            try:
                out.append(self._map_verdict(v))
            except Exception as exc:
                log.warning("Directive mapping failed for %s: %s", v.get("race_id"), exc)
        return out

    def append_to_paper_ledger(
        self,
        directives: list[ExecutionDirective],
        ledger_path: Path | None = None,
    ) -> tuple[int, int]:
        """
        Append directives to paper ledger. Idempotent — dedup key prevents
        duplicate rows on reruns.

        Returns:
            (rows_added, rows_skipped)
        """
        path = ledger_path or DEFAULT_PAPER_LEDGER
        path.parent.mkdir(parents=True, exist_ok=True)

        existing: set[tuple] = set()
        if path.exists() and path.stat().st_size > 0:
            with path.open(encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    existing.add(tuple(_s(row.get(k)) for k in _DEDUP_FIELDS))

        write_header = not path.exists() or path.stat().st_size == 0
        added = skipped = 0

        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_PAPER_LEDGER_HEADER, extrasaction="ignore")
            if write_header:
                writer.writeheader()

            for d in directives:
                key = (d.date, d.race_id, d.horse_id, d.directive_type, d.source)
                if key in existing:
                    skipped += 1
                    continue
                writer.writerow({
                    "date":                             d.date,
                    "race_id":                          d.race_id,
                    "horse_id":                         d.horse_id,
                    "horse":                            d.horse,
                    "course":                           d.course,
                    "off_time":                         d.off_time,
                    "directive_type":                   d.directive_type,
                    "confidence":                       d.confidence,
                    "reason_codes":                     "|".join(d.reason_codes),
                    "velo_prime_prob":                  d.velo_prime_prob,
                    "tier":                             d.tier,
                    "router_shadow_lane":               d.router_shadow_lane,
                    "candidate_execution_allowed":      d.candidate_execution_allowed,
                    "execution_allowed":                d.execution_allowed,
                    "assigned_product":                 d.assigned_product,
                    "market_deception_score":           d.market_deception_score,
                    "improvement_score":                d.improvement_score,
                    "rpdc_release_score":               d.rpdc_release_score,
                    "place_prob":                       d.place_prob,
                    "race_archetype":                   d.race_archetype,
                    "archetype_suppression":            d.archetype_suppression,
                    "racing_api_enrichment_shadow_score": d.racing_api_enrichment_shadow_score or "",
                    "simulation_only":                  True,
                    "execution_blocked_reason":         d.execution_blocked_reason,
                    "recommended_bet_type":             d.recommended_bet_type,
                    "result_position":                  "",
                    "won":                              "",
                    "placed":                           "",
                    "sp_decimal":                       "",
                    "paper_profit_loss":                "",
                    "created_at":                       d.created_at,
                    "source":                           d.source,
                })
                existing.add(key)
                added += 1

        return added, skipped

    # ── Directive mapping ─────────────────────────────────────────────────────

    def _map_verdict(self, v: dict) -> ExecutionDirective:
        """Map a single verdict dict to an ExecutionDirective (priority-ordered)."""

        # ── Extract fields ────────────────────────────────────────────────────
        race_id   = _s(v.get("race_id"))
        prob      = _f(v.get("velo_prime_prob"))
        tier      = _s(v.get("decision_tier") or v.get("tier"), "?")
        mds       = _f(v.get("market_deception_score"))
        imp       = _f(v.get("improvement_score"))
        rpdc      = _f(v.get("rpdc_release_score"))
        place_p   = _f(v.get("place_prob"))
        archetype = _s(v.get("race_archetype"))
        suppressed= _b(v.get("archetype_suppression"))
        exec_ok   = _b(v.get("execution_allowed"))
        cand_ok   = _b(v.get("candidate_execution_allowed"))
        product   = _s(v.get("assigned_product"))
        lane      = _s(v.get("router_shadow_lane"))
        enr       = v.get("racing_api_enrichment_shadow_score")
        conn      = v.get("racing_api_connection_shadow_score")
        crs       = v.get("racing_api_course_shadow_score")
        dst       = v.get("racing_api_distance_shadow_score")

        # ── Horse identifiers ─────────────────────────────────────────────────
        top_runner = _extract_top_runner(v.get("full_analysis"))
        horse      = _s(v.get("horse") or top_runner.get("horse") or top_runner.get("horse_name"), "?")
        horse_id   = _s(v.get("horse_id") or top_runner.get("horse_id"))
        off_time   = _s(v.get("off_time") or top_runner.get("off_time"))[:5]
        course     = _s(v.get("course") or v.get("track"))
        date_str   = _s(v.get("date") or _s(v.get("generated_at"))[:10])

        base = dict(
            race_id=race_id, horse_id=horse_id, horse=horse,
            velo_prime_prob=prob, tier=tier,
            router_shadow_lane=lane, candidate_execution_allowed=cand_ok,
            execution_allowed=exec_ok, assigned_product=product,
            date=date_str, course=course, off_time=off_time,
            market_deception_score=mds, improvement_score=imp,
            rpdc_release_score=rpdc, place_prob=place_p,
            race_archetype=archetype, archetype_suppression=suppressed,
            racing_api_enrichment_shadow_score=_f(enr) if enr is not None else None,
            racing_api_connection_shadow_score=_f(conn) if conn is not None else None,
            racing_api_course_shadow_score=_f(crs) if crs is not None else None,
            racing_api_distance_shadow_score=_f(dst) if dst is not None else None,
        )

        # ── Priority 1: Hard BLOCKED ──────────────────────────────────────────
        hard_reason = self._hard_block_reason(race_id, horse, horse_id)
        if hard_reason:
            return ExecutionDirective(
                directive_type="BLOCKED", confidence=0.0,
                reason_codes=["HARD_BLOCK"],
                execution_blocked_reason=hard_reason,
                recommended_bet_type="NONE",
                **base,
            )

        # ── Priority 2: CHAOS_CONTAINMENT_MODE ───────────────────────────────
        if suppressed or archetype.lower() in ("chaos", "chaotic"):
            codes = []
            if suppressed:
                codes.append("ARCHETYPE_SUPPRESSION")
            if archetype.lower() in ("chaos", "chaotic"):
                codes.append(f"CHAOS_ARCHETYPE({archetype})")
            return ExecutionDirective(
                directive_type="CHAOS_CONTAINMENT_MODE", confidence=0.0,
                reason_codes=codes,
                execution_blocked_reason="Archetype suppression or chaos race — no execution",
                recommended_bet_type="NO_BET",
                **base,
            )

        # ── Priority 3: POWER_ANCHOR_MODE ────────────────────────────────────
        if tier == "A" and prob >= 0.40 and cand_ok and not suppressed:
            codes = [f"TIER_A", f"VP={prob:.3f}"]
            if mds >= 0.25:
                codes.append(f"MDS={mds:.2f}")
            if imp >= 0.25:
                codes.append(f"IMP={imp:.2f}")
            if place_p >= 0.75:
                codes.append(f"PLACE={place_p:.2f}")
            return ExecutionDirective(
                directive_type="POWER_ANCHOR_MODE",
                confidence=round(prob, 4),
                reason_codes=codes,
                recommended_bet_type="WIN",
                **base,
            )

        # ── Priority 4: FAVOURITE_LIABILITY_MODE ─────────────────────────────
        if mds >= 0.50 and prob >= 0.30 and tier in ("A", "B") and not suppressed:
            codes = [f"MDS={mds:.2f}", f"VP={prob:.3f}", f"TIER={tier}"]
            if imp >= 0.30:
                codes.append(f"IMP={imp:.2f}")
            return ExecutionDirective(
                directive_type="FAVOURITE_LIABILITY_MODE",
                confidence=round(mds * 0.6 + prob * 0.4, 4),
                reason_codes=codes,
                recommended_bet_type="LAY_FAVOURITE",
                **base,
            )

        # ── Priority 5: MULTI_THREAT_ZONE_MODE ───────────────────────────────
        if prob >= 0.30 and imp >= 0.40:
            codes = [f"VP={prob:.3f}", f"IMP={imp:.2f}"]
            if place_p >= 0.70:
                codes.append(f"PLACE={place_p:.2f}")
            if mds >= 0.30:
                codes.append(f"MDS={mds:.2f}")
            return ExecutionDirective(
                directive_type="MULTI_THREAT_ZONE_MODE",
                confidence=round((prob + imp) / 2, 4),
                reason_codes=codes,
                recommended_bet_type="EACH_WAY",
                **base,
            )

        # ── Priority 6: WATCH_ONLY (VP30+ but gate not met) ──────────────────
        if prob >= 0.30:
            codes = [f"VP={prob:.3f}"]
            blocked_parts = []
            if not exec_ok:
                blocked_parts.append("EXECUTION_GATE_CLOSED")
            if not cand_ok:
                blocked_parts.append("CANDIDATE_GATE_CLOSED")
            if product and product not in ("EW_CANDIDATE",):
                blocked_parts.append(f"PRODUCT={product}")
            enr_f = _f(enr) if enr is not None else 0.0
            if enr_f > 0.50:
                codes.append(f"RACING_API_ENR={enr_f:.2f}")
            return ExecutionDirective(
                directive_type="WATCH_ONLY",
                confidence=round(prob, 4),
                reason_codes=codes,
                execution_blocked_reason="; ".join(blocked_parts) or "VP30+ but no directive match",
                recommended_bet_type="WATCH",
                **base,
            )

        # ── Fallthrough: BLOCKED (sub-threshold) ─────────────────────────────
        return ExecutionDirective(
            directive_type="BLOCKED", confidence=0.0,
            reason_codes=["SUB_THRESHOLD"],
            execution_blocked_reason=f"VP={prob:.3f} below 0.30 threshold",
            recommended_bet_type="NONE",
            **base,
        )

    def _hard_block_reason(self, race_id: str, horse: str, horse_id: str) -> str:
        """Return non-empty string if this verdict must be hard-blocked."""
        if self.mode == "LIVE":
            return "LIVE_MODE_FORBIDDEN"
        if os.getenv("BETFAIR_MODE", "SIM").upper() == "LIVE":
            return "BETFAIR_LIVE_MODE_DETECTED"
        if not race_id:
            return "MISSING_RACE_ID"
        if not horse_id and horse in ("?", "", "None"):
            return "MISSING_HORSE_IDENTIFIERS"
        return ""
