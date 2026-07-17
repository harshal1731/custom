import os
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

# Fetch API key from environment variable (default fallback if not set)
DEFAULT_API_KEY = "robo-secret-key-2026"
GET_API_KEY = os.getenv("API_KEY", DEFAULT_API_KEY)

async def verify_api_key(api_key: str = Security(api_key_header)):
    """
    Dependency that verifies the presence and validity of the X-API-Key header.
    """
    if api_key != GET_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key. Access Denied.",
        )
    return api_key

def get_security_headers() -> dict:
    """
    Return a dictionary of security headers to attach to API responses.
    """
    return {
        "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none';",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
        "Referrer-Policy": "no-referrer",
    }
