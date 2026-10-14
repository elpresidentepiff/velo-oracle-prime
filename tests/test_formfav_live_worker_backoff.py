from __future__ import annotations

from scripts.ops import formfav_live_worker as worker


def test_rate_limit_opens_one_global_provider_cooldown(monkeypatch) -> None:
    monkeypatch.setattr(worker.time, "time", lambda: 1_000.0)
    monkeypatch.setattr(worker, "RATE_LIMIT_BACKOFF_SECONDS", 900)
    monkeypatch.setattr(worker, "_provider_rate_limited_until", 0.0)

    assert worker._activate_provider_backoff(RuntimeError("HTTP 429")) is True
    assert worker._provider_backoff_remaining() == 900


def test_non_rate_limit_error_does_not_open_provider_cooldown(monkeypatch) -> None:
    monkeypatch.setattr(worker.time, "time", lambda: 1_000.0)
    monkeypatch.setattr(worker, "_provider_rate_limited_until", 0.0)

    assert worker._activate_provider_backoff(RuntimeError("HTTP 404")) is False
    assert worker._provider_backoff_remaining() == 0
