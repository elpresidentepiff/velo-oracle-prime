"""The EOD container must see the two morning-only inputs the learning gate is decided from.

Every night the cloud EOD finished `FAIL_GATE_BLOCKED`: the Council's data auditor said MISSING_SNAPSHOTS and mission
control said source_truth UNKNOWN. Both were true of the clean EOD container's disk, not of the data: the runner snapshots
are in `runner_prediction_snapshots`, and the run observability packet (the only place the day's source truth is read
from) is written to local disk by the morning container and was never saved. Step 12C (place stack) died on the same
missing snapshot file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.ops.persist_daily_artifacts as pda
import scripts.ops.rp_cloud_eod as eod
import scripts.ops.run_place_stack_shadow as place_stack
import scripts.ops.sync_runner_snapshots_from_supabase as sync
import scripts.ops.update_mission_control as umc
import src.velo.council.agents as council_agents

DATE = "2026-11-07"
TAG = "2026_11_07"


def _packet(root: Path, run_id: str, *, label: str, ts: str, mtime: float | None = None) -> Path:
    path = root / "data" / f"velo_run_observability_{TAG}_{run_id[:8]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"date": DATE, "run_id": run_id, "source_truth": label, "timestamp": ts}), encoding="utf-8"
    )
    return path


def _across_the_container_boundary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Morning container persists its artifacts; a clean EOD container restores them from the table."""
    morning, evening = tmp_path / "morning", tmp_path / "evening"
    morning.mkdir()
    evening.mkdir()
    _packet(morning, "aaaaaaaa-1", label="RP_MERGED_DEGRADED", ts="2026-11-07T07:00:00Z")
    _packet(morning, "bbbbbbbb-2", label="RP_MERGED_CLEAN", ts="2026-11-07T07:20:00Z")  # the retry: final run wins
    monkeypatch.setattr(pda, "ROOT", morning)
    persisted = json.loads(json.dumps(pda.build_reports([DATE]), default=str))
    monkeypatch.setattr(eod, "ROOT", evening)
    monkeypatch.setattr(eod, "_get", lambda table, params: persisted)
    eod._hydrate_report_artifacts(DATE)
    return evening


def test_a_clean_container_reads_the_source_truth_as_unknown(tmp_path) -> None:
    assert umc._read_observability_source_truth(DATE, tmp_path / "data") == "UNKNOWN"


def test_the_newest_packet_is_persisted_and_mission_control_reads_its_label_after_the_restore(
    tmp_path, monkeypatch
) -> None:
    evening = _across_the_container_boundary(tmp_path, monkeypatch)
    assert umc._read_observability_source_truth(DATE, evening / "data") == "RP_MERGED_CLEAN"
    restored = sorted((evening / "data").glob(f"velo_run_observability_{TAG}_*.json"))
    assert [p.name for p in restored] == [f"velo_run_observability_{TAG}_bbbbbbbb.json"]  # only the final run


def test_a_degraded_label_is_restored_as_degraded_the_gate_is_not_made_easier(tmp_path, monkeypatch) -> None:
    morning, evening = tmp_path / "m", tmp_path / "e"
    morning.mkdir()
    evening.mkdir()
    _packet(morning, "cccccccc-3", label="RP_MERGED_DEGRADED", ts="2026-11-07T07:20:00Z")
    monkeypatch.setattr(pda, "ROOT", morning)
    persisted = json.loads(json.dumps(pda.build_reports([DATE]), default=str))
    monkeypatch.setattr(eod, "ROOT", evening)
    monkeypatch.setattr(eod, "_get", lambda table, params: persisted)
    eod._hydrate_report_artifacts(DATE)
    source_truth = umc._read_observability_source_truth(DATE, evening / "data")
    assert source_truth == "RP_MERGED_DEGRADED"
    learning_gate, _promotion, reasons = umc._gate_status(0, 0, source_truth)
    assert learning_gate == umc.MC_CONFIG.LEARNING_GATE_BLOCKED and "GATE_SOURCE_DEGRADED" in reasons


def test_no_packet_means_no_row_so_nothing_is_invented(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(pda, "ROOT", tmp_path)
    assert pda.build_reports([DATE]) == []


def test_an_unreadable_packet_is_skipped_and_an_older_readable_one_is_kept(tmp_path, monkeypatch) -> None:
    _packet(tmp_path, "dddddddd-4", label="RP_MERGED_CLEAN", ts="2026-11-07T07:00:00Z")
    bad = tmp_path / "data" / f"velo_run_observability_{TAG}_eeeeeeee.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(pda, "ROOT", tmp_path)
    rows = pda.build_reports([DATE])
    assert len(rows) == 1 and rows[0]["payload"]["source_truth"] == "RP_MERGED_CLEAN"


def test_restored_runner_snapshots_are_found_by_the_council_and_the_place_stack(tmp_path, monkeypatch) -> None:
    rows = [
        {"id": 1, "run_id": "run_2026_11_07_abc12345", "race_id": "930514", "horse": "Alexei", "rank": 0},
        {"id": 2, "run_id": "run_2026_11_07_abc12345", "race_id": "930514", "horse": "Idem", "rank": 1},
    ]
    monkeypatch.setattr(sync, "latest_run_id", lambda date: "run_2026_11_07_abc12345")
    monkeypatch.setattr(sync, "fetch_run_rows", lambda run_id: [dict(r) for r in rows])
    result = sync.hydrate_runner_snapshots(DATE, tmp_path / "data")
    assert result["status"] == "LOCAL_HYDRATED" and result["row_count"] == 2 and result["write_back"] is False

    monkeypatch.setattr(council_agents, "ROOT", tmp_path)
    assert council_agents._load_snapshots_meta(DATE)["snapshot_files"]  # no longer MISSING_SNAPSHOTS
    monkeypatch.setattr(place_stack, "ROOT", tmp_path)
    assert {r["horse"] for r in place_stack.load_snapshot(DATE)} == {"Alexei", "Idem"}


def test_without_the_restore_both_consumers_fail_exactly_as_they_did_on_2026_11_07(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(council_agents, "ROOT", tmp_path)
    assert not council_agents._load_snapshots_meta(DATE)["snapshot_files"]
    monkeypatch.setattr(place_stack, "ROOT", tmp_path)
    with pytest.raises(FileNotFoundError):
        place_stack.load_snapshot(DATE)


def test_the_snapshot_restore_never_takes_the_eod_down(monkeypatch) -> None:
    def boom(date, output_dir):
        raise RuntimeError("SUPABASE_URL not set")

    monkeypatch.setattr(sync, "hydrate_runner_snapshots", boom)
    result = eod._hydrate_runner_snapshots(DATE)
    assert result["status"] == "HYDRATION_ERROR" and "SUPABASE_URL" in result["error"]

    monkeypatch.setattr(
        sync,
        "hydrate_runner_snapshots",
        lambda date, output_dir: {"status": "NO_DURABLE_RUNNER_SNAPSHOTS", "date": date},
    )
    assert eod._hydrate_runner_snapshots(DATE)["status"] == "NO_DURABLE_RUNNER_SNAPSHOTS"  # reported, not invented


def test_the_restore_runs_before_anything_captures_or_scores() -> None:
    src = (Path(__file__).parents[1] / "scripts" / "ops" / "rp_cloud_eod.py").read_text(encoding="utf-8")
    main_src = src[src.index("def main()") :]
    assert main_src.index("_hydrate_runner_snapshots(date_str)") < main_src.index("_login()")
    assert main_src.index("_hydrate_runner_snapshots(date_str)") < main_src.index("canonical EOD sequence")
