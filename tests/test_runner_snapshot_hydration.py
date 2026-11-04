import json

from scripts.ops import sync_runner_snapshots_from_supabase as sync


def test_hydrates_latest_run_without_database_id(monkeypatch, tmp_path):
    monkeypatch.setattr(sync, "latest_run_id", lambda date: "run-latest")
    monkeypatch.setattr(
        sync,
        "fetch_run_rows",
        lambda run_id: [
            {"id": 2, "run_id": run_id, "race_id": "r1", "rank": 1, "horse": "B"},
            {"id": 1, "run_id": run_id, "race_id": "r1", "rank": 0, "horse": "A"},
        ],
    )

    result = sync.hydrate_runner_snapshots("2026-11-04", tmp_path)

    assert result["status"] == "LOCAL_HYDRATED"
    assert result["row_count"] == 2
    assert result["race_count"] == 1
    assert result["write_back"] is False
    rows = [
        json.loads(line)
        for line in (tmp_path / "runner_snapshots_2026_11_04_run-latest.jsonl").read_text().splitlines()
    ]
    assert all("id" not in row for row in rows)
    assert {row["horse"] for row in rows} == {"A", "B"}


def test_no_durable_rows_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(sync, "latest_run_id", lambda date: None)

    result = sync.hydrate_runner_snapshots("2026-11-04", tmp_path)

    assert result == {
        "status": "NO_DURABLE_RUNNER_SNAPSHOTS",
        "date": "2026-11-04",
        "row_count": 0,
        "path": None,
    }
    assert list(tmp_path.iterdir()) == []


def test_fetch_run_rows_paginates(monkeypatch):
    first_page = [{"run_id": "r"}] * sync.PAGE_SIZE
    calls = []

    def fake_get(params):
        calls.append(params)
        return first_page if params["offset"] == "0" else [{"run_id": "r"}]

    monkeypatch.setattr(sync, "_get", fake_get)

    rows = sync.fetch_run_rows("r")

    assert len(rows) == sync.PAGE_SIZE + 1
    assert [call["offset"] for call in calls] == ["0", str(sync.PAGE_SIZE)]
