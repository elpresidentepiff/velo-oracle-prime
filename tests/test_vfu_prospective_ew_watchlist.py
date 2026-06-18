#!/usr/bin/env python3
"""
Tests for VFU-23: Prospective VP>=0.40 Each-Way Watchlist.

Covers the 15 required governance tests from the operator brief.
Run with: python3 tests/test_vfu_prospective_ew_watchlist.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_prospective_ew_watchlist import (
    POST_RACE_LABELS,
    VP_THRESHOLD,
    PAPER_ONLY,
    _assign_band,
    _check_contamination,
    build_watchlist,
    write_outputs,
)
import scripts.ops.vfu_prospective_ew_watchlist as _mod


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _verdict(vp: float = 0.45, extra_top: dict | None = None,
             extra_root: dict | None = None) -> dict:
    v = {
        "race_id":   "rac_test_001",
        "course":    "Ascot",
        "off_time":  "14:30",
        "race_name": "Test Race",
        "scored":    8,
        "tier":      "B",
        "top": {
            "horse":            "Test Horse",
            "horse_id":         123456,
            "velo_prime_prob":  vp,
            "tie_gate_ew_flag": False,
            "place_prob":       0.30,
        },
        "signal_stack": {"assigned_product": "PASS"},
    }
    if extra_top:
        v["top"].update(extra_top)
    if extra_root:
        v.update(extra_root)
    return v


def _run(verdicts: list, date: str = "2026-06-17") -> tuple[list, list, dict]:
    """Build watchlist from in-memory verdicts list."""
    p = pathlib.Path(tempfile.mktemp(suffix=".json"))
    p.write_text(json.dumps(verdicts), encoding="utf-8")
    return build_watchlist(date, p, verdicts, {})


def _run_and_write(verdicts: list, date: str = "2026-06-17") -> tuple[list, list, dict, pathlib.Path]:
    """Build + write to a temp directory. Returns (candidates, rejected, stats, tmp_dir)."""
    p = pathlib.Path(tempfile.mktemp(suffix=".json"))
    p.write_text(json.dumps(verdicts), encoding="utf-8")
    candidates, rejected, stats = build_watchlist(date, p, verdicts, {})
    tmp = pathlib.Path(tempfile.mkdtemp())
    orig = _mod.REPORTS
    _mod.REPORTS = tmp
    try:
        write_outputs(date, candidates, rejected, stats, p, dry_run=False)
    finally:
        _mod.REPORTS = orig
    return candidates, rejected, stats, tmp


# ── Tests 01–15 (required) ────────────────────────────────────────────────────

def test_01_watchlist_uses_only_prerace_fields():
    """All entries must not contain post-race field values."""
    candidates, _, _ = _run([_verdict(0.50)])
    assert len(candidates) == 1
    serialised = json.dumps(candidates[0])
    for label in POST_RACE_LABELS:
        assert label not in serialised, f"Post-race label '{label}' leaked into entry"


def test_02_vp_threshold_required():
    """Candidates below VP=0.40 must not enter the watchlist."""
    low  = _verdict(0.39)
    high = _verdict(0.45)
    candidates, _, stats = _run([low, high])
    assert stats["candidates_generated"] == 1
    assert stats["below_threshold"] == 1
    assert candidates[0]["VP"] == 0.45


def test_03_win_lane_confirmed_rejected():
    """WIN_LANE_CONFIRMED anywhere in a verdict triggers rejection."""
    v = _verdict(0.55, extra_root={"signal_stack": {"dual_lane_label": "WIN_LANE_CONFIRMED"}})
    candidates, rejected, _ = _run([v])
    assert len(candidates) == 0
    assert len(rejected) == 1
    assert "WIN_LANE_CONFIRMED" in rejected[0]["post_race_labels_found"]


def test_04_place_signal_win_outcome_rejected():
    """PLACE_SIGNAL_WIN_OUTCOME triggers rejection."""
    v = _verdict(0.55, extra_root={"signal_stack": {"dual_lane_label": "PLACE_SIGNAL_WIN_OUTCOME"}})
    candidates, rejected, _ = _run([v])
    assert len(candidates) == 0
    assert len(rejected) == 1
    assert "PLACE_SIGNAL_WIN_OUTCOME" in rejected[0]["post_race_labels_found"]


def test_05_all_post_race_labels_individually_rejected():
    """All six post-race labels must each be individually rejected."""
    for label in POST_RACE_LABELS:
        v = _verdict(0.55, extra_root={"signal_stack": {"post_race_marker": label}})
        candidates, rejected, _ = _run([v])
        assert len(candidates) == 0, f"Label '{label}' was not rejected"
        assert len(rejected) == 1, f"Label '{label}' missing from rejected list"
        assert label in rejected[0]["post_race_labels_found"], \
            f"Label '{label}' not recorded in post_race_labels_found"


def test_06_all_entries_blocked_from_live_use():
    """Every candidate must have blocked_from_live_use=True."""
    candidates, _, _ = _run([_verdict(0.50), _verdict(0.65)])
    assert len(candidates) == 2
    for c in candidates:
        assert c["blocked_from_live_use"] is True


def test_07_all_entries_paper_only():
    """Every candidate must have paper_only=True. Module constant must also be True."""
    assert PAPER_ONLY is True
    candidates, _, _ = _run([_verdict(0.50)])
    assert len(candidates) == 1
    assert candidates[0]["paper_only"] is True


def test_08_all_entries_human_review_required():
    """Every candidate must have human_review_required=True."""
    candidates, _, _ = _run([_verdict(0.50)])
    assert candidates[0]["human_review_required"] is True


def test_09_audit_trail_generated():
    """write_outputs must append a row to the audit trail JSONL."""
    _, _, _, tmp = _run_and_write([_verdict(0.50)])
    audit = tmp / "vfu_23_watchlist_audit_trail.jsonl"
    assert audit.exists(), "Audit trail file not created"
    rows = [json.loads(ln) for ln in audit.read_text().splitlines() if ln.strip()]
    assert len(rows) >= 1
    row = rows[-1]
    assert row["operator_mode"] == "PAPER_ONLY"
    assert "contamination_checks_performed" in row
    assert set(row["contamination_checks_performed"]) == POST_RACE_LABELS


def test_10_rejected_contaminated_report_generated():
    """Contaminated verdicts must appear in the rejected candidates report."""
    clean = _verdict(0.50)
    dirty = _verdict(0.55, extra_root={"signal_stack": {"lbl": "WIN_LANE_CONFIRMED"}})
    _, _, _, tmp = _run_and_write([clean, dirty])
    rej_path = tmp / "vfu_23_rejected_contaminated_candidates.json"
    assert rej_path.exists(), "Rejected candidates file not created"
    data = json.loads(rej_path.read_text())
    assert len(data) == 1
    assert data[0]["rejection_reason"] == "POST_RACE_LABEL_FOUND"


def test_11_settlement_template_created_not_settled():
    """Settlement template must exist with all entries PENDING and no results filled."""
    candidates, _, _, tmp = _run_and_write([_verdict(0.50)])
    settle = tmp / "vfu_23_settlement_template.json"
    assert settle.exists(), "Settlement template not created"
    data = json.loads(settle.read_text())
    assert data["settlement_status"] == "PENDING"
    assert data["paper_only"] is True
    assert len(data["entries"]) == len(candidates)
    for entry in data["entries"]:
        assert entry["settlement_status"] == "PENDING"
        assert entry["finish_position"] is None
        assert entry["win_return"] is None
        assert entry["EW_return"] is None
        assert entry["outcome"] is None


def test_12_no_supabase_in_module():
    """VFU-23 module must not import or call Supabase."""
    src = pathlib.Path(_mod.__file__).read_text(encoding="utf-8")
    assert "create_client" not in src, "Supabase create_client found"
    assert "from supabase" not in src, "Supabase import found"
    assert "import supabase" not in src, "Supabase import found"


def test_13_no_telegram_in_module():
    """VFU-23 module must not contain Telegram send logic."""
    src = pathlib.Path(_mod.__file__).read_text(encoding="utf-8")
    assert "bot.send" not in src, "Telegram bot.send found"
    assert "send_message" not in src.lower().replace("# ", ""), "Telegram send_message found"
    assert "telegram.Bot" not in src, "Telegram Bot import found"
    assert "sendMessage" not in src, "Telegram sendMessage found"


def test_14_no_live_scoring_change():
    """VFU-23 module must not invoke the live scoring pipeline."""
    src = pathlib.Path(_mod.__file__).read_text(encoding="utf-8")
    assert "run_prime_today" not in src, "run_prime_today invoked"
    assert "SQPEEngine" not in src, "SQPEEngine referenced"
    assert "VeloPrimeEnsemble" not in src, "VeloPrimeEnsemble referenced"


def test_15_vp_threshold_is_040():
    """VP threshold must be exactly 0.40 as specified."""
    assert VP_THRESHOLD == 0.40, f"Expected 0.40, got {VP_THRESHOLD}"


# ── Additional correctness tests ──────────────────────────────────────────────

def test_16_band_assignment():
    """Band assignment must follow the spec thresholds."""
    assert _assign_band(0.39, False) == "BELOW_THRESHOLD"
    assert _assign_band(0.40, False) == "PRIMARY_EW_WATCH"
    assert _assign_band(0.59, False) == "PRIMARY_EW_WATCH"
    assert _assign_band(0.40, True)  == "EW_REVIEW_WATCH"
    assert _assign_band(0.59, True)  == "EW_REVIEW_WATCH"
    assert _assign_band(0.60, False) == "HIGH_VP_WATCH"
    assert _assign_band(0.85, True)  == "HIGH_VP_WATCH"  # HIGH_VP trumps EW flag


def test_17_contamination_scan_nested():
    """Contamination scanner must find labels nested deep in the verdict."""
    obj = {"a": {"b": {"c": ["WIN_LANE_CONFIRMED", "safe_value"]}}}
    found = _check_contamination(obj)
    assert "WIN_LANE_CONFIRMED" in found


def test_18_contamination_scan_clean():
    """Clean verdict must return empty contamination list."""
    v = _verdict(0.50)
    assert _check_contamination(v) == []


def test_19_watchlist_json_contains_classifications():
    """Watchlist JSON must include all required classification strings."""
    required = [
        "VFU_23_PROSPECTIVE_EW_WATCHLIST_COMPLETE",
        "PAPER_ONLY_MODE_CONFIRMED",
        "VP_040_EW_WATCHLIST_CREATED",
        "POST_RACE_LABELS_REJECTED",
        "NO_STAKING_EXECUTION",
        "NO_TELEGRAM_BETTING_OUTPUT",
        "NO_SUPABASE_WRITES",
        "NO_LIVE_SCORING_CHANGE",
        "NO_MODEL_PROMOTION",
        "NO_VP_THRESHOLD_CHANGE",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_RACING_API_RESTORATION",
    ]
    p = pathlib.Path(tempfile.mktemp(suffix=".json"))
    p.write_text(json.dumps([_verdict(0.50)]), encoding="utf-8")
    candidates, rejected, stats = build_watchlist("2026-06-17", p, [_verdict(0.50)], {})
    tmp = pathlib.Path(tempfile.mkdtemp())
    orig = _mod.REPORTS
    _mod.REPORTS = tmp
    try:
        write_outputs("2026-06-17", candidates, rejected, stats, p, dry_run=False)
    finally:
        _mod.REPORTS = orig
    wl = json.loads((tmp / "vfu_23_prospective_ew_watchlist_latest.json").read_text())
    for cls in required:
        assert cls in wl["classifications"], f"Missing classification: {cls}"


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = sorted(
        [(k, v) for k, v in globals().items() if k.startswith("test_")],
        key=lambda x: x[0],
    )
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {name}: {exc}")
            failed += 1
    print(f"\n{passed + failed} tests  |  {passed} passed  |  {failed} failed")
    sys.exit(1 if failed else 0)
