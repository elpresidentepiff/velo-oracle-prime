"""
VÉLØ LLM Council — real post-Sigma tribunal agents.

Each agent reads local evidence artifacts and returns a structured verdict.
No LLM API calls. Deterministic rule-based checks with explicit conditions.

Council verdicts (Prime Chair only):
  PASS_TO_LEARNING      — all gates pass, learning consume allowed
  QUARANTINE_DAY        — contaminated run detected, block all learning
  RERUN_AFTER_FIX       — identity or flatline failure, fix required first
  WATCH_ONLY            — marginal day, accumulate evidence but no consume

Governance correction (permanent):
  Council DOES NOT block sigma_audits truth writes.
  Council blocks: learning admission, shadow consume, promotion evidence.
"""

import glob
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[3]

CONTAMINATED_RUN_IDS = {"32cc27f9", "847964a6"}
BASELINE_SR = 0.20

# ── Council label taxonomy — single source of truth ───────────────────────
# These were local variables inside PrimeChair.run(). They are module-level
# constants now because update_mission_control.py and
# nightly_eod_learning_runner.py both have to reason about the SAME sets, and
# a second hand-maintained copy of a label list is exactly how the
# "near-identical names on non-identical things" failures in ONE_TRUTH began.
BLOCKING_LABELS = {
    "FLATLINE_BLOCK", "CONTAMINATION_DETECTED", "CONTAMINATED",
    "SOURCE_CONTAMINATED", "SR_BELOW_HALF_BASELINE",
}
WATCH_LABELS = {
    "SR_BELOW_BASELINE", "SOURCE_UNKNOWN", "SIGMA_MISSING",
    "MISSING_SNAPSHOTS", "MIDPRICE_NOT_BUILT",
}

# Labels that describe HOW THE MODEL PERFORMED, not whether the day's data can
# be trusted. A low strike rate is a fact about the picks; it says nothing about
# whether the capture, identity resolution or reconciliation were sound.
#
# Operator ruling 2026-08-02: "LEARNING HAS TO HAPPEN EVERY DAY EVEN ON
# DEGRADED DAYS". A day the model called badly is the day most worth learning
# from -- holding it out biases the evidence base toward days the model already
# handled well. Before this, 2026-08-03 (32/32 reconciled, 0 identity failures,
# 100% PDF enrichment, SR 15.6%) was held out of learning purely for SR.
#
# Everything NOT in this set stays a hard block. Contamination, flatlines,
# unknown source, missing sigma and missing snapshots all mean the day's data
# cannot be trusted, and learning from untrustworthy data is worse than not
# learning at all.
PERFORMANCE_ONLY_LABELS = {"SR_BELOW_BASELINE", "SR_BELOW_HALF_BASELINE"}


def learning_disposition(agent_responses: List[Dict]) -> Dict:
    """Decide whether learning may consume this day, and say why.

    Returns {allowed, disposition, performance_reasons, integrity_reasons}.

      allowed=True  disposition=CLEAN                  no adverse labels
      allowed=True  disposition=DEGRADED_PERFORMANCE   only SR labels fired
      allowed=False disposition=INTEGRITY_BLOCKED      a data-trust label fired

    DEGRADED_PERFORMANCE days are learned from AND labelled, so a later audit
    can tell a bad-picks day from a clean one without re-deriving it.
    """
    # No agent responses means the Council produced no evidence, which is not
    # the same as producing clean evidence. Treating it as CLEAN would be the
    # identical fail-open this function exists to close (CLAUDE.md Law 5:
    # missing = UNKNOWN, never a default pass).
    if not agent_responses:
        return {
            "allowed": False,
            "disposition": "NO_AGENT_RESPONSES",
            "performance_reasons": [],
            "integrity_reasons": ["council run contained no agent responses"],
        }

    integrity: list = []
    performance: list = []
    for resp in agent_responses:
        labels = set(resp.get("labels", []))
        agent = resp.get("agent", "?")
        for lab in sorted(labels & (BLOCKING_LABELS | WATCH_LABELS)):
            (performance if lab in PERFORMANCE_ONLY_LABELS else integrity).append(
                f"{agent}: {lab}"
            )
    if integrity:
        disposition = "INTEGRITY_BLOCKED"
    elif performance:
        disposition = "DEGRADED_PERFORMANCE"
    else:
        disposition = "CLEAN"
    return {
        "allowed": not integrity,
        "disposition": disposition,
        "performance_reasons": performance,
        "integrity_reasons": integrity,
    }


