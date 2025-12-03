"""
Core configuration management for VÉLØ Oracle API
"""
import os
from typing import Optional
from pydantic import Field
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
    
    # CORS
    CORS_ORIGINS: list = ["*"]
    
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
