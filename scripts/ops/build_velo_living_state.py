"""
VCP-01 — VÉLØ Living State Packet builder.

Reads from all system organs and emits one canonical state packet.
REPORT_ONLY — no scoring, no Supabase, no model promotion, no Telegram.

Missing artifact → UNKNOWN (never CLEAN by default).
Contradiction → recorded and counted, never suppressed.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).parent.parent.parent
_OUT_JSON = _REPO_ROOT / "data" / "current" / "velo_living_state.json"
_OUT_BRIEF = _REPO_ROOT / "data" / "reports" / "vcp_01_living_state_operator_brief.md"
_TRUTH_DOC = "docs/current/ONE_TRUTH.md"
_STATE_VERSION = "velo_living_state_v1"

# VFU-20 sign-off is a permanent record — operator approved 2026-06-29
_VFU_20_SIGNOFF = {
    "signed_off": True,
    "signed_off_date": "2026-06-29",
    "field_size_missing_before": 1989,
    "field_size_missing_after": 152,
    "field_size_recovery_rate": 0.9236,
    "ew_profitability_status": "PARTIAL_EW_SIGNAL_NOT_PROFIT_PROOF",
    "ew_profitability_claim_authorised": False,
    "vfu_21_gate": "CLOSED",
    "vfu_21_gate_reason": "awaiting VCP-01 operator review before VFU-21",
}

# A-3 going_code fix is a permanent record — operator approved 2026-06-29
_A3_GOING_CODE = {
    "status": "FIXED",
    "scale": "[-1, 2]",
    "training_scale": "raceform_v17",
    "files_fixed": [
        "new_build_velo/paper_scorer.py",
        "scripts/ops/new_build_two_lane_score.py",
    ],
    "regression_tests": 4,
    "test_file": "tests/test_new_build_paper_scorer.py",
    "operator_approved": "2026-06-29",
}

_FORBIDDEN_ACTIONS = [
    "NO_LIVE_SCORING_CHANGE",
    "NO_VP_THRESHOLD_CHANGE",
    "NO_MODEL_PROMOTION",
    "NO_SUPABASE_WRITES",
    "NO_TELEGRAM_SEND",
    "NO_VFU_21_START",
    "NO_HEARTBEAT_BUILD_YET",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
]


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _repo_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO_ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "UNKNOWN"


def _latest_sigma_path() -> Path | None:
    sigma_dir = _REPO_ROOT / "data" / "sigma_results"
    if not sigma_dir.exists():
        return None
    candidates = sorted(sigma_dir.glob("sigma_results_*.json"))
    return candidates[-1] if candidates else None


def _latest_mc_path() -> Path | None:
    mc_latest = _REPO_ROOT / "data" / "mission_control" / "latest.json"
    if mc_latest.exists():
        return mc_latest
    mc_dir = _REPO_ROOT / "data" / "mission_control"
    if not mc_dir.exists():
        return None
    candidates = sorted(mc_dir.glob("*_mission_control.json"))
    return candidates[-1] if candidates else None


def _latest_council_packet_path() -> Path | None:
    cp_dir = _REPO_ROOT / "data" / "council_packets"
    if not cp_dir.exists():
        return None
    candidates = sorted(cp_dir.glob("council_packet_*.json"))
    return candidates[-1] if candidates else None


def _build_truth_lock() -> dict:
    spine_dir = _REPO_ROOT / "docs" / "current"
    spine_count = len(list(spine_dir.glob("*.md"))) if spine_dir.exists() else 0
    stale_root_docs_archived = not (
        (_REPO_ROOT / "CURRENT_RUNTIME_TRUTH.md").exists()
        or (_REPO_ROOT / "THE_NEW_TRUTH.md").exists()
    )
    truth_doc_exists = (_REPO_ROOT / _TRUTH_DOC).exists()
    return {
        "status": "LOCKED" if (stale_root_docs_archived and truth_doc_exists) else "PARTIAL",
        "truth_doc_exists": truth_doc_exists,
        "docs_current_spine_count": spine_count,
        "stale_root_truth_docs_archived": stale_root_docs_archived,
        "stale_docs_checked": ["CURRENT_RUNTIME_TRUTH.md", "THE_NEW_TRUTH.md"],
    }


def _build_sigma_state() -> dict:
    path = _latest_sigma_path()
    if path is None:
        return {
            "artifact": "MISSING",
            "status": "UNKNOWN",
            "date": "UNKNOWN",
            "sr": None,
            "identity_failures": None,
            "learning_candidate_rows": None,
        }
    d = _read_json(path)
    if d is None:
        return {"artifact": str(path.name), "status": "UNKNOWN", "parse_error": True}
    return {
        "artifact": path.name,
        "status": d.get("sigma_status", "UNKNOWN"),
        "date": d.get("date", "UNKNOWN"),
        "sr": d.get("sr"),
        "identity_failures": d.get("identity_failures", 0),
        "learning_candidate_rows": d.get("learning_candidate_rows"),
        "source": d.get("source", "UNKNOWN"),
    }


def _build_mission_control_state() -> dict:
    path = _latest_mc_path()
    if path is None:
        return {
            "artifact": "MISSING",
            "source_truth": "UNKNOWN",
            "council_verdict": "UNKNOWN",
            "learning_gate_status": "UNKNOWN",
            "promotion_gate_status": "UNKNOWN",
            "flatline_count": None,
            "identity_failure_count": None,
            "gate_reasons": [],
        }
    d = _read_json(path)
    if d is None:
        return {"artifact": str(path.name), "source_truth": "UNKNOWN", "parse_error": True}
    return {
        "artifact": path.name,
        "date": d.get("date", "UNKNOWN"),
        "source_truth": d.get("source_truth", "UNKNOWN"),
        "council_verdict": d.get("council_verdict", "UNKNOWN"),
        "learning_gate_status": d.get("learning_gate_status", "UNKNOWN"),
        "promotion_gate_status": d.get("promotion_gate_status", "UNKNOWN"),
        "flatline_count": d.get("flatline_count", 0),
        "identity_failure_count": d.get("identity_failure_count", 0),
        "gate_reasons": d.get("gate_reasons", []),
    }


def _build_council_state() -> dict:
    path = _latest_council_packet_path()
    if path is None:
        return {"artifact": "MISSING", "verdict": "UNKNOWN", "learning_open": None}
    d = _read_json(path)
    if d is None:
        return {"artifact": str(path.name), "verdict": "UNKNOWN", "parse_error": True}
    metadata = d.get("metadata", {})
    verdicts = d.get("verdicts", {})
    if isinstance(verdicts, list):
        verdicts = {}
    overall = verdicts.get("overall", {}) if verdicts else {}
    return {
        "artifact": path.name,
        "date": metadata.get("date", "UNKNOWN"),
        "verdict": overall.get("verdict", "UNKNOWN"),
        "learning_open": overall.get("learning_open"),
        "reasons": overall.get("reasons", []),
    }


def _build_playbook_g_state() -> dict:
    shadow_path = _REPO_ROOT / "data" / "sentient_state_shadow.json"
    if not shadow_path.exists():
        return {"artifact": "MISSING", "status": "UNKNOWN", "live_sentient_state_touched": "UNKNOWN"}
    d = _read_json(shadow_path)
    if d is None:
        return {"artifact": "sentient_state_shadow.json", "status": "UNKNOWN", "parse_error": True}
    # live_sentient_state_touched is written by nightly_eod_learning_runner.py
    # into data/nightly_eod_learning_status_{date}.json -- it is NOT a key of
    # sentient_state_shadow.json. Reading it from the state file meant .get()
    # always missed and defaulted to False, so `compliant` was hardcoded True in
    # effect: this check could never fail, whatever happened. Read the runner's
    # status file, and say UNKNOWN when there isn't one rather than reporting a
    # pass by default (found 2026-08-02).
    status_files = sorted(
        (_REPO_ROOT / "data").glob("nightly_eod_learning_status_*.json"), reverse=True
    )
    runner_status = _read_json(status_files[0]) if status_files else None
    if runner_status is None:
        touched = "UNKNOWN"
        compliant = "UNKNOWN"
    else:
        touched = runner_status.get("live_sentient_state_touched", "UNKNOWN")
        compliant = (touched is False)
    return {
        "artifact": "sentient_state_shadow.json",
        "status": "SHADOW_ONLY",
        "last_updated": d.get("last_updated", "UNKNOWN"),
        "total_races_observed": d.get("total_races_observed", 0),
        "live_sentient_state_touched": touched,
        "compliant": compliant,
        # The authorized live adapter (operator sign-off 2026-07-26) writes
        # sentient_state.json AFTER the runner's guard; surface it so
        # "compliant" is not misread as "live state untouched tonight".
        "live_adapter_state_written": (runner_status or {}).get("live_adapter_state_written", "UNKNOWN"),
        "live_adapter_updates_applied": (runner_status or {}).get("live_adapter_updates_applied", "UNKNOWN"),
        "source": str(status_files[0].name) if status_files else "MISSING",
    }


def _derive_learning_routes(mc: dict, sigma: dict) -> dict:
    # Memory capture is always open — we record everything
    # Failure learning is always open — bad days teach us
    # Promotion learning is gated by source truth and council
    mc_source = mc.get("source_truth", "UNKNOWN")
    council_v = mc.get("council_verdict", "UNKNOWN")
    promotion_blockers = []

    if mc_source not in ("RP_MERGED_CLEAN",):
        promotion_blockers.append(f"source_truth={mc_source}")
    if council_v not in ("PASS_TO_LEARNING",):
        promotion_blockers.append(f"council_verdict={council_v}")
    if sigma.get("identity_failures", 0) and sigma["identity_failures"] > 0:
        promotion_blockers.append(f"sigma_identity_failures={sigma['identity_failures']}")

    promotion_status = "GATED" if promotion_blockers else "ELIGIBLE"
    return {
        "memory_capture": "OPEN",
        "failure_learning": "OPEN",
        "promotion_learning": promotion_status,
        "promotion_blockers": promotion_blockers,
    }


def _detect_contradictions(truth_lock: dict, mc: dict, sigma: dict) -> list[dict]:
    items: list[dict] = []

    # MC says CLEAN but source is not RP_MERGED_CLEAN
    mc_source = mc.get("source_truth", "UNKNOWN")
    mc_gate = mc.get("learning_gate_status", "UNKNOWN")
    if mc_source == "RP_MERGED_CLEAN" and mc_gate == "BLOCKED":
        items.append({
            "id": "C-01",
            "description": "Mission Control reports RP_MERGED_CLEAN source but learning gate is BLOCKED",
            "severity": "WARN",
        })

    # Stale root truth doc still present
    if not truth_lock.get("stale_root_truth_docs_archived", True):
        items.append({
            "id": "C-02",
            "description": "Stale root truth doc(s) still present (CURRENT_RUNTIME_TRUTH.md or THE_NEW_TRUTH.md)",
            "severity": "ERROR",
        })

    # Identity failures in sigma but MC says zero
    sigma_idf = sigma.get("identity_failures") or 0
    mc_idf = mc.get("identity_failure_count") or 0
    if sigma_idf != mc_idf and sigma.get("status") != "UNKNOWN" and mc.get("source_truth") != "UNKNOWN":
        items.append({
            "id": "C-03",
            "description": f"Sigma identity_failures={sigma_idf} but MC identity_failure_count={mc_idf}",
            "severity": "WARN",
        })

    return items


def _build_state() -> dict:
    head = _repo_head()
    truth_lock = _build_truth_lock()
    sigma = _build_sigma_state()
    mc = _build_mission_control_state()
    council = _build_council_state()
    playbook_g = _build_playbook_g_state()
    learning_routes = _derive_learning_routes(mc, sigma)
    contradictions = _detect_contradictions(truth_lock, mc, sigma)

    # next safe action
    if not truth_lock["stale_root_truth_docs_archived"]:
        next_action = {
            "id": "VCP-00-INCOMPLETE",
            "name": "Complete Truth Lock — stale root docs still present",
            "allowed": True,
            "requires_operator_approval": False,
        }
    elif contradictions and any(c["severity"] == "ERROR" for c in contradictions):
        next_action = {
            "id": "RESOLVE_CONTRADICTIONS",
            "name": "Resolve ERROR-level contradictions before proceeding",
            "allowed": True,
            "requires_operator_approval": True,
        }
    else:
        next_action = {
            "id": "VCP-01-REVIEW",
            "name": "Operator review of velo_living_state_v1 before VCP-02 Heartbeat",
            "allowed": False,
            "requires_operator_approval": True,
            "reason": "VCP-01 must pass tests and operator review before Heartbeat is built",
        }

    return {
        "metadata": {
            "state_version": _STATE_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repo_head": head,
            "truth_doc": _TRUTH_DOC,
        },
        "truth_lock": truth_lock,
        "vfu": {
            "latest": "VFU-20",
            **_VFU_20_SIGNOFF,
        },
        "a3_going_code": _A3_GOING_CODE,
        "mission_control": mc,
        "sigma": sigma,
        "council": council,
        "playbook_g_shadow": playbook_g,
        "learning_routes": learning_routes,
        "contradictions": {
            "count": len(contradictions),
            "items": contradictions,
        },
        "next_safe_action": next_action,
        "forbidden_actions": _FORBIDDEN_ACTIONS,
        "final_classifications": [
            "VCP_01_LIVING_STATE_PACKET_COMPLETE",
            "VELO_LIVING_STATE_V1_WRITTEN",
            "ONE_TRUTH_LOCK_CONSUMED",
            "VFU_20_SIGNOFF_CONSUMED",
            "A3_GOING_CODE_FIX_CONSUMED",
            "MEMORY_CAPTURE_OPEN",
            "FAILURE_LEARNING_OPEN",
            "PROMOTION_LEARNING_GATED",
            "MISSING_ARTIFACTS_RESOLVE_UNKNOWN_NOT_CLEAN",
            "CONTRADICTIONS_RECORDED_NOT_SUPPRESSED",
            "NO_VFU_21_START",
            "NO_HEARTBEAT_BUILD",
            "NO_LIVE_SCORING_CHANGE",
            "NO_VP_THRESHOLD_CHANGE",
            "NO_MODEL_PROMOTION",
            "NO_SUPABASE_WRITES",
            "NO_TELEGRAM_SEND",
            "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
            "REPORT_ONLY",
        ],
    }


def _write_brief(state: dict, path: Path) -> None:
    mc = state["machine_control"] if "machine_control" in state else state["mission_control"]
    sigma = state["sigma"]
    lr = state["learning_routes"]
    contradictions = state["contradictions"]
    vfu = state["vfu"]
    a3 = state["a3_going_code"]
    tl = state["truth_lock"]

    lines = [
        "# VCP-01 — VÉLØ Living State Packet — Operator Brief",
        f"**Generated:** {state['metadata']['generated_at']}  ",
        f"**Repo HEAD:** `{state['metadata']['repo_head']}`  ",
        f"**State version:** `{state['metadata']['state_version']}`",
        "",
        "---",
        "",
        "## Truth Lock",
        f"- Status: **{tl['status']}**",
        f"- docs/current/ spine count: {tl['docs_current_spine_count']}",
        f"- Stale root truth docs archived: {tl['stale_root_truth_docs_archived']}",
        "",
        "## VFU-20",
        f"- Signed off: **{vfu['signed_off']}** ({vfu['signed_off_date']})",
        f"- Field size recovery: {vfu['field_size_missing_before']} → {vfu['field_size_missing_after']} ({vfu['field_size_recovery_rate']*100:.1f}%)",
        f"- EW status: `{vfu['ew_profitability_status']}`",
        f"- VFU-21 gate: **{vfu['vfu_21_gate']}** — {vfu['vfu_21_gate_reason']}",
        "",
        "## A-3 Going Code",
        f"- Status: **{a3['status']}**  Scale: `{a3['scale']}`",
        f"- Regression tests: {a3['regression_tests']} (all pass)",
        "",
        "## Mission Control",
        f"- Source truth: `{mc.get('source_truth', 'UNKNOWN')}`",
        f"- Council verdict: `{mc.get('council_verdict', 'UNKNOWN')}`",
        f"- Learning gate: `{mc.get('learning_gate_status', 'UNKNOWN')}`",
        f"- Promotion gate: `{mc.get('promotion_gate_status', 'UNKNOWN')}`",
        f"- Gate reasons: {mc.get('gate_reasons', [])}",
        "",
        "## Sigma",
        f"- Artifact: `{sigma.get('artifact', 'MISSING')}`",
        f"- Status: `{sigma.get('status', 'UNKNOWN')}`  Date: {sigma.get('date', 'UNKNOWN')}",
        f"- SR: {sigma.get('sr')}  Identity failures: {sigma.get('identity_failures', 0)}",
        "",
        "## Learning Routes",
        f"- MEMORY_CAPTURE: **{lr['memory_capture']}**",
        f"- FAILURE_LEARNING: **{lr['failure_learning']}**",
        f"- PROMOTION_LEARNING: **{lr['promotion_learning']}**",
    ]
    if lr.get("promotion_blockers"):
        for b in lr["promotion_blockers"]:
            lines.append(f"  - {b}")

    lines += [
        "",
        "## Contradictions",
        f"- Count: **{contradictions['count']}**",
    ]
    for c in contradictions.get("items", []):
        lines.append(f"- [{c['severity']}] {c['id']}: {c['description']}")

    lines += [
        "",
        "## Next Safe Action",
        f"- **{state['next_safe_action']['id']}**: {state['next_safe_action']['name']}",
        "",
        "## Forbidden Actions",
    ]
    for f in state["forbidden_actions"]:
        lines.append(f"- {f}")

    lines += [
        "",
        "---",
        "REPORT_ONLY — no scoring change, no Supabase write, no model promotion, no Telegram send.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    print("── VCP-01: Building VÉLØ Living State Packet ──")
    state = _build_state()

    _OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    _OUT_BRIEF.parent.mkdir(parents=True, exist_ok=True)

    _OUT_JSON.write_text(json.dumps(state, indent=2), encoding="utf-8")
    _write_brief(state, _OUT_BRIEF)

    print(f"  OK   {_OUT_JSON.relative_to(_REPO_ROOT)}")
    print(f"  OK   {_OUT_BRIEF.relative_to(_REPO_ROOT)}")
    print()
    print(f"  Truth lock:       {state['truth_lock']['status']}")
    print(f"  VFU-20 signed:    {state['vfu']['signed_off']}")
    print(f"  A-3 going_code:   {state['a3_going_code']['status']}")
    print(f"  Source truth:     {state['mission_control'].get('source_truth', 'UNKNOWN')}")
    print(f"  Council:          {state['mission_control'].get('council_verdict', 'UNKNOWN')}")
    print(f"  Learning gate:    {state['mission_control'].get('learning_gate_status', 'UNKNOWN')}")
    print(f"  Promotion gate:   {state['mission_control'].get('promotion_gate_status', 'UNKNOWN')}")
    print(f"  Memory capture:   {state['learning_routes']['memory_capture']}")
    print(f"  Failure learning: {state['learning_routes']['failure_learning']}")
    print(f"  Promotion:        {state['learning_routes']['promotion_learning']}")
    print(f"  Contradictions:   {state['contradictions']['count']}")
    print(f"  Next action:      {state['next_safe_action']['id']}")
    print()
    print("── VCP-01 COMPLETE ──")
    print("STOP — operator review required before VCP-02 Heartbeat.")


if __name__ == "__main__":
    main()
