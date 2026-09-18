"""
Tests for scripts/ops/model_disagreement_audit.py.

The audit exists to stop a shadow lane reading as "nearly level with Main" when
it is mostly copying Main's picks, so the things worth pinning down are: the
equal race set, the exclusion of the AGREE cohort from the edge, the redundancy
and evidence floors, and the big-price robustness twin.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "ops" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mda = _load("model_disagreement_audit")

INC = "MAIN_VELO_PRIME"
CHAL = "CHALLENGER_SHADOW"


def _pick(rid, model, horse, win=False, sp=3.0, frame=None, date="2026-09-18"):
    return {"date": date, "race_id": str(rid), "model": model, "horse": horse,
            "win": win, "frame": win if frame is None else frame, "sp": sp}


def _pair_rows(n_agree, n_disagree, *, inc_wins=0, chal_wins=0, sp=3.0, date="2026-09-18"):
    """n_agree races where both pick the same horse, then n_disagree where they differ."""
    rows = []
    for i in range(n_agree):
        rows += [_pick(f"a{i}", INC, "Same", date=date), _pick(f"a{i}", CHAL, "Same", date=date)]
    for i in range(n_disagree):
        rows += [
            _pick(f"d{i}", INC, "IncHorse", win=i < inc_wins, sp=sp, date=date),
            _pick(f"d{i}", CHAL, "ChalHorse", win=i < chal_wins, sp=sp, date=date),
        ]
    return rows


def test_equal_race_set_excludes_races_only_one_lane_picked():
    rows = _pair_rows(2, 0)
    rows.append(_pick("solo", CHAL, "OnlyChallenger"))   # incumbent never priced it
    rows.append(_pick("solo2", INC, "OnlyIncumbent"))
    rep = mda.compare(rows, INC, CHAL)
    assert rep["n_equal"] == 2, "a race only one lane picked is not a comparison"


def test_agree_cohort_is_reported_but_never_feeds_the_edge():
    # 40 shared winners for both, then 40 disagreements the challenger wins outright.
    rows = _pair_rows(40, 40, inc_wins=0, chal_wins=20)
    for i in range(40):
        for r in rows:
            if r["race_id"] == f"a{i}":
                r["win"] = r["frame"] = True
    rep = mda.compare(rows, INC, CHAL)
    assert rep["agree_n"] == 40 and rep["agree_sr"] == 100.0
    # The edge is computed on the 40 disagreements alone: 50% vs 0%.
    assert rep["disagree_n"] == 40
    assert rep["chal"]["sr"] == 50.0 and rep["inc"]["sr"] == 0.0
    assert rep["sr_edge_pts"] == 50.0
    assert rep["chal_only_wins"] == 20 and rep["inc_only_wins"] == 0


def test_high_overlap_is_redundant_even_with_a_strong_disagree_record():
    # 95% agreement; on the few disagreements the challenger is perfect.
    rows = _pair_rows(190, 10, inc_wins=0, chal_wins=10)
    rep = mda.compare(rows, INC, CHAL)
    assert rep["overlap_pct"] >= 90.0
    assert rep["verdict"] == "REDUNDANT_WITH_INCUMBENT"


def test_thin_disagreement_evidence_is_not_an_edge():
    rows = _pair_rows(10, mda.MIN_DISAGREE_N - 1, inc_wins=0, chal_wins=10)
    assert mda.compare(rows, INC, CHAL)["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_edge_carried_only_by_bigprice_winners_is_flagged_not_promoted():
    # Challenger wins 4 of 40 disagreements, all at 25/1; incumbent wins 3 at 3.0.
    rows = _pair_rows(10, 40, inc_wins=3, chal_wins=4, sp=3.0)
    for r in rows:
        if r["model"] == CHAL and r["win"]:
            r["sp"] = 25.0
    rep = mda.compare(rows, INC, CHAL)
    assert rep["chal"]["roi"] > rep["inc"]["roi"], "raw ROI favours the challenger"
    # Strip the 25/1 winners and the challenger's book is the worse one.
    assert rep["chal"]["roi_ex_bigprice"] < rep["inc"]["roi_ex_bigprice"]
    assert rep["verdict"] == "EDGE_UNPROVEN_BIGPRICE_DEPENDENT"


def test_genuine_edge_survives_the_bigprice_strip():
    rows = _pair_rows(10, 40, inc_wins=4, chal_wins=12, sp=4.0)
    rep = mda.compare(rows, INC, CHAL)
    assert rep["sr_edge_pts"] > 0 and rep["roi_edge_ex_bigprice_pts"] > 0
    assert rep["verdict"] == "ADDING_EDGE"


def test_worse_on_its_own_picks_is_subtracting():
    rows = _pair_rows(10, 40, inc_wins=12, chal_wins=4, sp=4.0)
    assert mda.compare(rows, INC, CHAL)["verdict"] == "SUBTRACTING_VS_INCUMBENT"


def test_silent_lane_is_retired_not_ranked_on_old_form():
    rows = _pair_rows(10, 40, inc_wins=0, chal_wins=20, sp=4.0, date="2026-01-01")
    rows.append(_pick("recent", INC, "Fresh", date="2026-09-18"))  # corpus moves on
    rep = mda.compare(rows, INC, CHAL)
    assert rep["last_date"] == "2026-01-01"
    assert rep["verdict"] == "RETIRED_OR_RENAMED"


def test_winner_with_no_recorded_sp_returns_stake_and_cannot_invent_profit():
    picks = [_pick("r1", CHAL, "H", win=True, sp=None), _pick("r2", CHAL, "H2", win=False)]
    assert mda._pnl(picks) == -1.0


def test_unsettled_rows_never_enter_a_cohort(tmp_path, monkeypatch):
    path = tmp_path / "canonical_model_scorecard_2026_09_18.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["date", "race_id", "model_name", "rank",
                                           "horse", "sp_dec", "result_position", "win", "frame"])
        w.writeheader()
        w.writerow({"date": "2026-09-18", "race_id": "1", "model_name": INC, "rank": "1",
                    "horse": "A", "sp_dec": "3.0", "result_position": "1", "win": "True", "frame": "True"})
        w.writerow({"date": "2026-09-18", "race_id": "2", "model_name": INC, "rank": "1",
                    "horse": "B", "sp_dec": "3.0", "result_position": "", "win": "False", "frame": "False"})
        w.writerow({"date": "2026-09-18", "race_id": "1", "model_name": INC, "rank": "2",
                    "horse": "C", "sp_dec": "5.0", "result_position": "2", "win": "False", "frame": "True"})
    monkeypatch.setattr(mda, "SCORECARD_GLOB", str(tmp_path / "canonical_model_scorecard_*.csv"))
    rows = mda.load_top_picks()
    assert len(rows) == 1, "unsettled race and rank-2 row must both be excluded"
    assert rows[0]["race_id"] == "1"
