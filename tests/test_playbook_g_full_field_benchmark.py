import json
from pathlib import Path

import pytest

from scripts.analysis.playbook_g_full_field_benchmark import (
    evaluate_field,
    run_benchmark,
    select_latest_pre_off_fields,
)


def _snapshot_rows(run_id: str, created_at: str, race_id: str = "r1"):
    horses = [
        ("h1", "Alpha", 0.48, 0.8, 2.0),
        ("h2", "Beta", 0.46, 0.1, 4.0),
        ("h3", "Gamma", 0.06, 0.1, 10.0),
    ]
    return [
        {
            "run_id": run_id,
            "created_at": created_at,
            "race_date": "2026-09-18",
            "race_id": race_id,
            "course": "Ayr",
            "off_time": "2.00",
            "rank": rank,
            "horse_id": horse_id,
            "horse": horse,
            "velo_prime_prob": probability,
            "market_deception_score": mds,
            "sp_dec": sp,
            "live_scoring_changed": False,
        }
        for rank, (horse_id, horse, probability, mds, sp) in enumerate(horses)
    ]


def _write_jsonl(path: Path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _result(winner_id: str = "h2"):
    return {
        "race_id": "r1",
        "course": "Ayr",
        "off": "2.00",
        "runners": [
            {"horse_id": winner_id, "horse_rp_uid": winner_id, "horse": "Beta", "position": "1", "sp_dec": 4.0, "draw": "4"},
            {"horse_id": "h1", "horse_rp_uid": "h1", "horse": "Alpha", "position": "2", "sp_dec": 2.0},
            {"horse_id": "h3", "horse_rp_uid": "h3", "horse": "Gamma", "position": "3", "sp_dec": 10.0},
        ],
    }


def test_selects_latest_strictly_pre_off_run_and_rejects_post_off_and_contaminated(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    rows = []
    rows.extend(_snapshot_rows("early", "2026-09-18T11:00:00+01:00"))
    rows.extend(_snapshot_rows("latest", "2026-09-18T13:30:00+01:00"))
    rows.extend(_snapshot_rows("post", "2026-09-18T14:01:00+01:00"))
    rows.extend(_snapshot_rows("2026_09_18_32cc27f9_bad", "2026-09-18T13:45:00+01:00"))
    _write_jsonl(data / "runner_snapshots_2026_09_18_test.jsonl", rows)

    selected, diagnostics = select_latest_pre_off_fields(data)

    assert selected["r1"][0]["run_id"] == "latest"
    assert diagnostics["race_runs_post_off"] == 1
    assert diagnostics["rows_contaminated_run"] == 3
    assert diagnostics["superseded_pre_off_runs"] == 1


def test_evaluate_field_renormalises_all_runners_and_can_change_pick():
    field = _snapshot_rows("run", "2026-09-18T12:00:00+01:00")

    def adjuster(row, _state, _is_favourite):
        return (0.7, ["TEST_DAMPEN"]) if row["horse_id"] == "h1" else (1.0, [])

    race = evaluate_field(field, _result(), state={}, adjuster=adjuster)

    assert race is not None
    assert race["base_top_name"] == "Alpha"
    assert race["g_top_name"] == "Beta"
    assert race["pick_changed"] is True
    assert race["base_won"] is False
    assert race["g_won"] is True
    assert sum(row["base_prob"] for row in race["runners"]) == pytest.approx(1.0)
    assert sum(row["g_prob"] for row in race["runners"]) == pytest.approx(1.0)
    assert sum(row["market_prob"] for row in race["runners"]) == pytest.approx(1.0)
    assert race["market_top_name"] == "Alpha"


def test_end_to_end_benchmark_writes_only_explicit_disposable_output(tmp_path):
    data = tmp_path / "source_data"
    results = data / "results"
    output = tmp_path / "analysis_output"
    results.mkdir(parents=True)

    _write_jsonl(
        data / "runner_snapshots_2026_09_18_test.jsonl",
        _snapshot_rows("clean_run", "2026-09-18T12:00:00+01:00"),
    )
    (results / "rp_results_2026_09_18.json").write_text(
        json.dumps({"results": [_result()]}), encoding="utf-8"
    )
    live_state = data / "sentient_state.json"
    live_state.write_text(json.dumps({"total_races_observed": 999}), encoding="utf-8")
    live_before = live_state.read_bytes()

    summary = run_benchmark(
        data_dir=data,
        output_dir=output,
        start_date="2026-09-18",
        end_date="2026-09-18",
        bootstrap_samples=20,
    )

    assert summary["races_evaluated"] == 1
    assert summary["outcomes_replayed"] == 1
    assert summary["pick_changes"] == 1
    assert summary["market_implied"]["races"] == 1
    assert summary["same_race_market_comparison"]["races"] == 1
    assert summary["clean_shadow_state_summary"]["total_races_observed"] == 1
    assert summary["safety"]["live_state_written"] is False
    assert live_state.read_bytes() == live_before
    assert (output / "playbook_g_full_field_benchmark.json").exists()
    assert (output / "playbook_g_full_field_benchmark.md").exists()
    assert (output / "race_level_counterfactuals.csv").exists()
    assert (output / "clean_shadow_state.json").exists()
