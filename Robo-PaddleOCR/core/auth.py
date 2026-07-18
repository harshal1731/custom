import os
from dotenv import load_dotenv
from fastapi import Security, HTTPException, status, Header, Form
from typing import Optional

# Load variables from .env file if it exists
load_dotenv()

# Fetch API key from environment variable (default fallback if not set)
DEFAULT_API_KEY = "robo-secret-key-2026"
GET_API_KEY = os.getenv("API_KEY", DEFAULT_API_KEY)

async def verify_api_key(
    x_api_key_header: Optional[str] = Header(None, alias="X-API-Key"),
    x_api_key_form: Optional[str] = Form(None, alias="X-API-Key")
):
    """
    Verifies the presence and validity of the X-API-Key, 
    accepting it from either HTTP Headers or the Form body.
    """
    api_key = x_api_key_header or x_api_key_form
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key. Provide it in X-API-Key header or form field.",
        )
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
