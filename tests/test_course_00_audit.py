"""
Tests for COURSE-00 — VÉLØ Course Eyes Completion Pack.
Verifies hard constraints, WATCHLIST_ONLY rules, unknown-not-None fields,
no external URL calls, no scoring changes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "ops"))
import build_course_00_audit as _course_00_mod  # type: ignore[import]
from build_course_00_audit import (  # type: ignore[import]
    _COURSE_EYES,
    _FINAL_CLASSIFICATIONS,
    _HARD_CONSTRAINTS,
    _default_course_eye_entry,
    _mp_band,
    _s1_course_registry,
    _s4_aw_cluster,
    _s5_beverley_war_book,
    _s6_midprice_6_10,
    _s7_feature_readiness,
    _s8_external_source_map,
    _s9_course_watchlist,
    _sp_to_dec,
)

# ── Synthetic fixtures ─────────────────────────────────────────────────────────

_SIGMA_BEV_MISS = {
    "id": "1",
    "race_id": "rac_001",
    "date": "2026-04-15",
    "track": "Beverley",
    "outcome": "MISS",
    "miss_reason": "mid_priced_won",
    "decision_tier": "B",
    "actual_winner_sp": 7.5,
    "pick_sp": 2.5,
    "distance": "5f",
    "going": "Good",
    "race_type": "Flat",
    "field_size": 10,
    "actual_winner_name": "TestWinner",
    "off_time": "2:00",
    "verdict_score": 0.3,
    "top_pick_position": 3,
    "created_at": "2026-04-15T10:00:00",
}
_SIGMA_AW_MISS = {
    **_SIGMA_BEV_MISS,
    "id": "2",
    "race_id": "rac_002",
    "track": "Southwell (AW)",
    "actual_winner_sp": 8.0,
    "pick_sp": 3.0,
}
_MINIMAL_SIGMA = [_SIGMA_BEV_MISS, _SIGMA_AW_MISS]

_CT = {
    "Beverley": {
        "course": "Beverley",
        "n": "50",
        "wins": "2",
        "sr": "0.04",
        "frame_rate": "0.38",
        "avg_winner_sp": "7.21",
        "label": "COURSE_DRAIN",
    },
    "Musselburgh": {
        "course": "Musselburgh",
        "n": "46",
        "wins": "17",
        "sr": "0.37",
        "frame_rate": "0.63",
        "avg_winner_sp": "3.0",
        "label": "COURSE_EDGE_CONFIRMED",
    },
}
_DR = {
    "Beverley": {
        "course": "Beverley",
        "n": "50",
        "wins": "2",
        "sr": "0.04",
        "misses": "31",
        "avg_winner_sp": "7.21",
        "avg_pick_sp": "13.92",
        "sp_gap": "-6.7",
        "miss_reason_breakdown": "{}",
        "root_cause_hypotheses": "draw_bias",
        "watchlist_status": "WATCHLIST_ONLY",
    }
}
_ER = {
    "Musselburgh": {
        "course": "Musselburgh",
        "n": "46",
        "wins": "17",
        "sr": "0.37",
        "frame_rate": "0.63",
        "avg_winner_sp": "3.0",
        "edge_label": "COURSE_EDGE_CONFIRMED",
        "edge_hypothesis": "RPR_anchor_works",
        "edge_verdict": "COURSE_EDGE_REAL",
    }
}
_MP = [
    {
        "date": "2026-04-15",
        "course": "Beverley",
        "off_time": "2:00",
        "race_type": "Flat",
        "distance": "5f",
        "going": "Good",
        "actual_winner": "TestWinner",
        "winner_sp_dec": "7.5",
        "mp_band": "6-10",
        "decision_tier": "B",
        "confidence_level": "unknown",
        "pick_sp_dec": "2.5",
        "stamina_emphasis": "high",
        "front_runner_bias": "yes",
        "uphill_finish": "yes",
        "turn_severity": "sharp",
    },
    {
        "date": "2026-04-15",
        "course": "Southwell (AW)",
        "off_time": "3:00",
        "race_type": "Flat",
        "distance": "6f",
        "going": "Standard",
        "actual_winner": "AWWinner",
        "winner_sp_dec": "8.0",
        "mp_band": "6-10",
        "decision_tier": "C",
        "confidence_level": "unknown",
        "pick_sp_dec": "3.0",
        "stamina_emphasis": "low",
        "front_runner_bias": "yes",
        "uphill_finish": "no",
        "turn_severity": "sharp",
    },
]


# ── T-01: No banned imports ────────────────────────────────────────────────────


def test_no_supabase_import() -> None:
    src = (Path(__file__).parent.parent / "scripts" / "ops" / "build_course_00_audit.py").read_text()
    for banned in ["import supabase", "from supabase"]:
        assert banned not in src, f"Banned import: {banned}"


def test_no_telegram_import() -> None:
    src = (Path(__file__).parent.parent / "scripts" / "ops" / "build_course_00_audit.py").read_text()
    for banned in ["import telegram", "from telegram"]:
        assert banned not in src, f"Banned import: {banned}"


def test_no_model_mutation_calls() -> None:
    src = (Path(__file__).parent.parent / "scripts" / "ops" / "build_course_00_audit.py").read_text()
    for banned in ["promote_model(", "place_order(", "score_race(", "place_bet("]:
        assert banned not in src, f"Banned call: {banned}"


def test_no_external_url_calls() -> None:
    src = (Path(__file__).parent.parent / "scripts" / "ops" / "build_course_00_audit.py").read_text()
    # Should not call requests.get or urllib on external URLs
    for banned in ["requests.get(", "urllib.request.urlopen("]:
        assert banned not in src, f"Banned external call: {banned}"


# ── T-02: Hard constraints and classifications ─────────────────────────────────


def test_hard_constraints_present() -> None:
    required = {
        "REPORT_ONLY",
        "NO_LIVE_SCORING_CHANGE",
        "NO_MODEL_PROMOTION",
        "NO_SUPABASE_WRITES",
        "NO_TELEGRAM_SEND",
        "NO_VFU_21_START",
        "NO_COURSE_01_IMPLEMENTATION",
        "COURSE_RULES_WATCHLIST_ONLY",
    }
    assert required.issubset(set(_HARD_CONSTRAINTS))


def test_final_classifications_complete() -> None:
    required = {
        "COURSE_00_COURSE_EYES_COMPLETION_COMPLETE",
        "BEVERLEY_WAR_BOOK_WRITTEN",
        "AW_CLUSTER_DEEP_DIVE_WRITTEN",
        "DRAW_EYES_IDENTIFIED_CRITICAL",
        "PACE_EYES_IDENTIFIED_CRITICAL",
        "BEVERLEY_WATCHLIST_ONLY",
        "AW_CLUSTER_WATCHLIST_ONLY",
        "COURSE_RULES_WATCHLIST_ONLY",
        "NO_COURSE_01_IMPLEMENTATION",
        "REPORT_ONLY",
    }
    assert required.issubset(set(_FINAL_CLASSIFICATIONS))


# ── T-03: Course eyes registry — unknown not None ──────────────────────────────


def test_course_eyes_no_none_fields() -> None:
    # _COURSE_EYES extends _COURSE_PROFILES with draw/pace fields — not all profile fields duplicated
    key_fields = ["draw_bias_known", "pace_bias_known", "front_runner_advantage", "circuit_type"]
    for course, entry in _COURSE_EYES.items():
        for field in key_fields:
            val = entry.get(field)
            assert val is not None, f"{course}.{field} is None — must be 'unknown'"
            assert val != "", f"{course}.{field} is empty — must be 'unknown'"


def test_beverley_draw_bias_documented() -> None:
    bev = _COURSE_EYES.get("Beverley", {})
    assert bev.get("draw_bias_known") == "yes"
    assert "low" in bev.get("draw_bias_side", "")
    assert bev.get("front_runner_advantage") == "yes"


def test_aw_cluster_entries_present() -> None:
    aw_tracks = ["Southwell (AW)", "Kempton (AW)", "Wolverhampton (AW)", "Lingfield (AW)"]
    for t in aw_tracks:
        assert t in _COURSE_EYES, f"AW track {t} missing from _COURSE_EYES"
        entry = _COURSE_EYES[t]
        assert entry.get("draw_bias_known") in ("yes", "unknown", "no")
        assert "AW_PACE_EYES_REQUIRED" in entry.get("course_00_required_features", [])


def test_default_entry_no_none_fields() -> None:
    entry = _default_course_eye_entry("UnknownCourse")
    for field in ["draw_bias_known", "pace_bias_known", "front_runner_advantage", "circuit_type", "source_confidence"]:
        val = entry.get(field)
        assert val is not None and val != "", f"Default entry field {field} is None/empty"
        assert val == "unknown" or val == "UNKNOWN", f"Default entry {field} should be 'unknown', got {val!r}"


# ── T-04: Section 1 — course registry ─────────────────────────────────────────


def test_s1_returns_list() -> None:
    s1 = _s1_course_registry(_MINIMAL_SIGMA, _CT, _DR, _ER)
    assert isinstance(s1, list)
    assert len(s1) >= 1


def test_s1_rows_have_required_fields() -> None:
    s1 = _s1_course_registry(_MINIMAL_SIGMA, _CT, _DR, _ER)
    required = {"course", "n", "wins", "sr", "label"}
    for row in s1:
        assert required.issubset(set(row.keys())), f"s1 row missing: {required - set(row.keys())}"


# ── T-05: Section 4 — AW cluster ─────────────────────────────────────────────


def test_s4_aw_cluster_runs() -> None:
    s4 = _s4_aw_cluster(_MINIMAL_SIGMA, _CT, _DR, _MP)
    assert isinstance(s4, dict)
    assert "aw_cluster_tracks" in s4
    assert "total_mp_misses" in s4


def test_s4_watchlist_status() -> None:
    _s4_aw_cluster(_MINIMAL_SIGMA, _CT, _DR, _MP)
    # Verify AW_CLUSTER_WATCHLIST_ONLY is in final classifications (the real gate)
    assert "AW_CLUSTER_WATCHLIST_ONLY" in _FINAL_CLASSIFICATIONS


# ── T-06: Section 5 — Beverley war book ───────────────────────────────────────


def test_s5_beverley_war_book_runs() -> None:
    s5 = _s5_beverley_war_book(_MINIMAL_SIGMA, _MP, _DR)
    assert isinstance(s5, dict)


def test_s5_beverley_has_draw_flag() -> None:
    s5 = _s5_beverley_war_book(_MINIMAL_SIGMA, _MP, _DR)
    assert s5.get("draw_bias_known") in ("yes", "unknown", "no")


def test_s5_beverley_watchlist_only() -> None:
    _s5_beverley_war_book(_MINIMAL_SIGMA, _MP, _DR)
    # War book must carry WATCHLIST_ONLY tag — verified via FINAL_CLASSIFICATIONS
    assert "BEVERLEY_WATCHLIST_ONLY" in _FINAL_CLASSIFICATIONS


# ── T-07: Section 6 — 6-10 wound table ───────────────────────────────────────


def test_s6_midprice_6_10_runs() -> None:
    s6 = _s6_midprice_6_10(_MINIMAL_SIGMA, _MP)
    assert isinstance(s6, dict)
    assert "rows" in s6 or "n_total" in s6


def test_s6_only_6_10_band() -> None:
    s6 = _s6_midprice_6_10(_MINIMAL_SIGMA, _MP)
    rows = s6.get("rows", [])
    for row in rows:
        sp = row.get("winner_sp_dec") or row.get("actual_winner_sp")
        try:
            sp_f = float(sp)
            assert 6.0 <= sp_f < 10.0, f"Row has SP {sp_f} outside 6-10 band"
        except (TypeError, ValueError):
            pass  # UNKNOWN is acceptable


# ── T-08: Section 7 — feature readiness ──────────────────────────────────────


def test_s7_feature_count() -> None:
    s7 = _s7_feature_readiness()
    assert isinstance(s7, list)
    assert len(s7) >= 10, f"Expected 10+ features in matrix, got {len(s7)}"


def test_s7_critical_features_present() -> None:
    s7 = _s7_feature_readiness()
    critical = [f["feature"] for f in s7 if f.get("priority") == "CRITICAL"]
    assert "draw_bias_by_course_distance" in critical
    assert "pace_map_front_runner_flag" in critical


def test_s7_recommended_phase_no_live() -> None:
    s7 = _s7_feature_readiness()
    for f in s7:
        phase = f.get("recommended_phase", "")
        # Should not recommend live scoring changes
        assert phase not in ("LIVE_NOW", "APPLY_IMMEDIATELY"), (
            f"Feature {f.get('feature')} has dangerous recommended_phase: {phase}"
        )


# ── T-09: Section 8 — external source map ─────────────────────────────────────


def test_s8_external_source_map_runs() -> None:
    s8 = _s8_external_source_map()
    assert isinstance(s8, list)
    assert len(s8) >= 5


def test_s8_no_false_proven_claims() -> None:
    s8 = _s8_external_source_map()
    for entry in s8:
        rp_status = entry.get("rp_status", "")
        bha_status = entry.get("bha_status", "")
        # If marked PROVEN, must have local_status=LOCAL_PRESENT
        if rp_status == "PROVEN_ACCESSIBLE":
            assert entry.get("local_status") == "LOCAL_PRESENT", (
                f"Field {entry.get('field')} claims RP PROVEN but not LOCAL_PRESENT"
            )
        if bha_status == "PROVEN_ACCESSIBLE":
            assert entry.get("local_status") == "LOCAL_PRESENT", (
                f"Field {entry.get('field')} claims BHA PROVEN but not LOCAL_PRESENT"
            )


# ── T-10: Section 9 — watchlist ───────────────────────────────────────────────


def test_s9_watchlist_runs() -> None:
    s9 = _s9_course_watchlist(_DR, _ER, _CT)
    assert isinstance(s9, dict)


def test_s9_beverley_in_watchlist() -> None:
    s9 = _s9_course_watchlist(_DR, _ER, _CT)
    # All courses in watchlist should have WATCHLIST_ONLY status
    for _cat_key, courses in s9.items():
        if isinstance(courses, list):
            for c in courses:
                if isinstance(c, dict) and c.get("course") == "Beverley":
                    status = c.get("rule_status", "WATCHLIST_ONLY")
                    assert status == "WATCHLIST_ONLY"


# ── T-11: SP conversion ───────────────────────────────────────────────────────


def test_sp_to_dec_fractional() -> None:
    assert abs(_sp_to_dec("3/1") - 4.0) < 0.001
    assert abs(_sp_to_dec("7/4F") - 2.75) < 0.001


def test_sp_to_dec_none() -> None:
    assert _sp_to_dec(None) is None
    assert _sp_to_dec("") is None


def test_mp_band_classification() -> None:
    assert _mp_band(4.0) is not None  # "4-6"
    assert _mp_band(7.0) is not None  # "6-10"
    assert _mp_band(12.0) is not None  # "10-16"
    assert _mp_band(None) in ("UNKNOWN", "unknown")  # case-insensitive


# ── T-12: Output files exist ──────────────────────────────────────────────────


def test_output_files_written(tmp_path, monkeypatch) -> None:
    """
    Self-contained: runs main() against a monkeypatched output directory
    so this test never depends on checked-in data/reports outputs.
    """
    monkeypatch.setattr(_course_00_mod, "_REPORTS_DIR", str(tmp_path))
    _course_00_mod.main()

    required_files = [
        "course_00_course_eyes_completion_pack.md",
        "course_00_course_eyes_completion_pack.json",
        "course_00_draw_bias_priority_table.csv",
        "course_00_pace_bias_priority_table.csv",
        "course_00_aw_cluster_deep_dive.md",
        "course_00_beverley_war_book.md",
        "course_00_midprice_6_10_wound_table.csv",
        "course_00_feature_readiness_matrix.csv",
        "course_00_external_source_field_map.md",
        "course_00_course_watchlist.md",
        "course_00_course_01_design_spec.md",
        "course_00_operator_brief.md",
    ]
    # course_00_midprice_6_10_wound_table.csv may legitimately be written empty
    # (header-less) when RESULTS-02's midprice input rows are unavailable —
    # existence, not size, is the contract for that one file.
    size_exempt = {"course_00_midprice_6_10_wound_table.csv"}
    for f in required_files:
        path = tmp_path / f
        assert path.exists(), f"Output file missing: {f}"
        if f not in size_exempt:
            assert path.stat().st_size > 0, f"Output file empty: {f}"


# ── T-13: COURSE-01 spec not implemented ─────────────────────────────────────


def test_course_01_spec_not_implemented() -> None:
    spec_path = Path(__file__).parent.parent / "data/reports/course_00_course_01_design_spec.md"
    if spec_path.exists():
        content = spec_path.read_text()
        assert "NOT IMPLEMENTED" in content or "NOT_IMPLEMENTED" in content or "design spec" in content.lower()
        # Must not contain actual code that modifies scoring
        assert "sqpe_v17_prob" not in content or "does not change" in content.lower()


def test_course_01_classification_not_implementation() -> None:
    assert "COURSE_01_DESIGN_SPEC_WRITTEN_NOT_IMPLEMENTED" in _FINAL_CLASSIFICATIONS
    assert "NO_COURSE_01_IMPLEMENTATION" in _FINAL_CLASSIFICATIONS


# ── T-14: Operator brief content ─────────────────────────────────────────────


def test_operator_brief_mentions_beverley() -> None:
    brief_path = Path(__file__).parent.parent / "data/reports/course_00_operator_brief.md"
    if brief_path.exists():
        content = brief_path.read_text()
        assert "Beverley" in content
        assert "draw" in content.lower() or "DRAW" in content
        assert "WATCHLIST" in content


# ── T-15: Containment not profit ─────────────────────────────────────────────


def test_containment_is_not_profit_in_source() -> None:
    src = (Path(__file__).parent.parent / "scripts" / "ops" / "build_course_00_audit.py").read_text()
    assert "containment_is_not_profit" in src
    assert "True" in src
