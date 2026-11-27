from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_rpdc_tag_cumulative_scorecard",
    ROOT / "scripts" / "ops" / "build_rpdc_tag_cumulative_scorecard.py",
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _daily(tag: str, *, treatment_n: int, treatment_wins: int, treatment_top3: int, control_n: int, control_wins: int, control_top3: int):
    return {
        "status": "OK",
        "tag_scorecards": [{
            "tag": tag,
            "treatment": {"n": treatment_n, "wins": treatment_wins, "top_3": treatment_top3, "sp_decimal_coverage": treatment_n},
            "same_race_control": {"n": control_n, "wins": control_wins, "top_3": control_top3},
        }],
    }


def test_cumulative_uses_sum_of_runner_counts_not_average_of_daily_percentages():
    report = module.aggregate({
        "2026-11-25": _daily("HANDICAP_RELEASE", treatment_n=1, treatment_wins=1, treatment_top3=1, control_n=9, control_wins=1, control_top3=4),
        "2026-11-26": _daily("HANDICAP_RELEASE", treatment_n=9, treatment_wins=0, treatment_top3=3, control_n=1, control_wins=1, control_top3=1),
    }, "2026-11-26")

    card = report["tag_scorecards"][0]
    assert report["days_with_usable_evidence"] == 2
    assert card["treatment"]["n"] == 10
    assert card["treatment"]["win_rate_pct"] == 10.0
    assert card["same_race_control"]["win_rate_pct"] == 20.0
    assert card["delta_win_rate_pp"] == -10.0


def test_cumulative_excludes_unsettled_or_future_daily_reports_without_retagging():
    report = module.aggregate({
        "2026-11-25": _daily("HANDICAP_RELEASE", treatment_n=2, treatment_wins=1, treatment_top3=2, control_n=6, control_wins=1, control_top3=3),
        "2026-11-26": {"status": "NO_SETTLED_TAG_EVIDENCE", "tag_scorecards": []},
        "2026-11-27": _daily("HANDICAP_RELEASE", treatment_n=10, treatment_wins=10, treatment_top3=10, control_n=10, control_wins=10, control_top3=10),
    }, "2026-11-26")

    assert report["included_report_dates"] == ["2026-11-25"]
    assert report["excluded_report_dates"] == [{"date": "2026-11-26", "reason": "NO_SETTLED_TAG_EVIDENCE"}]
    assert report["tag_scorecards"][0]["treatment"]["n"] == 2
    assert report["guardrails"]["retrospective_retagging"] == "DISALLOWED"


def test_eod_and_artifact_persistence_are_wired_for_cumulative_report():
    eod_source = (ROOT / "scripts" / "ops" / "run_full_raceday_eod.py").read_text(encoding="utf-8")
    persistence_source = (ROOT / "scripts" / "ops" / "persist_daily_artifacts.py").read_text(encoding="utf-8")

    assert "Step 13C: RPDC tag cumulative matched-control shadow" in eod_source
    assert "build_rpdc_tag_cumulative_scorecard.py" in eod_source
    assert '"rpdc_tag_matched_control_cumulative"' in persistence_source
