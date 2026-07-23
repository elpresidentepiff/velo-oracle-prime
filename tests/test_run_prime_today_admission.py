"""SCORING-RUN-ADMISSION-HARDENING-01: completed-PASS admission gate, PIPELINE_RUN_ID
validation, and authorised-rescore artifact behavior in run_prime_today.py's
_open_pipeline_run(). True concurrent-overlap atomicity is proven separately against a
real temporary Postgres instance (see test_run_prime_today_admission_concurrency.py) --
a mocked client alone cannot prove that, per SCORING-RUN-ADMISSION-HARDENING-01 P0-4."""
import json

import pytest

from scripts.ops.run_prime_today import (
    PipelineRunOpenResult,
    _open_pipeline_run,
    _validate_supplied_run_id,
)


class _FakeQuery:
    def __init__(self, table_name, responder):
        self._table = table_name
        self._responder = responder
        self._filters = {}

    def select(self, *a, **k):
        return self

    def eq(self, field, value):
        self._filters[field] = value
        return self

    def insert(self, row):
        self._insert_row = row
        return self

    def update(self, fields):
        self._update_fields = fields
        return self

    def execute(self):
        return self._responder(self._table, dict(self._filters), getattr(self, "_insert_row", None))


class _FakeClient:
    """responder(table_name, filters, insert_row) -> object with .data / .count, or raises."""

    def __init__(self, responder):
        self._responder = responder

    def table(self, name):
        return _FakeQuery(name, self._responder)


class _Result:
    def __init__(self, data=None, count=None):
        self.data = data
        self.count = count


def _no_prior_no_running_then_insert_ok(insert_capture):
    def responder(table, filters, insert_row):
        assert table == "pipeline_runs"
        if insert_row is not None:
            insert_capture.append(insert_row)
            return _Result(data=[{"id": insert_row["id"]}])
        if filters.get("run_state") == "completed" and filters.get("status") == "PASS":
            return _Result(data=[])
        if filters.get("run_state") == "running":
            return _Result(data=[])
        raise AssertionError(f"unexpected query filters: {filters}")

    return responder


def test_no_prior_run_is_admitted(monkeypatch, tmp_path):
    monkeypatch.delenv("PIPELINE_RUN_ID", raising=False)
    inserted = []
    client = _FakeClient(_no_prior_no_running_then_insert_ok(inserted))
    result = _open_pipeline_run(client, "2026-07-21")
    assert result.run_id is not None
    assert result.blocked_reason is None
    assert inserted[0]["run_type"] == "daily_scoring"


def test_completed_pass_blocks_by_default(monkeypatch):
    monkeypatch.delenv("PIPELINE_RUN_ID", raising=False)

    def responder(table, filters, insert_row):
        if filters.get("run_state") == "completed" and filters.get("status") == "PASS":
            return _Result(
                data=[
                    {"id": "run-1", "started_at": "2026-07-14T08:44:55Z", "finished_at": "2026-07-14T08:45:34Z", "commit_sha": "aaa"},
                    {"id": "run-2", "started_at": "2026-07-14T14:07:13Z", "finished_at": "2026-07-14T14:07:48Z", "commit_sha": "bbb"},
                ]
            )
        raise AssertionError("should not reach the running-row check when already blocked")

    client = _FakeClient(responder)
    result = _open_pipeline_run(client, "2026-07-14")
    assert result.run_id is None
    assert result.blocked_reason is not None
    assert "run-1" in result.blocked_reason and "run-2" in result.blocked_reason
    assert "2 completed PASS" in result.blocked_reason


def test_completed_fail_does_not_block(monkeypatch):
    monkeypatch.delenv("PIPELINE_RUN_ID", raising=False)
    inserted = []

    def responder(table, filters, insert_row):
        if insert_row is not None:
            inserted.append(insert_row)
            return _Result(data=[{"id": insert_row["id"]}])
        if filters.get("run_state") == "completed" and filters.get("status") == "PASS":
            return _Result(data=[])  # the FAIL row doesn't match this filter
        if filters.get("run_state") == "running":
            return _Result(data=[])
        raise AssertionError(f"unexpected filters {filters}")

    client = _FakeClient(responder)
    result = _open_pipeline_run(client, "2026-07-13")
    assert result.run_id is not None
    assert result.blocked_reason is None


