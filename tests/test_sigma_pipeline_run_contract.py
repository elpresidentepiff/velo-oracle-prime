from __future__ import annotations

import json

import pytest

from scripts.ops import run_results_sigma as sigma


def test_open_sigma_run_uses_null_status_for_active_row(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_request(method: str, path: str, data: dict | None = None) -> tuple[int, bytes]:
        captured.update(method=method, path=path, data=data)
        return 201, b""

    monkeypatch.setattr(sigma, "SB_URL", "https://example.supabase.co")
    monkeypatch.setattr(sigma, "SB_KEY", "service-key")
    monkeypatch.setattr(sigma, "_pipeline_request", fake_request)

    run_id = sigma._open_sigma_run("2026-11-03")

    assert run_id
    assert captured["method"] == "POST"
    assert captured["path"] == "/pipeline_runs"
    assert captured["data"]["run_state"] == "running"  # type: ignore[index]
    assert captured["data"]["status"] is None  # type: ignore[index]


def test_open_sigma_run_fails_loudly_when_persistence_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"code": "23514", "message": "terminal-only contract rejected active status"}

    monkeypatch.setattr(sigma, "SB_URL", "https://example.supabase.co")
    monkeypatch.setattr(sigma, "SB_KEY", "service-key")
    monkeypatch.setattr(
        sigma,
        "_pipeline_request",
        lambda *_args, **_kwargs: (400, json.dumps(body).encode()),
    )

    with pytest.raises(RuntimeError, match="HTTP 400.*23514"):
        sigma._open_sigma_run("2026-11-03")
