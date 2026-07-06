"""
Regression test hard-coding the July 05 Little Lady Rock proof case
(race_id 922118), per MODEL-TRUTH-RESET-01-CANONICAL-SCORECARD-CONTRACT.

Guards against ever again reporting this pick as "ranked 2nd / near-miss"
for New Build's actual model output, and guards against ever reporting
a passport_strength_score row as a calibrated model prediction.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "reports" / "canonical_model_scorecard_2026_07_05.csv"


def _rows():
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _race_rows(rows, race_id="922118"):
    return [r for r in rows if r["race_id"] == race_id]


def test_scorecard_file_exists():
    assert CSV_PATH.exists(), (
        "Run: PYTHONPATH=. python scripts/ops/build_canonical_model_scorecard.py --date 2026-07-05"
    )


def test_race_922118_exists():
    rows = _race_rows(_rows())
    assert rows, "race_id 922118 must be present in the canonical scorecard"


def test_little_lady_rock_exists_with_sp_41():
    rows = _race_rows(_rows())
    llr_rows = [r for r in rows if r["horse"] == "Little Lady Rock"]
    assert llr_rows, "Little Lady Rock must appear at least once in race 922118"
    sps = {r["sp_dec"] for r in llr_rows if r["sp_dec"]}
    assert "41.0" in sps, f"Expected SP 41.0 for Little Lady Rock, found {sps}"


def test_new_build_lane_a_rank_is_1_for_little_lady_rock():
    rows = _race_rows(_rows())
    lane_a = [r for r in rows if r["model_name"] == "NEW_BUILD_LANE_A_MODEL" and r["horse"] == "Little Lady Rock"]
    assert lane_a, "NEW_BUILD_LANE_A_MODEL row for Little Lady Rock must exist"
    assert lane_a[0]["rank"] == "1", f"Expected Lane A rank 1, got {lane_a[0]['rank']}"
    assert lane_a[0]["win"] == "True"


def test_new_build_lane_b_rank_is_1_for_little_lady_rock():
    rows = _race_rows(_rows())
    lane_b = [r for r in rows if r["model_name"] == "NEW_BUILD_LANE_B_MODEL" and r["horse"] == "Little Lady Rock"]
    assert lane_b, "NEW_BUILD_LANE_B_MODEL row for Little Lady Rock must exist"
    assert lane_b[0]["rank"] == "1", f"Expected Lane B rank 1, got {lane_b[0]['rank']}"


def test_policy_decision_is_no_edge_and_stake_not_authorised():
    rows = _race_rows(_rows())
    lane_a = [r for r in rows if r["model_name"] == "NEW_BUILD_LANE_A_MODEL" and r["horse"] == "Little Lady Rock"]
    assert lane_a[0]["policy_decision"] == "NO_EDGE", f"Expected NO_EDGE, got {lane_a[0]['policy_decision']}"
    assert lane_a[0]["stake_authorised"] == "False"
    assert lane_a[0]["learning_class"] == "MODEL_HIT_POLICY_BLOCKED"


def test_main_velo_pick_is_way_maker():
    rows = _race_rows(_rows())
    main_velo = [r for r in rows if r["model_name"] == "MAIN_VELO_PRIME"]
    assert main_velo, "MAIN_VELO_PRIME row must exist for race 922118"
    assert main_velo[0]["horse"] == "Way Maker"
    assert main_velo[0]["win"] == "False"


def test_no_row_labels_lane_a_or_b_as_near_miss():
    rows = _race_rows(_rows())
    for r in rows:
        if r["model_name"] in ("NEW_BUILD_LANE_A_MODEL", "NEW_BUILD_LANE_B_MODEL") and r["horse"] == "Little Lady Rock":
            note = (r.get("notes") or "").lower()
            learning = (r.get("learning_class") or "").lower()
            assert "near-miss" not in note and "near miss" not in note
            assert "near-miss" not in learning and "near miss" not in learning
            assert r["rank"] == "1", "Lane A/B model rank for the actual winner must be 1, not 2"


def test_passport_strength_score_row_is_labelled_proxy_not_model():
    rows = _race_rows(_rows())
    proxy_rows = [r for r in rows if r["model_name"] == "PASSPORT_STRENGTH_SCORE_PROXY"]
    assert proxy_rows, "A passport_strength_score proxy row must exist for audit-trail purposes"
    for r in proxy_rows:
        assert r["learning_class"] == "PROXY_NOT_A_MODEL_CLAIM"
        assert "not" in (r.get("policy_decision") or "").lower()
