"""
blast_ocr.api.dependencies

API dependencies for authentication and authorization.
"""

from typing import Optional
from fastapi import Header, HTTPException, status
from blast_ocr.config import config


async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> str:
    """
    Validates API key header or Bearer token against configured BLAST_OCR_API_KEY.
    If no API key is configured in the environment (default for local/dev), requests pass through.
    """
    configured_key = getattr(config, "api_key", None)
    if not configured_key:
        return "anonymous-dev"

    provided_key = None
    if x_api_key:
        provided_key = x_api_key.strip()
    elif authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() in ("bearer", "apikey"):
            provided_key = parts[1]
        elif len(parts) == 1:
            provided_key = parts[0]

    if not provided_key or provided_key != configured_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Provide a valid 'X-API-Key' or 'Authorization: Bearer <key>' header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return provided_key
