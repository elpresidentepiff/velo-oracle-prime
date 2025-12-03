"""
Security utilities for API authentication and authorization
"""
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

security = HTTPBearer(auto_error=False)


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    Verify API key from Authorization header
    Optional: Can be enabled for production authentication
    """
    # For now, authentication is optional
    # In production, implement proper API key validation
    return credentials


def get_cors_config():
    """Get CORS middleware configuration"""
    return {
        "allow_origins": settings.CORS_ORIGINS,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }

