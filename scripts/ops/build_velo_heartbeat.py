"""
VCP-02 — VÉLØ Heartbeat V1.

Reads ONLY from data/current/velo_living_state.json.
No direct organ reads. No Supabase. No scoring. No Telegram. REPORT_ONLY.

The Living State is the nervous system.
The Heartbeat is its voice.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).parent.parent.parent
_LIVING_STATE = _REPO_ROOT / "data" / "current" / "velo_living_state.json"
_OUT_MD = _REPO_ROOT / "data" / "reports" / "velo_heartbeat_latest.md"
_OUT_JSON = _REPO_ROOT / "data" / "reports" / "velo_heartbeat_latest.json"
_OUT_BRIEF = _REPO_ROOT / "data" / "reports" / "vcp_02_heartbeat_operator_brief.md"
_HEARTBEAT_VERSION = "velo_heartbeat_v1"

_FORBIDDEN_ACTIONS = [
    "NO_LIVE_SCORING_CHANGE",
    "NO_VP_THRESHOLD_CHANGE",
    "NO_MODEL_PROMOTION",
    "NO_SUPABASE_WRITES",
    "NO_TELEGRAM_SEND",
    "NO_VFU_21_START",
    "NO_CASE_MEMORY_BUILD",
    "NO_DEEPSEARCHER_BUILD",
    "NO_AGENT_BROWSER_BUILD",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
    "REPORT_ONLY",
]


def _load_living_state() -> dict | None:
    if not _LIVING_STATE.exists():
        return None
    try:
        return json.loads(_LIVING_STATE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _get(d: dict, *keys: str, default: Any = "UNKNOWN") -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
        if cur is default:
            return default
    return cur


def _source_truth_note(source_truth: str) -> str:
    if source_truth == "RP_MERGED_CLEAN":
        return "Source verified — promotion eligible if council agrees."
    if source_truth == "LOCAL_JSON_FALLBACK":
        return "Not RP_MERGED_CLEAN — promotion gated until source is verified."
    if source_truth == "DEGRADED":
        return "Source degraded — promotion blocked, failure learning open."
    return f"Source status unknown ({source_truth}) — promotion gated."


def _build_heartbeat_from_state(state: dict) -> dict:
    meta = state.get("metadata", {})
    tl = state.get("truth_lock", {})
    vfu = state.get("vfu", {})
    a3 = state.get("a3_going_code", {})
    mc = state.get("mission_control", {})
    sigma = state.get("sigma", {})
    council = state.get("council", {})
    pg = state.get("playbook_g_shadow", {})
    lr = state.get("learning_routes", {})
    contradictions = state.get("contradictions", {"count": 0, "items": []})
    next_action = state.get("next_safe_action", {"id": "UNKNOWN", "name": "UNKNOWN"})

    source_truth = mc.get("source_truth", "UNKNOWN")
    council_verdict = mc.get("council_verdict", "UNKNOWN")
    promotion_status = lr.get("promotion_learning", "UNKNOWN")
    promotion_blockers = lr.get("promotion_blockers", [])

    operator_decisions: list[str] = []
    if next_action.get("requires_operator_approval"):
        operator_decisions.append(next_action["name"])

    return {
        "heartbeat_version": _HEARTBEAT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "living_state_version": meta.get("state_version", "UNKNOWN"),
        "living_state_generated_at": meta.get("generated_at", "UNKNOWN"),
        "repo_head": meta.get("repo_head", "UNKNOWN"),
        "sections": {
            "system_status": {
                "truth_lock": tl.get("status", "UNKNOWN"),
                "spine_count": tl.get("docs_current_spine_count", "UNKNOWN"),
                "stale_docs_archived": tl.get("stale_root_truth_docs_archived", False),
                "repo_head": meta.get("repo_head", "UNKNOWN"),
            },
            "source_truth": {
                "status": source_truth,
                "note": _source_truth_note(source_truth),
            },
            "vfu_status": {
                "latest": vfu.get("latest", "UNKNOWN"),
                "signed_off": vfu.get("signed_off", False),
                "signed_off_date": vfu.get("signed_off_date", "UNKNOWN"),
                "field_size_recovery_rate": vfu.get("field_size_recovery_rate"),
                "field_size_missing_before": vfu.get("field_size_missing_before"),
                "field_size_missing_after": vfu.get("field_size_missing_after"),
                "ew_profitability_status": vfu.get("ew_profitability_status", "UNKNOWN"),
                "vfu_21_gate": vfu.get("vfu_21_gate", "UNKNOWN"),
            },
            "a3_going_code": {
                "status": a3.get("status", "UNKNOWN"),
                "scale": a3.get("scale", "UNKNOWN"),
                "regression_tests": a3.get("regression_tests", 0),
            },
            "council_verdict": {
                "verdict": council_verdict,
                "learning_gate": mc.get("learning_gate_status", "UNKNOWN"),
                "promotion_gate": mc.get("promotion_gate_status", "UNKNOWN"),
                "gate_reasons": mc.get("gate_reasons", []),
                "sigma_date": sigma.get("date", "UNKNOWN"),
                "sigma_status": sigma.get("status", "UNKNOWN"),
                "sigma_sr": sigma.get("sr"),
                "identity_failures": sigma.get("identity_failures", 0),
            },
            "learning_routes": {
                "memory_capture": lr.get("memory_capture", "UNKNOWN"),
                "failure_learning": lr.get("failure_learning", "UNKNOWN"),
                "promotion_learning": promotion_status,
                "promotion_blockers": promotion_blockers,
            },
            "contradictions": {
                "count": contradictions.get("count", 0),
                "items": contradictions.get("items", []),
            },
            "playbook_g_shadow": {
                "status": pg.get("status", "UNKNOWN"),
                "live_sentient_state_touched": pg.get("live_sentient_state_touched", "UNKNOWN"),
                "compliant": pg.get("compliant", "UNKNOWN"),
            },
            "next_safe_action": next_action,
            "forbidden_actions": _FORBIDDEN_ACTIONS,
            "operator_decisions_needed": operator_decisions,
        },
        "final_classifications": [
            "VCP_02_HEARTBEAT_V1_COMPLETE",
            "HEARTBEAT_READS_LIVING_STATE_ONLY",
            "VELO_HEARTBEAT_MD_WRITTEN",
            "VELO_HEARTBEAT_JSON_WRITTEN",
            "MEMORY_CAPTURE_OPEN_RENDERED",
            "FAILURE_LEARNING_OPEN_RENDERED",
            "PROMOTION_LEARNING_GATED_RENDERED",
            "CONTRADICTIONS_RENDERED",
            "MISSING_LIVING_STATE_RESOLVES_UNKNOWN_NOT_CLEAN",
            "NO_VFU_21_START",
            "NO_CASE_MEMORY_BUILD",
            "NO_HEARTBEAT_DIRECT_ORGAN_READS",
            "NO_LIVE_SCORING_CHANGE",
            "NO_VP_THRESHOLD_CHANGE",
            "NO_MODEL_PROMOTION",
            "NO_SUPABASE_WRITES",
            "NO_TELEGRAM_SEND",
            "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
            "REPORT_ONLY",
        ],
    }


def _build_unavailable_heartbeat(reason: str) -> dict:
    return {
        "heartbeat_version": _HEARTBEAT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "HEARTBEAT_UNAVAILABLE",
        "reason": reason,
        "instruction": "Run: python scripts/ops/build_velo_living_state.py",
        "sections": {
            "system_status": {"truth_lock": "UNKNOWN"},
            "source_truth": {"status": "UNKNOWN", "note": "Living state missing — cannot determine source truth."},
            "learning_routes": {
                "memory_capture": "UNKNOWN",
                "failure_learning": "UNKNOWN",
                "promotion_learning": "UNKNOWN",
                "promotion_blockers": ["living_state_missing"],
            },
            "contradictions": {"count": 0, "items": []},
            "forbidden_actions": _FORBIDDEN_ACTIONS,
            "operator_decisions_needed": ["Regenerate living state before heartbeat can report."],
        },
    }


def _render_md(hb: dict) -> str:
    unavailable = hb.get("status") == "HEARTBEAT_UNAVAILABLE"
    ts = hb["generated_at"]
    head = hb.get("repo_head", "UNKNOWN")
    s = hb.get("sections", {})

    lines = [
        "# VÉLØ HEARTBEAT",
        f"**{ts}** | HEAD `{head}` | `{_HEARTBEAT_VERSION}`",
        "",
        "---",
    ]

    if unavailable:
        lines += [
            "",
            "## HEARTBEAT UNAVAILABLE",
            f"Reason: {hb.get('reason', 'UNKNOWN')}",
            f"Action: `{hb.get('instruction', '')}`",
            "",
            "All organs report: **UNKNOWN**",
            "Source truth: **UNKNOWN** — cannot determine clean / degraded / fallback.",
            "Memory capture: **UNKNOWN**",
            "Failure learning: **UNKNOWN**",
            "Promotion: **UNKNOWN**",
        ]
    else:
        sys_s = s.get("system_status", {})
        src = s.get("source_truth", {})
        vfu = s.get("vfu_status", {})
        a3 = s.get("a3_going_code", {})
        council = s.get("council_verdict", {})
        lr = s.get("learning_routes", {})
        contra = s.get("contradictions", {})
        pg = s.get("playbook_g_shadow", {})
        nsa = s.get("next_safe_action", {})

        # 1. System status
        stale_flag = "" if sys_s.get("stale_docs_archived") else "  ⚠ STALE ROOT DOCS PRESENT"
        lines += [
            "",
            "## 1. System Status",
            f"- Truth lock: **{sys_s.get('truth_lock', 'UNKNOWN')}**{stale_flag}",
            f"- docs/current/ spine: {sys_s.get('spine_count', 'UNKNOWN')} files",
            f"- Repo HEAD: `{sys_s.get('repo_head', 'UNKNOWN')}`",
        ]

        # 2. Source truth
        lines += [
            "",
            "## 2. Source Truth",
            f"- Status: **{src.get('status', 'UNKNOWN')}**",
            f"- {src.get('note', '')}",
        ]

        # 3. VFU status
        recovery = vfu.get("field_size_recovery_rate")
        recovery_str = f"{recovery*100:.1f}%" if recovery is not None else "UNKNOWN"
        vfu21 = vfu.get("vfu_21_gate", "UNKNOWN")
        vfu21_flag = "🔒 " if vfu21 == "CLOSED" else ""
        lines += [
            "",
            "## 3. VFU Status",
            f"- Latest: **{vfu.get('latest', 'UNKNOWN')}**  "
            f"Signed off: **{vfu.get('signed_off', False)}** ({vfu.get('signed_off_date', 'UNKNOWN')})",
            f"- Field size recovery: {vfu.get('field_size_missing_before')} → "
            f"{vfu.get('field_size_missing_after')} ({recovery_str})",
            f"- EW claim: `{vfu.get('ew_profitability_status', 'UNKNOWN')}`",
            f"- VFU-21: {vfu21_flag}**{vfu21}**",
        ]

        # 4. A-3
        lines += [
            "",
            "## 4. A-3 Going Code",
            f"- Status: **{a3.get('status', 'UNKNOWN')}**  Scale: `{a3.get('scale', 'UNKNOWN')}`",
            f"- Regression tests: {a3.get('regression_tests', 0)} passing",
        ]

        # 5. Council / sigma
        gate_reasons = council.get("gate_reasons", [])
        lines += [
            "",
            "## 5. Council Verdict",
            f"- Verdict: **{council.get('verdict', 'UNKNOWN')}**",
            f"- Learning gate: `{council.get('learning_gate', 'UNKNOWN')}`",
            f"- Promotion gate: `{council.get('promotion_gate', 'UNKNOWN')}`",
        ]
        for r in gate_reasons:
            lines.append(f"  - {r}")
        sigma_sr = council.get("sigma_sr")
        sr_str = f"{sigma_sr:.1%}" if sigma_sr is not None else "UNKNOWN"
        lines += [
            f"- Sigma ({council.get('sigma_date', 'UNKNOWN')}): "
            f"`{council.get('sigma_status', 'UNKNOWN')}` SR={sr_str}  "
            f"Identity failures: {council.get('identity_failures', 0)}",
        ]

        # 6. Learning routes
        promo = lr.get("promotion_learning", "UNKNOWN")
        blockers = lr.get("promotion_blockers", [])
        lines += [
            "",
            "## 6. Learning Routes",
            f"- Memory capture:   **{lr.get('memory_capture', 'UNKNOWN')}**",
            f"- Failure learning: **{lr.get('failure_learning', 'UNKNOWN')}**",
            f"- Promotion:        **{promo}**",
        ]
        for b in blockers:
            lines.append(f"  - {b}")

        # 7. Contradictions
        count = contra.get("count", 0)
        lines += [
            "",
            "## 7. Contradictions",
            f"- Count: **{count}**",
        ]
        for item in contra.get("items", []):
            sev = item.get("severity", "UNKNOWN")
            lines.append(f"- [{sev}] {item.get('id', '?')}: {item.get('description', '')}")

        # 8. Playbook G
        compliant = pg.get("compliant")
        compliant_str = "YES" if compliant is True else ("NO ⚠" if compliant is False else "UNKNOWN")
        lines += [
            "",
            "## 8. Playbook G Shadow",
            f"- Status: **{pg.get('status', 'UNKNOWN')}**",
            f"- Live state touched: `{pg.get('live_sentient_state_touched', 'UNKNOWN')}`  "
            f"Compliant: **{compliant_str}**",
        ]

        # 9. Next safe action
        lines += [
            "",
            "## 9. Next Safe Action",
            f"- **{nsa.get('id', 'UNKNOWN')}**: {nsa.get('name', 'UNKNOWN')}",
        ]
        if nsa.get("requires_operator_approval"):
            lines.append("  - Requires operator approval before proceeding.")
        if nsa.get("reason"):
            lines.append(f"  - {nsa['reason']}")

        # 10. Forbidden actions
        lines += ["", "## 10. Forbidden Actions"]
        for f in s.get("forbidden_actions", _FORBIDDEN_ACTIONS):
            lines.append(f"- {f}")

        # 11. Operator decisions
        operator_decisions = s.get("operator_decisions_needed", [])
        lines += ["", "## 11. Operator Decision Needed"]
        if operator_decisions:
            for d in operator_decisions:
                lines.append(f"- {d}")
        else:
            lines.append("- None at this time.")

    lines += [
        "",
        "---",
        "REPORT_ONLY — no scoring change, no Supabase write, no model promotion, no Telegram send.",
    ]
    return "\n".join(lines)


def _render_brief(hb: dict) -> str:
    ts = hb["generated_at"]
    head = hb.get("repo_head", "UNKNOWN")
    fc = hb.get("final_classifications", [])
    s = hb.get("sections", {})
    unavailable = hb.get("status") == "HEARTBEAT_UNAVAILABLE"

    lr = s.get("learning_routes", {})
    contra = s.get("contradictions", {})
    nsa = s.get("next_safe_action", {})

    lines = [
        "# VCP-02 — VÉLØ Heartbeat V1 — Operator Brief",
        f"**Generated:** {ts}  ",
        f"**Repo HEAD:** `{head}`",
        "",
        "---",
        "",
        "## Mission Outcome",
        f"- Status: **{'HEARTBEAT_UNAVAILABLE' if unavailable else 'COMPLETE'}**",
        f"- Living state source: `data/current/velo_living_state.json`",
        f"- Heartbeat reads only living state — no direct organ reads.",
        "",
        "## Learning Routes (summary)",
        f"- Memory capture: **{lr.get('memory_capture', 'UNKNOWN')}**",
        f"- Failure learning: **{lr.get('failure_learning', 'UNKNOWN')}**",
        f"- Promotion: **{lr.get('promotion_learning', 'UNKNOWN')}**",
        "",
        "## Contradictions",
        f"- Count: **{contra.get('count', 0)}**",
        "",
        "## Next Safe Action",
        f"- **{nsa.get('id', 'UNKNOWN')}**: {nsa.get('name', 'UNKNOWN')}",
        "",
        "## Final Classifications",
    ]
    for c in fc:
        lines.append(f"- {c}")
    lines += [
        "",
        "---",
        "STOP — operator review required before VCP-03 Ten-Day Burn-In begins.",
        "REPORT_ONLY — no scoring change, no Supabase write, no model promotion, no Telegram send.",
    ]
    return "\n".join(lines)


def main() -> None:
    print("── VCP-02: Building VÉLØ Heartbeat ──")

    state = _load_living_state()
    if state is None:
        hb = _build_unavailable_heartbeat(
            "data/current/velo_living_state.json missing or unreadable. "
            "Run build_velo_living_state.py first."
        )
        print("  WARN  Living state not found — heartbeat is UNAVAILABLE")
    else:
        hb = _build_heartbeat_from_state(state)

    _OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    _OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    _OUT_MD.write_text(_render_md(hb), encoding="utf-8")
    _OUT_JSON.write_text(json.dumps(hb, indent=2), encoding="utf-8")
    _OUT_BRIEF.write_text(_render_brief(hb), encoding="utf-8")

    print(f"  OK   {_OUT_MD.relative_to(_REPO_ROOT)}")
    print(f"  OK   {_OUT_JSON.relative_to(_REPO_ROOT)}")
    print(f"  OK   {_OUT_BRIEF.relative_to(_REPO_ROOT)}")

    if state is not None:
        s = hb.get("sections", {})
        lr = s.get("learning_routes", {})
        contra = s.get("contradictions", {})
        nsa = s.get("next_safe_action", {})
        print()
        print(f"  Truth lock:       {s.get('system_status', {}).get('truth_lock', 'UNKNOWN')}")
        print(f"  Source truth:     {s.get('source_truth', {}).get('status', 'UNKNOWN')}")
        print(f"  VFU-21 gate:      {s.get('vfu_status', {}).get('vfu_21_gate', 'UNKNOWN')}")
        print(f"  Council:          {s.get('council_verdict', {}).get('verdict', 'UNKNOWN')}")
        print(f"  Memory capture:   {lr.get('memory_capture', 'UNKNOWN')}")
        print(f"  Failure learning: {lr.get('failure_learning', 'UNKNOWN')}")
        print(f"  Promotion:        {lr.get('promotion_learning', 'UNKNOWN')}")
        print(f"  Contradictions:   {contra.get('count', 0)}")
        print(f"  Next action:      {nsa.get('id', 'UNKNOWN')}")

    print()
    print("── VCP-02 COMPLETE ──")
    print("STOP — operator review required before VCP-03 Ten-Day Burn-In.")


if __name__ == "__main__":
    main()
