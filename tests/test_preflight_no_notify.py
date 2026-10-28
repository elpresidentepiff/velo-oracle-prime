from __future__ import annotations

import pytest

from src import preflight


def test_no_notify_env_check_does_not_require_telegram(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    result = preflight._check_env_vars(require_telegram=False)

    assert result.passed is True
    assert "telegram disabled" in result.detail


def test_notify_env_check_stays_strict(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    result = preflight._check_env_vars(require_telegram=True)

    assert result.passed is False
    assert "TELEGRAM_BOT_TOKEN" in result.detail
    assert "TELEGRAM_CHAT_ID" in result.detail


def test_no_notify_preflight_does_not_call_telegram_on_failure(monkeypatch):
    failed = preflight.PreflightResult()
    failed.add(
        preflight.PreflightCheck(
            "supabase", preflight.Severity.CRITICAL, False, "unreachable"
        )
    )
    monkeypatch.setattr(preflight, "preflight", lambda **_: failed)
    calls: list[str] = []

    with pytest.raises(SystemExit):
        preflight.preflight_or_die(
            tg_fn=calls.append,
            require_telegram=False,
        )

    assert calls == []
