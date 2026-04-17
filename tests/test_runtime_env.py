from __future__ import annotations

import tempfile
from pathlib import Path

from app.core.runtime_env import (
    load_optional_env_file,
    resolve_runtime_environment,
    resolve_supabase_service_key,
    resolve_telegram_settings,
)


def test_load_optional_env_file_populates_values(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False, encoding="utf-8") as handle:
        handle.write("TELEGRAM_BOT_TOKEN=test-token\nTELEGRAM_CHAT_ID=12345\n")
        env_path = Path(handle.name)
    try:
        load_optional_env_file(env_path)
    finally:
        env_path.unlink(missing_ok=True)

    settings = resolve_telegram_settings()
    assert settings.bot_token == "test-token"
    assert settings.chat_id == "12345"
    assert settings.configured is True


def test_resolve_supabase_service_key_uses_canonical_order(monkeypatch):
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "legacy-service")
    monkeypatch.setenv("SUPABASE_KEY", "deprecated")

    assert resolve_supabase_service_key() == "legacy-service"

    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "canonical")
    assert resolve_supabase_service_key() == "canonical"


def test_resolve_runtime_environment_prefers_railway(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("API_ENV", "staging")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "railway-prod")

    assert resolve_runtime_environment() == "railway-prod"
