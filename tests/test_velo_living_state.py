"""
VCP-01 regression tests for velo_living_state_v1.
Tests the builder and the emitted JSON against all VCP-01 acceptance criteria.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "ops"))
from build_velo_living_state import (  # type: ignore[import]
    _build_state,
    _FORBIDDEN_ACTIONS,
    _STATE_VERSION,
    _TRUTH_DOC,
)

_REPO_ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def state() -> dict:
    return _build_state()


# ── T-01: Builds successfully ─────────────────────────────────────────────────

def test_state_has_required_top_level_keys(state: dict) -> None:
    required = {
        "metadata", "truth_lock", "vfu", "a3_going_code",
        "mission_control", "sigma", "council", "playbook_g_shadow",
        "learning_routes", "contradictions", "next_safe_action",
        "forbidden_actions", "final_classifications",
    }
    missing = required - set(state.keys())
    assert not missing, f"State missing keys: {missing}"


def test_metadata_fields_present(state: dict) -> None:
    m = state["metadata"]
    assert m["state_version"] == _STATE_VERSION
    assert m["truth_doc"] == _TRUTH_DOC
    assert m["repo_head"] not in ("", None)
    assert m["generated_at"] not in ("", None)


# ── T-02: Missing artifact → UNKNOWN, never CLEAN ─────────────────────────────

def test_unknown_not_clean_for_missing_artifact() -> None:
    """
    If an artifact is missing the value must be UNKNOWN, not CLEAN.
    We verify this by checking that no field that could default to CLEAN
    actually returns CLEAN when the file is absent.
    """
    # Monkey-patch _latest_sigma_path to return None and rebuild sigma state
    from build_velo_living_state import _build_sigma_state  # type: ignore[import]
    import build_velo_living_state as mod  # type: ignore[import]

    original = mod._latest_sigma_path
    mod._latest_sigma_path = lambda: None
    try:
        result = _build_sigma_state()
        assert result["status"] == "UNKNOWN", "Missing sigma must → UNKNOWN"
        assert result["artifact"] == "MISSING"
    finally:
        mod._latest_sigma_path = original


def test_missing_mission_control_gives_unknown() -> None:
    from build_velo_living_state import _build_mission_control_state  # type: ignore[import]
    import build_velo_living_state as mod  # type: ignore[import]

    original = mod._latest_mc_path
    mod._latest_mc_path = lambda: None
    try:
        result = _build_mission_control_state()
        assert result["source_truth"] == "UNKNOWN"
        assert result["council_verdict"] == "UNKNOWN"
        assert result["learning_gate_status"] == "UNKNOWN"
    finally:
        mod._latest_mc_path = original


# ── T-03: Archived root truth docs not treated as live ────────────────────────

def test_stale_root_truth_docs_not_present(state: dict) -> None:
    tl = state["truth_lock"]
    assert tl["stale_root_truth_docs_archived"] is True, (
        "CURRENT_RUNTIME_TRUTH.md or THE_NEW_TRUTH.md still present in root — VCP-00 not complete"
    )


def test_truth_doc_exists(state: dict) -> None:
    assert (_REPO_ROOT / _TRUTH_DOC).exists(), f"Truth doc {_TRUTH_DOC} must exist"


# ── T-04: VFU-20 sign-off in state ────────────────────────────────────────────

def test_vfu_20_signoff_present(state: dict) -> None:
    vfu = state["vfu"]
    assert vfu["latest"] == "VFU-20"
    assert vfu["signed_off"] is True
    assert vfu["field_size_missing_before"] == 1989
    assert vfu["field_size_missing_after"] == 152
    assert abs(vfu["field_size_recovery_rate"] - 0.9236) < 0.001
    assert vfu["ew_profitability_status"] == "PARTIAL_EW_SIGNAL_NOT_PROFIT_PROOF"
    assert vfu["ew_profitability_claim_authorised"] is False


# ── T-05: A-3 going_code fix in state ─────────────────────────────────────────

def test_a3_going_code_fix_in_state(state: dict) -> None:
    a3 = state["a3_going_code"]
    assert a3["status"] == "FIXED"
    assert a3["scale"] == "[-1, 2]"
    assert a3["regression_tests"] == 4


# ── T-06: VFU-21 gate remains CLOSED ─────────────────────────────────────────

def test_vfu_21_gate_closed(state: dict) -> None:
    assert state["vfu"]["vfu_21_gate"] == "CLOSED", "VFU-21 gate must remain CLOSED until operator approves"


# ── T-07: Contradictions counted, not hidden ─────────────────────────────────

def test_contradictions_block_present(state: dict) -> None:
    c = state["contradictions"]
    assert "count" in c
    assert "items" in c
    assert isinstance(c["items"], list)
    assert c["count"] == len(c["items"]), "contradiction count must match items list length"


def test_contradiction_detection_fires_on_stale_doc(tmp_path: Path, monkeypatch) -> None:
    from build_velo_living_state import _detect_contradictions  # type: ignore[import]
    import build_velo_living_state as mod  # type: ignore[import]

    # Simulate stale doc present → truth_lock reports not archived
    truth_lock_with_stale = {"stale_root_truth_docs_archived": False}
    mc = {"source_truth": "RP_MERGED_CLEAN", "learning_gate_status": "OPEN"}
    sigma = {"identity_failures": 0}
    contradictions = _detect_contradictions(truth_lock_with_stale, mc, sigma)
    ids = [c["id"] for c in contradictions]
    assert "C-02" in ids, "Stale root truth doc must register as C-02 contradiction"


# ── T-08: Forbidden actions always present ─────────────────────────────────────

def test_forbidden_actions_present(state: dict) -> None:
    fa = state["forbidden_actions"]
    for required in _FORBIDDEN_ACTIONS:
        assert required in fa, f"Forbidden action {required} must appear in state"


def test_forbidden_actions_immutable() -> None:
    required = {
        "NO_LIVE_SCORING_CHANGE",
        "NO_MODEL_PROMOTION",
        "NO_SUPABASE_WRITES",
        "NO_TELEGRAM_SEND",
        "NO_VFU_21_START",
    }
    assert required.issubset(set(_FORBIDDEN_ACTIONS))


# ── T-09: No side-effect strings in builder source ───────────────────────────

def test_no_live_side_effect_imports_in_builder() -> None:
    src = (Path(__file__).parent.parent / "scripts" / "ops" / "build_velo_living_state.py").read_text()
    # Check for import or call patterns — not docstring mentions
    import_banned = ["import supabase", "from supabase", "import telegram", "from telegram"]
    call_banned = ["score_race(", "place_order(", "place_bet(", "promote_model("]
    for term in import_banned + call_banned:
        assert term not in src, f"Banned pattern '{term}' found in build_velo_living_state.py"


# ── T-10: Learning routes use correct terminology ─────────────────────────────

def test_learning_routes_terminology(state: dict) -> None:
    lr = state["learning_routes"]
    assert lr["memory_capture"] == "OPEN"
    assert lr["failure_learning"] == "OPEN"
    assert lr["promotion_learning"] in ("OPEN", "GATED", "ELIGIBLE")
    assert "promotion_blockers" in lr
    assert isinstance(lr["promotion_blockers"], list)
    # Must not use the old blanket term
    state_str = json.dumps(state)
    assert "learning_blocked" not in state_str.lower(), \
        "State must not use old 'learning_blocked' language — use promotion_learning=GATED instead"


# ── T-11: Final classifications complete ─────────────────────────────────────

def test_final_classifications_complete(state: dict) -> None:
    required = {
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
        "NO_MODEL_PROMOTION",
        "NO_SUPABASE_WRITES",
        "NO_TELEGRAM_SEND",
        "REPORT_ONLY",
    }
    found = set(state["final_classifications"])
    missing = required - found
    assert not missing, f"Missing final classifications: {missing}"
