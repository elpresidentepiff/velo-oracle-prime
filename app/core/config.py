"""
Core configuration management for VÉLØ Oracle API
"""

import json
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # API Configuration
    API_VERSION: str = "v1"
    API_ENV: str = Field(default="production")
    API_TITLE: str = "VÉLØ Oracle API"
    API_DESCRIPTION: str = "Production ML API for horse racing predictions"

    # Supabase Configuration
    SUPABASE_URL: str = Field(default="")
    SUPABASE_KEY: str = Field(default="")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(default="")

    # Model Registry
    MODEL_REGISTRY_PATH: str = Field(default="ml/models/")
    ACTIVE_MODEL_NAME: str = Field(default="SQPE")
    ACTIVE_MODEL_VERSION: str = Field(default="v1_real")

    # Feature Engineering
    FEATURE_MAP_PATH: str = "app/ml/feature_map.json"

    # CORS — accepts plain string ("*"), comma-separated string, or JSON list
    CORS_ORIGINS: list[str] | str = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            # Comma-separated or plain wildcard
            return [item.strip() for item in v.split(",") if item.strip()]
        return ["*"]

    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    LOG_JSON: bool = Field(default=True)

    # Performance
    MODEL_CACHE_SIZE: int = 3
    REQUEST_TIMEOUT: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# Global settings instance
settings = Settings()
