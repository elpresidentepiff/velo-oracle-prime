"""
VÉLØ v10 - Centralized Settings
Type-safe configuration with Pydantic validation
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """
    Centralized configuration for VÉLØ Oracle
    All settings loaded from environment variables or .env file
    """
    
    # Betfair API Configuration
    BETFAIR_USERNAME: Optional[str] = Field(None, description="Betfair account username")
    BETFAIR_PASSWORD: Optional[str] = Field(None, description="Betfair account password")
    BETFAIR_APP_KEY: Optional[str] = Field(None, description="Betfair application key")
    BETFAIR_CERT_PATH: Optional[str] = Field(None, description="Path to Betfair SSL certificate")
    BETFAIR_KEY_PATH: Optional[str] = Field(None, description="Path to Betfair SSL key")
    
    # Racing API Configuration
    RACING_API_KEY: Optional[str] = Field(None, description="The Racing API key")
    RACING_API_BASE_URL: str = Field(
        "https://api.theracingapi.com",
        description="Base URL for Racing API"
    )
    
    # Database Configuration
    DB_HOST: str = Field("localhost", description="Database host")
    DB_PORT: int = Field(5432, description="Database port")
    DB_NAME: str = Field("velo", description="Database name")
    DB_USER: str = Field("velo", description="Database user")
    DB_PASSWORD: str = Field("velo", description="Database password")
    DATABASE_URL: Optional[str] = Field(
        None,
        description="Full database URL (overrides individual DB settings)"
    )
    
    # Oracle Configuration
    MIN_ODDS: float = Field(1.5, description="Minimum odds to consider")
    MAX_ODDS: float = Field(200.0, description="Maximum odds to consider")
    CONFIDENCE_THRESHOLD: float = Field(
        0.02,
        description="Minimum overlay confidence (p_model - p_market)"
    )
    FRACTIONAL_KELLY: float = Field(
        0.33,
        description="Fraction of Kelly criterion to use (0.0-1.0)"
    )
    
    # Benter Model Configuration
    ALPHA: float = Field(0.9, description="Weight for fundamental model")
    BETA: float = Field(1.1, description="Weight for public odds model")
    
    # HTTP Configuration
    HTTP_TIMEOUT: int = Field(6, description="Default HTTP timeout in seconds")
    HTTP_MAX_RETRIES: int = Field(5, description="Maximum HTTP retry attempts")
    HTTP_BACKOFF_MIN: float = Field(1.0, description="Minimum backoff time in seconds")
    HTTP_BACKOFF_MAX: float = Field(8.0, description="Maximum backoff time in seconds")
    
    # Logging Configuration
    LOG_LEVEL: str = Field("INFO", description="Logging level")
    LOG_DIR: str = Field("logs", description="Directory for log files")
    
    # Environment
    ENV: str = Field("development", description="Environment (development/production)")
    DEBUG: bool = Field(False, description="Enable debug mode")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
        case_sensitive = False
    
    @property
    def db_url(self) -> str:
        """
        Construct database URL from individual settings or use DATABASE_URL
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENV.lower() == "production"
    
    def has_betfair_credentials(self) -> bool:
        """Check if Betfair credentials are configured"""
        return all([
            self.BETFAIR_USERNAME,
            self.BETFAIR_PASSWORD,
            self.BETFAIR_APP_KEY
        ])
    
    def has_racing_api_key(self) -> bool:
        """Check if Racing API key is configured"""
        return self.RACING_API_KEY is not None


# Global settings instance
settings = Settings()

