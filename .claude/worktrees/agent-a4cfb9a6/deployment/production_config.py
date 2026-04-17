"""
VÉLØ Oracle - Production Deployment Configuration
FastAPI + Railway + Cloudflare
"""
import os
from typing import Optional


class ProductionConfig:
    """Production configuration"""
    
    # Environment
    ENV: str = os.getenv("ENV", "production")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # API
    API_TITLE: str = "VÉLØ Oracle API"
    API_VERSION: str = "v1.0"
    API_PREFIX: str = "/api"
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    WORKERS: int = int(os.getenv("WORKERS", "4"))
    
    # Database (Supabase)
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    
    # Authentication
    API_KEY: str = os.getenv("API_KEY", "")
    API_KEY_HEADER: str = "x-api-key"
    
    # Models
    MODELS_DIR: str = os.getenv("MODELS_DIR", "models")
    
    # Data
    DATASET_PATH: str = os.getenv("DATASET_PATH", "storage/velo-datasets/racing_full_1_7m.parquet")
    
    # Monitoring
    ENABLE_TELEMETRY: bool = os.getenv("ENABLE_TELEMETRY", "true").lower() == "true"
    ENABLE_DRIFT_DETECTION: bool = os.getenv("ENABLE_DRIFT_DETECTION", "true").lower() == "true"
    
    # Performance
    MAX_CONCURRENT_PREDICTIONS: int = int(os.getenv("MAX_CONCURRENT_PREDICTIONS", "100"))
    PREDICTION_TIMEOUT_SECONDS: int = int(os.getenv("PREDICTION_TIMEOUT_SECONDS", "5"))
    
    # Caching
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "true").lower() == "true"
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # CORS
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "*").split(",")
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    
    # Cloudflare
    CLOUDFLARE_ZONE_ID: str = os.getenv("CLOUDFLARE_ZONE_ID", "")
    CLOUDFLARE_API_TOKEN: str = os.getenv("CLOUDFLARE_API_TOKEN", "")
    
    # Railway
    RAILWAY_ENVIRONMENT: str = os.getenv("RAILWAY_ENVIRONMENT", "production")
    RAILWAY_PROJECT_ID: str = os.getenv("RAILWAY_PROJECT_ID", "")
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration"""
        required = [
            ("SUPABASE_URL", cls.SUPABASE_URL),
            ("SUPABASE_KEY", cls.SUPABASE_KEY),
            ("API_KEY", cls.API_KEY)
        ]
        
        missing = [name for name, value in required if not value]
        
        if missing:
            print(f"❌ Missing required config: {', '.join(missing)}")
            return False
        
        print("✅ Configuration validated")
        return True
    
    @classmethod
    def summary(cls):
        """Print configuration summary"""
        print("="*60)
        print("Production Configuration")
        print("="*60)
        print(f"Environment: {cls.ENV}")
        print(f"Debug: {cls.DEBUG}")
        print(f"Host: {cls.HOST}:{cls.PORT}")
        print(f"Workers: {cls.WORKERS}")
        print(f"API Version: {cls.API_VERSION}")
        print(f"Models Dir: {cls.MODELS_DIR}")
        print(f"Dataset: {cls.DATASET_PATH}")
        print(f"Telemetry: {cls.ENABLE_TELEMETRY}")
        print(f"Drift Detection: {cls.ENABLE_DRIFT_DETECTION}")
        print(f"Cache: {cls.ENABLE_CACHE}")
        print(f"Rate Limit: {cls.RATE_LIMIT_PER_MINUTE}/min")
        print("="*60)


if __name__ == "__main__":
    config = ProductionConfig()
    config.summary()
    config.validate()
