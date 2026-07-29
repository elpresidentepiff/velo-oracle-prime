"""verdicts_already_persisted(): must check pipeline_runs (not velo_verdicts.race_id), and
must fail closed (raise) rather than silently permit a second scoring pass when the check
itself cannot be completed -- this is the confirmed mechanism behind the 2026-07-15
double-scoring overwrite (see data/reports/runtime_scheduler_ownership_checkpoint_2026_07_20.md)."""
import pytest

from scripts.ops.run_full_raceday import IdempotenceCheckError, verdicts_already_persisted


class _FakeResult:
    def __init__(self, count):
        self.count = count


class _FakeQuery:
    def __init__(self, count, capture):
        self._count = count
        self._capture = capture

    def select(self, *args, **kwargs):
        self._capture["select_args"] = args
        self._capture["select_kwargs"] = kwargs
        return self

    def eq(self, field, value):
        self._capture.setdefault("eq_calls", []).append((field, value))
        return self

    def execute(self):
        return _FakeResult(self._count)


class _FakeTable:
    def __init__(self, count, capture):
        self._count = count
        self._capture = capture

    def __call__(self, name):
        self._capture["table_name"] = name
        return _FakeQuery(self._count, self._capture)


class _FakeClient:
    def __init__(self, count, capture):
        self.table = _FakeTable(count, capture)


def _patch_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")


def test_queries_pipeline_runs_not_velo_verdicts(monkeypatch):
    """The fixed check must query pipeline_runs by source_date/run_state/status --
    not velo_verdicts.race_id, which real numeric race IDs never date-match against."""
    _patch_env(monkeypatch)
    capture = {}
    monkeypatch.setattr("supabase.create_client", lambda *a, **k: _FakeClient(0, capture))

    verdicts_already_persisted("2026-07-15")

    assert capture["table_name"] == "pipeline_runs"
    eq_calls = dict(capture["eq_calls"])
    assert eq_calls["service_name"] == "velo-prime-scoring"
    assert eq_calls["source_date"] == "2026-07-15"
    assert eq_calls["run_state"] == "completed"
    assert eq_calls["status"] == "PASS"


def test_true_when_a_completed_pass_run_exists(monkeypatch):
    _patch_env(monkeypatch)
    capture = {}
    monkeypatch.setattr("supabase.create_client", lambda *a, **k: _FakeClient(1, capture))
    assert verdicts_already_persisted("2026-07-15") is True


def test_false_when_no_completed_pass_run_exists(monkeypatch):
    _patch_env(monkeypatch)
    capture = {}
    monkeypatch.setattr("supabase.create_client", lambda *a, **k: _FakeClient(0, capture))
    assert verdicts_already_persisted("2026-07-16") is False


def test_fails_closed_on_client_creation_error(monkeypatch):
    """A broken idempotence check must raise, never silently 'assume not scored'."""
    _patch_env(monkeypatch)

    def _boom(*a, **k):
        raise ConnectionError("network unreachable")

    monkeypatch.setattr("supabase.create_client", _boom)
    with pytest.raises(IdempotenceCheckError):
        verdicts_already_persisted("2026-07-15")


def test_fails_closed_on_query_error(monkeypatch):
    """A query-time failure (e.g. table/column drift) must also raise, not return False."""
    _patch_env(monkeypatch)

    class _BoomingQuery:
        def select(self, *a, **k):
            return self

        def eq(self, *a, **k):
            return self

        def execute(self):
            raise RuntimeError("PGRST: column does not exist")

    class _BoomingClient:
        def table(self, name):
            return _BoomingQuery()

    monkeypatch.setattr("supabase.create_client", lambda *a, **k: _BoomingClient())
    with pytest.raises(IdempotenceCheckError):
        verdicts_already_persisted("2026-07-15")
