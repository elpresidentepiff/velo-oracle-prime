"""
Regression test for scripts/ops/build_canonical_learning_events.py, hard-coding
the July 05 Little Lady Rock proof case (race 922118), sourced from Supabase
public.canonical_model_scorecards only.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "reports" / "canonical_learning_events_2026_07_05.csv"


def _rows():
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_csv_exists():
    assert CSV_PATH.exists(), (
        "Run: PYTHONPATH=. python scripts/ops/build_canonical_learning_events.py --date 2026-07-05 --dry-run"
    )


def test_race_922118_produces_events():
    rows = [r for r in _rows() if r["race_id"] == "922118"]
    assert rows, "race_id 922118 must produce learning events"


def _llr_row(model_name):
    rows = [r for r in _rows() if r["race_id"] == "922118" and r["horse"] == "Little Lady Rock" and r["model_name"] == model_name]
    assert rows, f"{model_name} event for Little Lady Rock must exist"
    return rows[0]


def test_lane_a_event():
    r = _llr_row("NEW_BUILD_LANE_A_MODEL")
    assert r["event_type"] == "VALUE_DISCOVERY_POLICY_BLOCKED"
    assert r["learning_class"] == "MODEL_HIT_POLICY_BLOCKED"
    assert r["sp_dec"] == "41.0"
    assert r["rank"] == "1"
    assert r["policy_decision"] == "NO_EDGE"
    assert r["stake_authorised"] == "False"
    assert r["promotion_eligible"] == "False"
    assert "value discovery" in r["lesson"].lower()
    assert "policy" in r["lesson"].lower()


def test_lane_b_event():
    r = _llr_row("NEW_BUILD_LANE_B_MODEL")
    assert r["event_type"] == "VALUE_DISCOVERY_POLICY_BLOCKED"
    assert r["rank"] == "1"
    assert r["policy_decision"] == "NO_EDGE"
    assert r["promotion_eligible"] == "False"


def test_no_event_labels_lane_a_or_b_as_near_miss():
    for model in ("NEW_BUILD_LANE_A_MODEL", "NEW_BUILD_LANE_B_MODEL"):
        r = _llr_row(model)
        lesson = r["lesson"].lower()
        assert "near-miss" not in lesson and "near miss" not in lesson
        assert r["rank"] == "1"


def test_passport_proxy_is_context_only():
    rows = [r for r in _rows() if r["race_id"] == "922118" and r["model_name"] == "PASSPORT_STRENGTH_SCORE_PROXY" and r["horse"] == "Little Lady Rock"]
    assert rows
    assert rows[0]["event_type"] == "PROXY_CONTEXT_ONLY"
    assert rows[0]["promotion_eligible"] == "False"


def test_promotion_block_reason_for_little_lady_rock():
    r = _llr_row("NEW_BUILD_LANE_A_MODEL")
    assert r["promotion_block_reason"] == "POLICY_NO_EDGE_AND_SINGLE_DAY_EVIDENCE"


def test_no_event_is_promotion_eligible_for_the_day():
    rows = [r for r in _rows() if r["run_date"] == "2026-07-05"]
    assert rows
    assert all(r["promotion_eligible"] == "False" for r in rows), "no 2026-07-05 event may be promotion_eligible"
