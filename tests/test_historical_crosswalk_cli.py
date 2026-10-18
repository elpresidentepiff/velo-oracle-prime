from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from src.intelligence.historical_crosswalk_cli import run


def test_cli_writes_a_hashed_blocked_replay_for_empty_certified_cohort(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    output = tmp_path / "crosswalk.json"
    source.write_text(
        json.dumps(
            {
                "runner_prediction_snapshots": [],
                "velo_verdicts": [],
                "canonical_model_scorecards": [],
                "velo_race_truth": [],
            }
        ),
        encoding="utf-8",
    )
    args = SimpleNamespace(
        source_export=source,
        supabase_readonly=False,
        env_file=None,
        source_cache=None,
        snapshot_jsonl_dir=None,
        output=output,
        holdout_start="2026-06-20",
        holdout_end=None,
        baseline_ref="git:test",
        min_runners=300,
    )

    payload = run(args)

    assert output.exists()
    assert len(payload["artifact_sha256"]) == 64
    assert payload["evo2_replay"]["executable"] is False
    assert payload["evo2_replay"]["blocker"] == "INSUFFICIENT_COMPLETE_VERIFIED_RUNNERS"


def test_cli_reads_and_hashes_local_snapshot_archive(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps(
            {
                name: []
                for name in (
                    "runner_prediction_snapshots",
                    "velo_verdicts",
                    "canonical_model_scorecards",
                    "velo_race_truth",
                )
            }
        ),
        encoding="utf-8",
    )
    archive = tmp_path / "archive"
    archive.mkdir()
    (archive / "runner_snapshots_2026_06_20_test.jsonl").write_text(
        json.dumps(
            {
                "run_id": "test",
                "created_at": "2026-06-20T11:00:00Z",
                "race_date": "2026-06-20",
                "race_id": "921135",
                "course": "Ascot",
                "off_time": "2.30",
                "rank": 0,
                "horse_id": "h1",
                "horse": "Runner",
                "velo_prime_prob": 0.5,
                "sqpe_v17_prob": 0.5,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    args = SimpleNamespace(
        source_export=source,
        supabase_readonly=False,
        env_file=None,
        source_cache=None,
        snapshot_jsonl_dir=archive,
        output=tmp_path / "crosswalk.json",
        holdout_start="2026-06-20",
        holdout_end=None,
        baseline_ref="git:test",
        min_runners=300,
    )

    payload = run(args)

    assert payload["source_counts"]["runner_prediction_snapshots.local_jsonl"] == 1
    assert len(payload["source_hashes"]["runner_prediction_snapshots.local_jsonl"]) == 64
    assert len(payload["records"]) == 1