def _extract_sha8(run_id: str) -> str:
    parts = run_id.split("_")
    if len(parts) >= 4:
        return parts[3]
    return run_id[:8]


def _load_mc(date_str: str) -> dict:
    p = ROOT / "data" / "mission_control" / f"{date_str}_mission_control.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {}


def _load_sigma(date_str: str) -> dict:
    date_und = date_str.replace("-", "_")
    candidates = [
        ROOT / "data" / "sigma_results" / f"sigma_results_{date_und}.json",
        ROOT / "data" / f"sigma_results_{date_und}.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                pass
    return {}


def _load_snapshots_meta(date_str: str) -> dict:
    date_und = date_str.replace("-", "_")
    patterns = [
        str(ROOT / "data" / f"runner_snapshots_{date_str}*.jsonl"),
        str(ROOT / "data" / f"runner_snapshots_{date_und}*.jsonl"),
    ]
    files = []
    seen = set()
    for pat in patterns:
        for f in glob.glob(pat):
            if f not in seen:
                seen.add(f)
                files.append(Path(f).name)
    run_ids = set()
    for name in files:
        parts = Path(name).stem.split("_")
        if len(parts) >= 4:
            run_ids.add(parts[3])
    return {"snapshot_files": files, "run_ids": sorted(run_ids)}


class CouncilAgent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    def run(self, evidence_packet: Dict) -> Dict:
        raise NotImplementedError


class DataAuditor(CouncilAgent):
    def __init__(self):
        super().__init__("DATA AUDITOR", "Data Quality Verification")

    def run(self, evidence_packet: Dict) -> Dict:
        date_str = evidence_packet.get("metadata", {}).get("date", "")
        mc = _load_mc(date_str)
        snap = _load_snapshots_meta(date_str)

        issues = []
        labels = []

        flatline = mc.get("flatline_count", 0)
        if flatline > 0:
            issues.append(f"FLATLINE: {flatline} fully-uniform races detected")
            labels.append("FLATLINE")

        contaminated = set(snap["run_ids"]) & CONTAMINATED_RUN_IDS
        if contaminated:
            issues.append(f"CONTAMINATED_RUN_IDS: {sorted(contaminated)}")
            labels.append("CONTAMINATED")

        if not snap["snapshot_files"]:
            issues.append("NO_SNAPSHOTS: no runner snapshot files found for date")
            labels.append("MISSING_SNAPSHOTS")

        source = mc.get("source_truth", "UNKNOWN")
        if source == "RP_MERGED_CONTAMINATED":
            labels.append("SOURCE_CONTAMINATED")
        elif source == "UNKNOWN":
            labels.append("SOURCE_UNKNOWN")

        if not issues:
            labels.append("DATA_CLEAN")
            response = f"Data audit PASS — source={source}, snapshots={len(snap['snapshot_files'])}, flatlines=0"
        else:
            response = "Data audit FAIL — " + " | ".join(issues)

        return {
            "agent": self.name,
            "role": self.role,
            "response": response,
            "labels": labels,
            "data": {
                "flatline_count": flatline,
                "contaminated_run_ids": sorted(contaminated),
                "snapshot_files": snap["snapshot_files"],
                "source_truth": source,
            },
        }


class FlatlineGateAgent(CouncilAgent):
    def __init__(self):
        super().__init__("FLATLINE GATE", "Scoring Integrity Check")

    def run(self, evidence_packet: Dict) -> Dict:
        date_str = evidence_packet.get("metadata", {}).get("date", "")
        mc = _load_mc(date_str)

        flatline = mc.get("flatline_count", 0)
        uniform_races = mc.get("fully_uniform_races", [])
        source = mc.get("source_truth", "UNKNOWN")

        if flatline > 0:
            return {
                "agent": self.name,
                "role": self.role,
                "response": (
                    f"FLATLINE BLOCK — {flatline} fully-uniform races: {uniform_races}. "
                    f"source={source}. Learning blocked. Do not consume. Check RP_MERGED hydration."
                ),
                "labels": ["FLATLINE_BLOCK", "LEARNING_BLOCKED"],
                "data": {"flatline_count": flatline, "uniform_races": uniform_races},
            }

        return {
            "agent": self.name,
            "role": self.role,
            "response": f"Flatline gate PASS — no uniform races detected. source={source}",
            "labels": ["FLATLINE_PASS"],
            "data": {"flatline_count": 0},
        }


class SigmaCoverageAgent(CouncilAgent):
    def __init__(self):
        super().__init__("SIGMA COVERAGE", "Result Coverage Check")

    def run(self, evidence_packet: Dict) -> Dict:
        date_str = evidence_packet.get("metadata", {}).get("date", "")
        sigma = _load_sigma(date_str)
        mc = _load_mc(date_str)

        runners_snap = mc.get("runners_snapshotted", 0)
        sigma_rows = sigma.get("total_rows", sigma.get("audit_rows", 0))
        wins = sigma.get("wins", 0)
        total_reviewed = sigma.get("total_reviewed", sigma_rows)
        sr = wins / total_reviewed if total_reviewed > 0 else 0.0

        labels = []
        if total_reviewed == 0:
            labels.append("SIGMA_MISSING")
            response = "No sigma results found for date — cannot evaluate coverage"
        elif sr < BASELINE_SR * 0.5:
            labels.append("SR_BELOW_HALF_BASELINE")
            response = f"SR={sr:.1%} — significantly below baseline {BASELINE_SR:.0%}. Possible contamination."
        elif sr < BASELINE_SR:
            labels.append("SR_BELOW_BASELINE")
            response = f"SR={sr:.1%} — below baseline {BASELINE_SR:.0%}. Watchlist day."
        else:
            labels.append("SR_ABOVE_BASELINE")
            response = f"SR={sr:.1%} — at or above baseline {BASELINE_SR:.0%}. Coverage OK."

        return {
            "agent": self.name,
            "role": self.role,
            "response": response,
            "labels": labels,
            "data": {
                "sigma_rows": sigma_rows,
                "wins": wins,
                "total_reviewed": total_reviewed,
                "sr": round(sr, 4),
            },
        }


class ContaminationDetectorAgent(CouncilAgent):
    def __init__(self):
        super().__init__("CONTAMINATION DETECTOR", "Run ID Contamination Check")

    def run(self, evidence_packet: Dict) -> Dict:
        date_str = evidence_packet.get("metadata", {}).get("date", "")
        snap = _load_snapshots_meta(date_str)

        contaminated = set(snap["run_ids"]) & CONTAMINATED_RUN_IDS
        clean = set(snap["run_ids"]) - CONTAMINATED_RUN_IDS

        if contaminated:
            return {
                "agent": self.name,
                "role": self.role,
                "response": (
                    f"CONTAMINATED run_ids detected: {sorted(contaminated)}. "
                    f"Clean runs also present: {sorted(clean)}. "
                    f"Gate V2 must exclude contaminated rows. Learning blocked."
                ),
                "labels": ["CONTAMINATION_DETECTED", "GATE_V2_EXCLUDE"],
                "data": {"contaminated": sorted(contaminated), "clean": sorted(clean)},
            }

        return {
            "agent": self.name,
            "role": self.role,
            "response": f"No contaminated run_ids. Clean runs: {sorted(clean)}",
            "labels": ["CONTAMINATION_CLEAR"],
            "data": {"contaminated": [], "clean": sorted(clean)},
        }


class MidPriceSummaryAgent(CouncilAgent):
    def __init__(self):
        super().__init__("MIDPRICE SUMMARY", "Mid-Price Leak Summary")

    def run(self, evidence_packet: Dict) -> Dict:
        delta_path = ROOT / "data" / "midprice_winner_deltas.csv"
        latest_path = ROOT / "data" / "reports" / "midprice_winner_delta_latest.json"

        if latest_path.exists():
            try:
                d = json.loads(latest_path.read_text())
                n = d.get("total_races", 0)
                rescued = d.get("rescued_by_sidecar", 0)
                pct = rescued / n * 100 if n > 0 else 0
                return {
                    "agent": self.name,
                    "role": self.role,
                    "response": f"Mid-price delta: {n} races, {rescued} rescuable by sidecar ({pct:.1f}%). Shadow audit only.",
                    "labels": ["MIDPRICE_AUDITED"],
                    "data": d,
                }
            except Exception:
                pass

        if delta_path.exists():
            n_rows = sum(1 for _ in open(delta_path)) - 1
            return {
                "agent": self.name,
                "role": self.role,
                "response": f"Mid-price delta CSV exists ({n_rows} rows). Run midprice_winner_delta.py for full summary.",
                "labels": ["MIDPRICE_CSV_ONLY"],
                "data": {"csv_rows": n_rows},
            }

        return {
            "agent": self.name,
            "role": self.role,
            "response": "Mid-price delta not yet built. Run scripts/audit/midprice_winner_delta.py post-sigma.",
            "labels": ["MIDPRICE_NOT_BUILT"],
            "data": {},
        }


class PrimeChair(CouncilAgent):
    def __init__(self):
        super().__init__("PRIME CHAIR", "Final Synthesis and Governance")

    def run(self, evidence_packet: Dict) -> Dict:
        date_str = evidence_packet.get("metadata", {}).get("date", "")
        agent_responses = evidence_packet.get("_agent_responses", [])

        blocking_labels = BLOCKING_LABELS
        watch_labels = WATCH_LABELS

        all_labels: set = set()
        blocking_reasons: list = []
        watch_reasons: list = []

        for resp in agent_responses:
            labels = set(resp.get("labels", []))
            all_labels.update(labels)
            hit = labels & blocking_labels
            if hit:
                blocking_reasons.append(f"{resp['agent']}: {', '.join(sorted(hit))}")
            hit2 = labels & watch_labels
            if hit2:
                watch_reasons.append(f"{resp['agent']}: {', '.join(sorted(hit2))}")

        if blocking_reasons:
            verdict = "QUARANTINE_DAY"
            summary = (
                f"QUARANTINE_DAY — {date_str}. "
                f"Learning blocked. Shadow consume blocked. Promotion evidence blocked. "
                f"sigma_audits truth records are preserved. "
                f"Blocking: {'; '.join(blocking_reasons)}"
            )
        elif watch_reasons:
            verdict = "WATCH_ONLY"
            summary = (
                f"WATCH_ONLY — {date_str}. "
                f"Evidence accumulation continues. Do not consume for learning yet. "
                f"Watch: {'; '.join(watch_reasons)}"
            )
        else:
            verdict = "PASS_TO_LEARNING"
            summary = (
                f"PASS_TO_LEARNING — {date_str}. "
                f"All gates clear. Learning consume permitted if operator approves."
            )

        return {
            "agent": self.name,
            "role": self.role,
            "response": summary,
            "labels": ["SHADOW", "OPERATOR_ONLY"],
            "council_verdict": verdict,
            "blocking_reasons": blocking_reasons,
            "watch_reasons": watch_reasons,
        }


def get_v01_council() -> List[CouncilAgent]:
    return [
        DataAuditor(),
        FlatlineGateAgent(),
        SigmaCoverageAgent(),
        ContaminationDetectorAgent(),
        MidPriceSummaryAgent(),
        PrimeChair(),
    ]
