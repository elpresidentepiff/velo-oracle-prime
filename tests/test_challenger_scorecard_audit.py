"""Coverage audit tests: no scores are treated as probabilities."""
import json

from src.intelligence.challenger_scorecard_audit import audit_scorecard_export


def test_audit_reports_only_identical_runner_cohorts(tmp_path):
    rows = []
    for model, runners in (("A", ["1", "2"]), ("B", ["1", "2"]), ("C", ["1"])):
        for runner in runners:
            rows.append({"model_name": model, "race_id": "r1", "horse_id": runner,
                         "official_evaluation_eligible": True, "result_source_complete": True})
    rows.append({"model_name": "B", "race_id": "r2", "horse_id": "3",
                 "official_evaluation_eligible": False, "result_source_complete": True})
    file = tmp_path / "scorecards.json"
    file.write_text(json.dumps(rows))
    report = audit_scorecard_export(file)
    assert report["models"]["B"]["rejected_rows"] == 1
    pairs = {(x["model_a"], x["model_b"]): x for x in report["pair_coverage"]}
    assert pairs[("A", "B")]["identical_runner_cohort_races"] == 1
    assert pairs[("A", "C")]["identical_runner_cohort_races"] == 0
    assert report["performance_verified"] is False
    assert report["promotion"] == "NOT_AUTHORISED"
