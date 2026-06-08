"""
Security utilities for API authentication and authorization.
"""
from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

security = HTTPBearer(auto_error=False)


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> bool:
    """
    Fail-closed API key validation via Authorization: Bearer <key> header.

    Behaviour:
      - VELO_DEV_AUTH_BYPASS=1  → allowed (local dev only, never set in prod)
      - API_KEY not configured  → 503 Service Unavailable
      - Key missing or wrong    → 403 Forbidden
    """
    if os.getenv("VELO_DEV_AUTH_BYPASS", "").strip() == "1":
        return True

    api_key = os.getenv("API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="API key not configured on this server")

    provided = credentials.credentials if credentials else None
    if not provided or not hmac.compare_digest(provided, api_key):
        raise HTTPException(status_code=403, detail="Invalid API key")

    return True


def get_cors_config():
    """Get CORS middleware configuration"""
    return {
        "allow_origins": settings.CORS_ORIGINS,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
