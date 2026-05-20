"""
Tests for Issue #78 Track A — VÉLØ Mid-Price Hunter shadow module.

Validates:
  - All three shadow rules fire on correct signal combinations
  - MIDPRICE_CLEAN fires when signals are strong (MDS≥0.30 at VP≥0.30)
  - live_scoring_changed and execution_allowed are always False
  - Ledger append creates file with correct headers
  - Thresholds match Phase 1 forensic audit findings (PR #79)
"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.velo.midprice_hunter import (  # noqa: E402
    _LEDGER_FIELDS,
    MIDPRICE_CLEAN,
    MIDPRICE_NO_EDGE,
    MIDPRICE_SPLIT_RACE,
    MIDPRICE_SUPPRESS_TOP,
    append_to_ledger,
    evaluate_race,
)


def _race(tier="B", vp=0.35, mds=0.10, imp=0.08, place_prob=0.65):
    return {
        "race_id": "rac_test001",
        "race_date": "2026-05-20",
        "course": "Ascot",
        "off_time": "14:30",
        "tier": tier,
        "top_pick": "Test Horse",
        "top_vp": vp,
        "top_mds": mds,
        "top_improvement": imp,
        "top_place_prob": place_prob,
    }


# ── Rule 1: MIDPRICE_SUPPRESS_TOP ─────────────────────────────────────────


def test_suppress_top_fires_at_vp30_mds_below_gate():
    v = evaluate_race(**_race(tier="B", vp=0.35, mds=0.10))
    assert v["shadow_action"] == MIDPRICE_SUPPRESS_TOP


def test_suppress_top_fires_exactly_at_threshold():
    v = evaluate_race(**_race(tier="B", vp=0.30, mds=0.29))
    assert v["shadow_action"] == MIDPRICE_SUPPRESS_TOP


def test_suppress_top_evidence_contains_gate_tags():
    v = evaluate_race(**_race(tier="B", vp=0.35, mds=0.10))
    evid = v["evidence"]
    assert "VP_ABOVE_GATE" in evid
    assert "MDS_BELOW_GATE" in evid


def test_suppress_top_near_zero_mds_adds_tag():
    v = evaluate_race(**_race(tier="B", vp=0.35, mds=0.03))
    assert "MDS_NEAR_ZERO" in v["evidence"]


# ── Rule 2: MIDPRICE_NO_EDGE ───────────────────────────────────────────────


def test_no_edge_fires_on_borderline_vp_no_signals():
    v = evaluate_race(**_race(tier="B", vp=0.25, mds=0.02, imp=0.05))
    assert v["shadow_action"] == MIDPRICE_NO_EDGE


def test_no_edge_does_not_fire_if_mds_above_low():
    # MDS 0.06 > _MDS_LOW=0.05 → should not fire NO_EDGE
    v = evaluate_race(**_race(tier="B", vp=0.25, mds=0.06, imp=0.05))
    assert v["shadow_action"] != MIDPRICE_NO_EDGE


def test_no_edge_does_not_fire_below_vp_min():
    v = evaluate_race(**_race(tier="B", vp=0.18, mds=0.02, imp=0.05))
    assert v["shadow_action"] != MIDPRICE_NO_EDGE


def test_no_edge_evidence_has_borderline_tag():
    v = evaluate_race(**_race(tier="B", vp=0.25, mds=0.02, imp=0.05))
    assert "VP_BORDERLINE" in v["evidence"]


# ── Rule 3: MIDPRICE_SPLIT_RACE ────────────────────────────────────────────


def test_split_race_fires_tier_a_high_vp_weak_both():
    v = evaluate_race(**_race(tier="A", vp=0.45, mds=0.10, imp=0.08))
    assert v["shadow_action"] == MIDPRICE_SPLIT_RACE


def test_split_race_does_not_fire_on_tier_b():
    v = evaluate_race(**_race(tier="B", vp=0.45, mds=0.10, imp=0.08))
    assert v["shadow_action"] != MIDPRICE_SPLIT_RACE


def test_split_race_does_not_fire_if_mds_above_split_max():
    v = evaluate_race(**_race(tier="A", vp=0.45, mds=0.25, imp=0.08))
    assert v["shadow_action"] != MIDPRICE_SPLIT_RACE


def test_split_race_evidence_has_tier_a_tag():
    v = evaluate_race(**_race(tier="A", vp=0.45, mds=0.10, imp=0.08))
    assert "TIER_A" in v["evidence"]


# ── Rule priority: SPLIT_RACE beats SUPPRESS_TOP ──────────────────────────


def test_split_race_takes_priority_over_suppress_top():
    # Tier A + VP≥0.40 + MDS<0.20 + imp<0.20 should fire SPLIT_RACE, not SUPPRESS_TOP
    v = evaluate_race(**_race(tier="A", vp=0.45, mds=0.10, imp=0.08))
    assert v["shadow_action"] == MIDPRICE_SPLIT_RACE


# ── MIDPRICE_CLEAN (strong signals, no suppression) ────────────────────────


def test_clean_fires_when_mds_above_gate_at_vp30():
    # VP≥0.30 + MDS≥0.30 = the good zone (SR=55%, MP-miss=18%)
    v = evaluate_race(**_race(tier="B", vp=0.35, mds=0.35, imp=0.25))
    assert v["shadow_action"] == MIDPRICE_CLEAN


def test_clean_fires_when_vp_below_all_gates():
    v = evaluate_race(**_race(tier="C", vp=0.15, mds=0.05, imp=0.05))
    assert v["shadow_action"] == MIDPRICE_CLEAN


# ── Safety invariants ──────────────────────────────────────────────────────


def test_live_scoring_changed_always_false():
    for tier, vp, mds, imp in [
        ("A", 0.45, 0.10, 0.08),
        ("B", 0.35, 0.10, 0.08),
        ("B", 0.25, 0.02, 0.05),
        ("B", 0.35, 0.35, 0.25),
    ]:
        v = evaluate_race(**_race(tier=tier, vp=vp, mds=mds, imp=imp))
        assert v["live_scoring_changed"] is False, f"live_scoring_changed True for {tier}/{vp}"


def test_execution_allowed_always_false():
    for tier, vp, mds, imp in [
        ("A", 0.45, 0.10, 0.08),
        ("B", 0.35, 0.10, 0.08),
        ("B", 0.25, 0.02, 0.05),
        ("B", 0.35, 0.35, 0.25),
    ]:
        v = evaluate_race(**_race(tier=tier, vp=vp, mds=mds, imp=imp))
        assert v["execution_allowed"] is False, f"execution_allowed True for {tier}/{vp}"


def test_evaluate_returns_all_required_fields():
    v = evaluate_race(**_race())
    required = {
        "race_id",
        "race_date",
        "course",
        "off_time",
        "tier",
        "top_pick",
        "top_vp",
        "top_mds",
        "top_improvement",
        "top_place_prob",
        "shadow_action",
        "evidence",
        "live_scoring_changed",
        "execution_allowed",
    }
    for field in required:
        assert field in v, f"Missing field: {field}"


# ── Ledger append ──────────────────────────────────────────────────────────


def test_ledger_creates_file_with_headers(tmp_path):
    ledger = tmp_path / "test_ledger.csv"
    v = evaluate_race(**_race())
    append_to_ledger(v, ledger_path=ledger)
    assert ledger.exists()
    with ledger.open() as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    assert len(rows) == 1
    for field in _LEDGER_FIELDS:
        assert field in rows[0], f"Ledger missing field: {field}"


def test_ledger_appends_multiple_rows(tmp_path):
    ledger = tmp_path / "test_ledger.csv"
    for _ in range(3):
        v = evaluate_race(**_race())
        append_to_ledger(v, ledger_path=ledger)
    with ledger.open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 3


def test_ledger_no_header_duplication_on_append(tmp_path):
    ledger = tmp_path / "test_ledger.csv"
    v = evaluate_race(**_race())
    append_to_ledger(v, ledger_path=ledger)
    append_to_ledger(v, ledger_path=ledger)
    lines = ledger.read_text().splitlines()
    header_lines = [line for line in lines if line.startswith("created_at")]
    assert len(header_lines) == 1, "Duplicate headers written"


def test_ledger_shadow_action_written_correctly(tmp_path):
    ledger = tmp_path / "test_ledger.csv"
    v = evaluate_race(**_race(tier="B", vp=0.35, mds=0.10))
    append_to_ledger(v, ledger_path=ledger)
    with ledger.open() as fh:
        row = list(csv.DictReader(fh))[0]
    assert row["shadow_action"] == MIDPRICE_SUPPRESS_TOP
    assert row["live_scoring_changed"] == "False"
    assert row["execution_allowed"] == "False"


# ── None handling ──────────────────────────────────────────────────────────


def test_none_sidecar_scores_do_not_crash():
    v = evaluate_race(
        race_id="rac_x",
        race_date="2026-05-20",
        course="Flat",
        off_time="14:00",
        tier="B",
        top_pick="Unknown",
        top_vp=None,
        top_mds=None,
        top_improvement=None,
        top_place_prob=None,
    )
    assert v["shadow_action"] in (MIDPRICE_CLEAN, MIDPRICE_NO_EDGE, MIDPRICE_SUPPRESS_TOP, MIDPRICE_SPLIT_RACE)
    assert v["live_scoring_changed"] is False
