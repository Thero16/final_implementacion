"""FastAPI dependency for validating Keycloak-issued JWT tokens."""
import logging
from functools import lru_cache

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from src.backend.config.settings import get_settings

logger = logging.getLogger(__name__)
security = HTTPBearer()


@lru_cache(maxsize=1)
def _get_jwks() -> dict:
    """Fetch Keycloak's public keys (cached for the process lifetime)."""
    settings = get_settings()
    url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/certs"
    try:
        response = httpx.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.error("Failed to fetch Keycloak JWKS from %s: %s", url, exc)
        raise


def _decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        jwks = _get_jwks()
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return payload
    except JWTError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as exc:
        logger.error("Unexpected error during token validation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Validate the Bearer token and return the decoded user claims."""
    return _decode_token(credentials.credentials)
