"""
Core configuration management for VÉLØ Oracle API
"""
import os
from typing import Optional
from pydantic import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # API Configuration
    API_VERSION: str = "v1"
    API_ENV: str = os.getenv("API_ENV", "production")
    API_TITLE: str = "VÉLØ Oracle API"
    API_DESCRIPTION: str = "Production ML API for horse racing predictions"
    
    # Supabase Configuration
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    
    # Model Registry
    MODEL_REGISTRY_PATH: str = os.getenv("MODEL_REGISTRY_PATH", "ml/models/")
    ACTIVE_MODEL_NAME: str = os.getenv("ACTIVE_MODEL_NAME", "SQPE")
    ACTIVE_MODEL_VERSION: str = os.getenv("ACTIVE_MODEL_VERSION", "v1_real")
    
    # Feature Engineering
    FEATURE_MAP_PATH: str = "app/ml/feature_map.json"
    
    # CORS
    CORS_ORIGINS: list = ["*"]
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_JSON: bool = os.getenv("LOG_JSON", "true").lower() == "true"
    
    # Performance
    MODEL_CACHE_SIZE: int = 3
    REQUEST_TIMEOUT: int = 30
    
    class Config:
        case_sensitive = True
        env_file = ".env"


# Global settings instance
settings = Settings()

