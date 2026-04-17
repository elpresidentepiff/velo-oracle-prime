from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class TelegramSettings:
    bot_token: str
    chat_id: str

    @property
    def configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)


def load_optional_env_file(env_file: str | Path | None) -> None:
    if not env_file:
        return
    load_dotenv(Path(env_file), override=False)


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_now_iso() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def resolve_supabase_service_key() -> str:
    return (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        or os.getenv("SUPABASE_SERVICE_KEY", "")
        or os.getenv("SUPABASE_KEY", "")
    )


def resolve_supabase_url() -> str:
    return os.getenv("SUPABASE_URL", "")


def resolve_telegram_settings() -> TelegramSettings:
    return TelegramSettings(
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
    )


def resolve_runtime_environment() -> str:
    return os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("ENV") or os.getenv("API_ENV") or "local"
