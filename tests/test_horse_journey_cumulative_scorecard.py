from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("horse_journey_cumulative", ROOT / "scripts" / "ops" / "build_horse_journey_cumulative_scorecard.py")
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(module)

def _daily(n, wins, top3, cn, cw, ct):
    return {"status": "OK", "tag_scorecards": [{"tag": "JOURNEY_HANDICAP_RELEASE_PATTERN", "treatment": {"n": n, "wins": wins, "top_3": top3}, "same_race_control": {"n": cn, "wins": cw, "top_3": ct}}]}

def test_journey_cumulative_sums_runner_counts_and_excludes_unsettled_days():
    report = module.aggregate({"2026-11-25": _daily(1, 1, 1, 9, 1, 4), "2026-11-26": _daily(9, 0, 3, 1, 1, 1), "2026-11-27": {"status": "NO_SETTLED_JOURNEY_EVIDENCE"}}, "2026-11-27")
    card = report["tag_scorecards"][0]
    assert card["treatment"]["n"] == 10
    assert card["treatment"]["win_rate_pct"] == 10.0
    assert card["same_race_control"]["win_rate_pct"] == 20.0
    assert report["excluded_report_dates"] == [{"date": "2026-11-27", "reason": "NO_SETTLED_JOURNEY_EVIDENCE"}]
    assert report["guardrails"]["retrospective_retagging"] == "DISALLOWED"

def test_journey_cumulative_is_wired_to_eod_and_persistence():
    eod = (ROOT / "scripts" / "ops" / "run_full_raceday_eod.py").read_text(encoding="utf-8")
    persistence = (ROOT / "scripts" / "ops" / "persist_daily_artifacts.py").read_text(encoding="utf-8")
    assert "Step 13E: Horse Journey cumulative matched-control shadow" in eod
    assert "horse_journey_matched_control_cumulative" in persistence
