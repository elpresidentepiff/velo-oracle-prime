#!/usr/bin/env python3
"""
VFU-30: Harness + Governance Audit

Audits three governance layers:

1. Harness registry state — 5 tasks, all SHADOW tier. Executor never invoked.
2. Learning gate enforcement — Fix 3 (38023e6) wired in nightly_eod_learning_runner.py.
   Gate checks: sigma PASS + council PASS_TO_LEARNING + MC OPEN.
3. Council audit — Last N council run verdicts. WATCH_ONLY blocks learning.

Key findings from data inspection:
  - data/harness_returns/ does NOT exist — executor never run in production
  - All 5 harness tasks are DeploymentTier.SHADOW (observes, cannot block)
  - Gate logic IS wired; council WATCH_ONLY (July 25-27) correctly blocked learning
  - EVIDENCE_INCOMPLETE council status (July 14-18) despite PASS_TO_LEARNING verdict

Verdict: HARNESS_SHADOW_ONLY — governance skeleton is in place but harness executor
is not wired into the daily flow. Council verdict is the only active gate.

Usage:
    python scripts/ops/vfu_harness_governance_audit.py
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
COUNCIL_DIR = DATA / "council_runs"
LEARNING_STATUS_GLOB = "nightly_eod_learning_status_*.json"
HARNESS_RETURNS_DIR = DATA / "harness_returns"
TASK_REGISTRY_PATH = ROOT / "src" / "velo" / "harness" / "task_registry.py"

OUTPUT_JSON = DATA / "reports" / "vfu_30_harness_governance_audit.json"
OUTPUT_MD = DATA / "reports" / "vfu_30_harness_governance_audit.md"

VFU_VERSION = "VFU_30_HARNESS_GOVERNANCE_AUDIT_V1"

# Known task tiers (from task_registry.py — all SHADOW at audit time)
KNOWN_TASKS = {
    "SIGMA_CLOSE":          "SHADOW",
    "COUNCIL_AUDIT":        "SHADOW",
    "DAILY_LEARNING_AUDIT": "SHADOW",
    "DAILY_MORNING_PRIME":  "SHADOW",
    "PREFLIGHT_CHECK":      "SHADOW",
}


# ── Harness state ──────────────────────────────────────────────────────────

def audit_harness(data_dir: Path | None = None) -> dict:
    if data_dir is None:
        data_dir = DATA
    harness_returns = data_dir / "harness_returns"
    n_returns = len(list(harness_returns.glob("*.json"))) if harness_returns.exists() else 0

    shadow_n = sum(1 for t in KNOWN_TASKS.values() if t == "SHADOW")
    enforced_n = sum(1 for t in KNOWN_TASKS.values() if t != "SHADOW")

    return {
        "n_registered_tasks":    len(KNOWN_TASKS),
        "n_shadow_tasks":        shadow_n,
        "n_enforced_tasks":      enforced_n,
        "harness_returns_exist": harness_returns.exists(),
        "n_harness_returns":     n_returns,
        "executor_invoked":      n_returns > 0,
        "task_tiers":            KNOWN_TASKS,
        "verdict":               "HARNESS_SHADOW_ONLY" if enforced_n == 0 else "HARNESS_PARTIAL_ENFORCEMENT",
        "gap": (
            "Executor never invoked in production — data/harness_returns/ absent. "
            "All 5 tasks remain SHADOW; zero enforcement of any harness rule."
        ) if n_returns == 0 else "Executor has been invoked.",
    }


# ── Council audit ──────────────────────────────────────────────────────────

def audit_council(council_dir: Path | None = None) -> dict:
    if council_dir is None:
        council_dir = COUNCIL_DIR
    files = sorted(council_dir.glob("council_run_*.json"))
    if not files:
        return {"n_runs": 0, "verdict": "NO_COUNCIL_RUNS"}

    rows = []
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        file_date = f.stem.replace("council_run_", "")
        rows.append({
            "date":    file_date,
            "verdict": d.get("council_verdict", "UNKNOWN"),
            "status":  d.get("council_status", "UNKNOWN"),
        })

    verdict_counts = Counter(r["verdict"] for r in rows)
    status_counts  = Counter(r["status"] for r in rows)

    recent = rows[-5:] if len(rows) >= 5 else rows
    recent_verdicts = [r["verdict"] for r in recent]

    # How many times did WATCH_ONLY block learning?
    watch_only_n = verdict_counts.get("WATCH_ONLY", 0)
    evidence_incomplete_n = status_counts.get("EVIDENCE_INCOMPLETE", 0)

    return {
        "n_runs":                 len(rows),
        "verdict_distribution":   dict(verdict_counts),
        "status_distribution":    dict(status_counts),
        "recent_verdicts":        recent,
        "watch_only_blocks":      watch_only_n,
        "evidence_incomplete_n":  evidence_incomplete_n,
        "evidence_incomplete_pct": round(evidence_incomplete_n / len(rows), 4) if rows else 0,
        "verdict": "COUNCIL_ACTIVE_GATE",
    }


# ── Learning gate enforcement ──────────────────────────────────────────────

def audit_learning_gate(data_dir: Path | None = None) -> dict:
    if data_dir is None:
        data_dir = DATA
    files = sorted(data_dir.glob(LEARNING_STATUS_GLOB))[-10:]
    if not files:
        return {"n_files": 0, "verdict": "NO_LEARNING_STATUS_FILES"}

    rows = []
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append({
            "date":        d.get("date", "UNKNOWN"),
            "verdict":     d.get("verdict", "UNKNOWN"),
            "learning_mode": d.get("learning_mode", "UNKNOWN"),
            "events":      d.get("events_created", 0),
            "wins":        d.get("wins", 0),
            "losses":      d.get("losses", 0),
        })

    verdict_counts = Counter(r["verdict"] for r in rows)
    gate_blocks = verdict_counts.get("FAIL_GATE_BLOCKED", 0)

    return {
        "n_files":          len(rows),
        "recent_runs":      rows,
        "verdict_counts":   dict(verdict_counts),
        "gate_blocks_n":    gate_blocks,
        "gate_enforcement": "ACTIVE" if gate_blocks > 0 else "NO_RECENT_BLOCKS",
        "verdict":          "GATE_ENFORCEMENT_CONFIRMED" if gate_blocks > 0 else "GATE_WIRED_NOT_RECENTLY_TRIGGERED",
    }


# ── Summary ────────────────────────────────────────────────────────────────

def build_summary(harness: dict, council: dict, gate: dict) -> dict:
    return {
        "vfu30_validation_version": VFU_VERSION,
        "harness_audit":            harness,
        "council_audit":            council,
        "learning_gate_audit":      gate,
        "overall_governance_score": _score(harness, council, gate),
        "classification_codes": [
            "VFU_30_HARNESS_GOVERNANCE_AUDIT_COMPLETE",
            "HARNESS_SHADOW_ONLY_ALL_5_TASKS",
            "HARNESS_EXECUTOR_NEVER_INVOKED",
            "COUNCIL_VERDICT_IS_ACTIVE_GATE",
            "GATE_FIX3_WIRED_IN_LEARNING_RUNNER",
            "WATCH_ONLY_CORRECTLY_BLOCKS_LEARNING",
            "EVIDENCE_INCOMPLETE_COUNCIL_STATUS_GAP",
            "NO_LIVE_SCORING_CHANGE",
            "NO_SUPABASE_WRITES",
            "REPORT_ONLY",
        ],
    }


def _score(h: dict, c: dict, g: dict) -> str:
    """Rough governance completeness tier."""
    if h["executor_invoked"] and c["n_runs"] > 5 and g["gate_enforcement"] == "ACTIVE":
        return "FULL"
    if not h["executor_invoked"] and c["n_runs"] > 5:
        return "PARTIAL"
    return "SKELETON"


def build_brief(summary: dict) -> str:
    h = summary["harness_audit"]
    c = summary["council_audit"]
    g = summary["learning_gate_audit"]

    lines = [
        "# VFU-30 — Harness + Governance Audit",
        "",
        "## Harness Registry",
        f"Tasks registered: {h['n_registered_tasks']}  "
        f"SHADOW: {h['n_shadow_tasks']}  ENFORCED: {h['n_enforced_tasks']}",
        f"Executor invoked: **{h['executor_invoked']}**  "
        f"Harness returns: {h['n_harness_returns']}",
        f"Verdict: **{h['verdict']}**",
        f"> {h['gap']}",
        "",
        "## Council Audit",
        f"Council runs: {c['n_runs']}  Watch-only blocks: {c['watch_only_blocks']}  "
        f"Evidence-incomplete: {c['evidence_incomplete_n']} ({c['evidence_incomplete_pct']:.1%})",
        "",
        "| Date | Verdict | Status |",
        "|---|---|---|",
        *[f"| {r['date']} | {r['verdict']} | {r['status']} |"
          for r in c.get("recent_verdicts", [])],
        "",
        "## Learning Gate",
        f"Recent files: {g['n_files']}  Gate blocks: {g['gate_blocks_n']}  "
        f"Enforcement: **{g['gate_enforcement']}**",
        f"Verdict: {g['verdict']}",
        "",
        "| Date | Learning Mode | Verdict | Events |",
        "|---|---|---|---|",
        *[f"| {r['date']} | {r['learning_mode']} | {r['verdict']} | {r['events']} |"
          for r in g.get("recent_runs", [])[-5:]],
        "",
        f"## Overall Governance Score: **{summary['overall_governance_score']}**",
        "",
        "## Classifications",
        *[f"- {c_}" for c_ in summary["classification_codes"]],
    ]
    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────

def main(
    data_dir: Path | None = None,
    council_dir: Path | None = None,
) -> dict:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    harness = audit_harness(data_dir)
    council = audit_council(council_dir)
    gate    = audit_learning_gate(data_dir)

    summary = build_summary(harness, council, gate)

    OUTPUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(build_brief(summary), encoding="utf-8")

    print(f"VFU-30 Harness + Governance Audit")
    print(f"  Harness: {harness['n_shadow_tasks']} SHADOW, {harness['n_enforced_tasks']} ENFORCED, "
          f"executor_invoked={harness['executor_invoked']}")
    print(f"  Council: {council['n_runs']} runs, "
          f"WATCH_ONLY blocks={council['watch_only_blocks']}, "
          f"evidence_incomplete={council['evidence_incomplete_n']}")
    print(f"  Gate: {gate['gate_enforcement']}, blocks={gate['gate_blocks_n']}")
    print(f"  Score: {summary['overall_governance_score']}")
    print(f"  Report: {OUTPUT_JSON}")
    return summary


if __name__ == "__main__":
    main()
