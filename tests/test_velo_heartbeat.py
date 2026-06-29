"""
VCP-02 regression tests for VÉLØ Heartbeat V1.
All 12 acceptance criteria from the operator mission spec.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "ops"))
from build_velo_heartbeat import (  # type: ignore[import]
    _build_heartbeat_from_state,
    _build_unavailable_heartbeat,
    _render_md,
    _render_brief,
    _HEARTBEAT_VERSION,
    _LIVING_STATE,
    _FORBIDDEN_ACTIONS,
)

_REPO_ROOT = Path(__file__).parent.parent

_MINIMAL_LIVING_STATE: dict = {
    "metadata": {
        "state_version": "velo_living_state_v1",
        "generated_at": "2026-06-29T23:50:27+00:00",
        "repo_head": "ff86674",
        "truth_doc": "docs/current/ONE_TRUTH.md",
    },
    "truth_lock": {
        "status": "LOCKED",
        "docs_current_spine_count": 25,
        "stale_root_truth_docs_archived": True,
    },
    "vfu": {
        "latest": "VFU-20",
        "signed_off": True,
        "signed_off_date": "2026-06-29",
        "field_size_missing_before": 1989,
        "field_size_missing_after": 152,
        "field_size_recovery_rate": 0.9236,
        "ew_profitability_status": "PARTIAL_EW_SIGNAL_NOT_PROFIT_PROOF",
        "vfu_21_gate": "CLOSED",
        "vfu_21_gate_reason": "awaiting operator review",
    },
    "a3_going_code": {
        "status": "FIXED",
        "scale": "[-1, 2]",
        "regression_tests": 4,
    },
    "mission_control": {
        "source_truth": "LOCAL_JSON_FALLBACK",
        "council_verdict": "WATCH_ONLY",
        "learning_gate_status": "BLOCKED",
        "promotion_gate_status": "BLOCKED",
        "gate_reasons": ["GATE_COUNCIL_WATCH_ONLY", "GATE_PIPELINE_TRUTH_MANUAL_RECOVERY_ONLY"],
        "flatline_count": 0,
        "identity_failure_count": 0,
    },
    "sigma": {
        "artifact": "sigma_results_2026_06_29.json",
        "status": "PASS",
        "date": "2026-06-29",
        "sr": 0.3636,
        "identity_failures": 0,
    },
    "council": {
        "artifact": "council_packet_2026-06-29.json",
        "verdict": "UNKNOWN",
        "learning_open": None,
    },
    "playbook_g_shadow": {
        "artifact": "sentient_state_shadow.json",
        "status": "SHADOW_ONLY",
        "live_sentient_state_touched": False,
        "compliant": True,
    },
    "learning_routes": {
        "memory_capture": "OPEN",
        "failure_learning": "OPEN",
        "promotion_learning": "GATED",
        "promotion_blockers": [
            "source_truth=LOCAL_JSON_FALLBACK",
            "council_verdict=WATCH_ONLY",
        ],
    },
    "contradictions": {"count": 0, "items": []},
    "next_safe_action": {
        "id": "VCP-01-REVIEW",
        "name": "Operator review of velo_living_state_v1 before VCP-02 Heartbeat",
        "allowed": False,
        "requires_operator_approval": True,
    },
    "forbidden_actions": _FORBIDDEN_ACTIONS,
    "final_classifications": [],
}


@pytest.fixture(scope="module")
def heartbeat() -> dict:
    return _build_heartbeat_from_state(_MINIMAL_LIVING_STATE)


# ── T-01: Refuses to invent state when living state is missing ────────────────

def test_unavailable_when_living_state_missing() -> None:
    hb = _build_unavailable_heartbeat("test: living state absent")
    assert hb["status"] == "HEARTBEAT_UNAVAILABLE"
    assert "instruction" in hb
    assert "UNKNOWN" not in str(hb.get("reason", ""))  # reason is specific, not vague


def test_unavailable_heartbeat_has_forbidden_actions() -> None:
    hb = _build_unavailable_heartbeat("missing")
    fa = hb.get("sections", {}).get("forbidden_actions", [])
    assert "NO_MODEL_PROMOTION" in fa
    assert "NO_SUPABASE_WRITES" in fa


# ── T-02: Missing living state → UNKNOWN, not CLEAN ──────────────────────────

def test_unavailable_learning_routes_are_unknown() -> None:
    hb = _build_unavailable_heartbeat("missing")
    lr = hb.get("sections", {}).get("learning_routes", {})
    assert lr["memory_capture"] == "UNKNOWN"
    assert lr["failure_learning"] == "UNKNOWN"
    assert lr["promotion_learning"] == "UNKNOWN"
    assert "living_state_missing" in lr.get("promotion_blockers", [])


def test_unavailable_source_truth_is_unknown() -> None:
    hb = _build_unavailable_heartbeat("missing")
    src = hb.get("sections", {}).get("source_truth", {})
    assert src["status"] == "UNKNOWN"
    assert "CLEAN" not in src.get("note", "").upper()


# ── T-03: Heartbeat reads only living state ───────────────────────────────────

def test_builder_source_reads_only_living_state() -> None:
    src = (Path(__file__).parent.parent / "scripts" / "ops" / "build_velo_heartbeat.py").read_text()
    # These paths must NOT be opened directly by the heartbeat builder
    forbidden_direct_reads = [
        "mission_control/",
        "sigma_results/",
        "council_packets/",
        "sentient_state_shadow",
        "data/reports/vfu_20",
    ]
    for term in forbidden_direct_reads:
        assert term not in src, (
            f"Heartbeat builder must not read '{term}' directly — use living state only"
        )


def test_living_state_path_constant_correct() -> None:
    assert _LIVING_STATE == _REPO_ROOT / "data" / "current" / "velo_living_state.json"


# ── T-04: Memory capture OPEN rendered ───────────────────────────────────────

def test_memory_capture_open_in_heartbeat(heartbeat: dict) -> None:
    lr = heartbeat["sections"]["learning_routes"]
    assert lr["memory_capture"] == "OPEN"


def test_memory_capture_open_in_markdown(heartbeat: dict) -> None:
    md = _render_md(heartbeat)
    assert "Memory capture" in md
    assert "**OPEN**" in md


# ── T-05: Failure learning OPEN rendered ─────────────────────────────────────

def test_failure_learning_open_in_heartbeat(heartbeat: dict) -> None:
    lr = heartbeat["sections"]["learning_routes"]
    assert lr["failure_learning"] == "OPEN"


def test_failure_learning_open_in_markdown(heartbeat: dict) -> None:
    md = _render_md(heartbeat)
    assert "Failure learning" in md
    assert md.count("**OPEN**") >= 2  # at least memory + failure


# ── T-06: Promotion GATED rendered with reasons ───────────────────────────────

def test_promotion_gated_in_heartbeat(heartbeat: dict) -> None:
    lr = heartbeat["sections"]["learning_routes"]
    assert lr["promotion_learning"] == "GATED"
    assert len(lr["promotion_blockers"]) > 0


def test_promotion_gated_in_markdown(heartbeat: dict) -> None:
    md = _render_md(heartbeat)
    assert "**GATED**" in md
    assert "LOCAL_JSON_FALLBACK" in md or "WATCH_ONLY" in md


def test_no_blanket_learning_blocked_language(heartbeat: dict) -> None:
    md = _render_md(heartbeat)
    assert "learning blocked" not in md.lower(), \
        "Heartbeat must not use old 'learning blocked' phrase"


# ── T-07: Contradiction count rendered ───────────────────────────────────────

def test_contradictions_in_heartbeat(heartbeat: dict) -> None:
    contra = heartbeat["sections"]["contradictions"]
    assert "count" in contra
    assert "items" in contra


def test_contradictions_in_markdown(heartbeat: dict) -> None:
    md = _render_md(heartbeat)
    assert "Contradiction" in md
    assert "Count:" in md or "**0**" in md


def test_contradiction_items_rendered_when_present() -> None:
    state_with_contradiction = dict(_MINIMAL_LIVING_STATE)
    state_with_contradiction = {**_MINIMAL_LIVING_STATE, "contradictions": {
        "count": 1,
        "items": [{"id": "C-99", "severity": "WARN", "description": "test contradiction"}],
    }}
    hb = _build_heartbeat_from_state(state_with_contradiction)
    md = _render_md(hb)
    assert "C-99" in md
    assert "test contradiction" in md


# ── T-08: Forbidden actions rendered ─────────────────────────────────────────

def test_forbidden_actions_in_heartbeat(heartbeat: dict) -> None:
    fa = heartbeat["sections"]["forbidden_actions"]
    required = {
        "NO_LIVE_SCORING_CHANGE", "NO_MODEL_PROMOTION",
        "NO_SUPABASE_WRITES", "NO_TELEGRAM_SEND", "NO_VFU_21_START",
    }
    assert required.issubset(set(fa))


def test_forbidden_actions_in_markdown(heartbeat: dict) -> None:
    md = _render_md(heartbeat)
    assert "NO_LIVE_SCORING_CHANGE" in md
    assert "NO_MODEL_PROMOTION" in md
    assert "NO_SUPABASE_WRITES" in md


# ── T-09: VFU-21 remains CLOSED ──────────────────────────────────────────────

def test_vfu_21_closed_in_heartbeat(heartbeat: dict) -> None:
    assert heartbeat["sections"]["vfu_status"]["vfu_21_gate"] == "CLOSED"


def test_vfu_21_closed_in_markdown(heartbeat: dict) -> None:
    md = _render_md(heartbeat)
    assert "CLOSED" in md


# ── T-10: No banned side-effect imports ──────────────────────────────────────

def test_no_live_side_effect_patterns_in_builder() -> None:
    src = (Path(__file__).parent.parent / "scripts" / "ops" / "build_velo_heartbeat.py").read_text()
    import_banned = ["import supabase", "from supabase", "import telegram", "from telegram"]
    call_banned = ["score_race(", "place_order(", "place_bet(", "promote_model("]
    for term in import_banned + call_banned:
        assert term not in src, f"Banned pattern '{term}' in build_velo_heartbeat.py"


# ── T-11: Both MD and JSON outputs produced ───────────────────────────────────

def test_markdown_output_non_empty(heartbeat: dict) -> None:
    md = _render_md(heartbeat)
    assert len(md) > 200
    assert "# VÉLØ HEARTBEAT" in md


def test_json_output_serialisable(heartbeat: dict) -> None:
    serialised = json.dumps(heartbeat)
    assert len(serialised) > 100
    parsed = json.loads(serialised)
    assert parsed["heartbeat_version"] == _HEARTBEAT_VERSION


# ── T-12: Operator brief produced ────────────────────────────────────────────

def test_operator_brief_non_empty(heartbeat: dict) -> None:
    brief = _render_brief(heartbeat)
    assert "VCP-02" in brief
    assert "REPORT_ONLY" in brief
    assert "HEARTBEAT_READS_LIVING_STATE_ONLY" in brief


def test_final_classifications_complete(heartbeat: dict) -> None:
    required = {
        "VCP_02_HEARTBEAT_V1_COMPLETE",
        "HEARTBEAT_READS_LIVING_STATE_ONLY",
        "VELO_HEARTBEAT_MD_WRITTEN",
        "VELO_HEARTBEAT_JSON_WRITTEN",
        "MEMORY_CAPTURE_OPEN_RENDERED",
        "FAILURE_LEARNING_OPEN_RENDERED",
        "PROMOTION_LEARNING_GATED_RENDERED",
        "NO_VFU_21_START",
        "NO_LIVE_SCORING_CHANGE",
        "NO_MODEL_PROMOTION",
        "NO_SUPABASE_WRITES",
        "NO_TELEGRAM_SEND",
        "REPORT_ONLY",
    }
    found = set(heartbeat.get("final_classifications", []))
    missing = required - found
    assert not missing, f"Missing final classifications: {missing}"
