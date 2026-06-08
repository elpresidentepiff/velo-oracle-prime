from __future__ import annotations

from scripts.ops import run_prime_today


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db, operation: str, payload=None):
        self.db = db
        self.operation = operation
        self.payload = payload

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def execute(self):
        if self.operation == "select":
            return _Response([])
        if self.operation == "insert":
            self.db.inserted.append(self.payload)
            return _Response([self.payload])
        raise AssertionError(f"unexpected operation: {self.operation}")


class _FakeDb:
    def __init__(self):
        self.inserted = []

    def table(self, name: str):
        assert name == "pipeline_runs"
        return self

    def select(self, *_args):
        return _Query(self, "select")

    def insert(self, payload):
        return _Query(self, "insert", payload)


def test_open_pipeline_run_persists_truth_row(monkeypatch):
    monkeypatch.delenv("PIPELINE_RUN_ID", raising=False)
    monkeypatch.setenv("TRIGGER_SOURCE", "manual")
    db = _FakeDb()

    result = run_prime_today._open_pipeline_run(db, "2026-06-08")

    assert result.run_id
    assert len(db.inserted) == 1
    assert db.inserted[0]["id"] == result.run_id
    assert db.inserted[0]["source_date"] == "2026-06-08"
    assert db.inserted[0]["run_state"] == "running"
