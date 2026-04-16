from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi.responses import JSONResponse

from app import main


def test_schema_verification_fails_closed_in_strict_runtime(monkeypatch):
    monkeypatch.setattr(main.settings, "API_ENV", "production")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    try:
        asyncio.run(main._verify_schema_at_startup())
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass


def test_schema_verification_stays_soft_in_local_runtime(monkeypatch):
    monkeypatch.setattr(main.settings, "API_ENV", "local")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    asyncio.run(main._verify_schema_at_startup())


def test_score_trigger_rejects_duplicate_and_returns_run_id(monkeypatch):
    class _Request:
        async def json(self):
            return {"target_date": "2026-04-16", "trigger_source": "test"}

    monkeypatch.setenv("TRIGGER_SCORE_SECRET", "secret")
    monkeypatch.setattr(main, "_claim_trigger_run", lambda **kwargs: {"status": "duplicate", "run_id": "run-123", "detail": "run already running"})

    response = asyncio.run(main.trigger_score_daily(_Request(), x_trigger_secret="secret"))

    assert isinstance(response, JSONResponse)
    assert response.status_code == 409
    assert b"run-123" in response.body


def test_score_trigger_returns_durable_run_id_on_success(monkeypatch):
    class _Request:
        async def json(self):
            return {"target_date": "2026-04-16", "trigger_source": "test"}

    monkeypatch.setenv("TRIGGER_SCORE_SECRET", "secret")
    monkeypatch.setattr(main, "_claim_trigger_run", lambda **kwargs: {"status": "created", "run_id": "run-456"})
    monkeypatch.setattr(main.pathlib.Path, "exists", lambda self: True)
    monkeypatch.setattr(
        main,
        "_spawn_trigger_subprocess",
        lambda **kwargs: (SimpleNamespace(pid=999), kwargs["script_path"].parent.parent / "logs" / "triggers" / "score.log"),
    )

    response = asyncio.run(main.trigger_score_daily(_Request(), x_trigger_secret="secret"))

    assert response.status_code == 202
    assert b"run-456" in response.body