def test_authorised_rescore_bypasses_block_and_writes_artifact(monkeypatch, tmp_path):
    monkeypatch.delenv("PIPELINE_RUN_ID", raising=False)
    import scripts.ops.run_prime_today as rpt

    monkeypatch.setattr(rpt, "ROOT", tmp_path)
    inserted = []

    def responder(table, filters, insert_row):
        if insert_row is not None:
            inserted.append(insert_row)
            return _Result(data=[{"id": insert_row["id"]}])
        if filters.get("run_state") == "completed" and filters.get("status") == "PASS":
            return _Result(data=[{"id": "run-1", "started_at": "t0", "finished_at": "t1", "commit_sha": "aaa"}])
        if filters.get("run_state") == "running":
            return _Result(data=[])
        raise AssertionError(f"unexpected filters {filters}")

    client = _FakeClient(responder)
    result = _open_pipeline_run(client, "2026-07-14", rescore_reason="INC-42 confirmed bad passport data")
    assert result.run_id is not None
    assert inserted[0]["run_type"] == "authorised_rescore"

    artifact_dir = tmp_path / "data" / "reports" / "rescore_authorizations"
    files = list(artifact_dir.glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert payload["reason"] == "INC-42 confirmed bad passport data"
    assert payload["prior_completed_pass_run_ids"] == ["run-1"]
    assert payload["new_run_id"] == inserted[0]["id"]


def test_admission_check_failure_is_an_error_not_a_silent_pass(monkeypatch):
    monkeypatch.delenv("PIPELINE_RUN_ID", raising=False)

    def responder(table, filters, insert_row):
        raise ConnectionError("supabase unreachable")

    client = _FakeClient(responder)
    result = _open_pipeline_run(client, "2026-07-21")
    assert result.run_id is None
    assert result.error is not None


def test_valid_supplied_run_id_is_reused(monkeypatch):
    def responder(table, filters, insert_row):
        assert filters.get("id") == "good-run-id"
        return _Result(
            data=[{"id": "good-run-id", "service_name": "velo-prime-scoring", "source_date": "2026-07-21", "run_state": "running", "status": None}]
        )

    client = _FakeClient(responder)
    result = _validate_supplied_run_id(client, "good-run-id", "velo-prime-scoring", "2026-07-21")
    assert result.run_id == "good-run-id"
    assert result.error is None


@pytest.mark.parametrize(
    "row,expected_substring",
    [
        (None, "does not exist"),
        ({"id": "x", "service_name": "wrong-service", "source_date": "2026-07-21", "run_state": "running", "status": None}, "service_name"),
        ({"id": "x", "service_name": "velo-prime-scoring", "source_date": "2026-07-20", "run_state": "running", "status": None}, "source_date"),
        ({"id": "x", "service_name": "velo-prime-scoring", "source_date": "2026-07-21", "run_state": "completed", "status": "PASS"}, "run_state"),
        ({"id": "x", "service_name": "velo-prime-scoring", "source_date": "2026-07-21", "run_state": "running", "status": "PASS"}, "status"),
    ],
)
def test_invalid_supplied_run_id_hard_aborts(row, expected_substring):
    def responder(table, filters, insert_row):
        return _Result(data=[row] if row else [])

    client = _FakeClient(responder)
    result = _validate_supplied_run_id(client, "x", "velo-prime-scoring", "2026-07-21")
    assert result.run_id is None
    assert result.error is not None
    assert expected_substring in result.error


def test_invalid_supplied_run_id_short_circuits_before_any_insert(monkeypatch):
    """A rejected PIPELINE_RUN_ID must hard-abort -- never silently fall through to
    creating or reusing a different run."""
    monkeypatch.setenv("PIPELINE_RUN_ID", "bad-run-id")

    def responder(table, filters, insert_row):
        if insert_row is not None:
            raise AssertionError("must not attempt an insert when the supplied run_id is invalid")
        return _Result(data=[])  # run_id lookup returns nothing -> "does not exist"

    client = _FakeClient(responder)
    result = _open_pipeline_run(client, "2026-07-21")
    assert result.run_id is None
    assert result.error is not None
    assert "does not exist" in result.error
