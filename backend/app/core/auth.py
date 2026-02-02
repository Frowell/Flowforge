"""Authentication utilities.

Two auth modes:
- Keycloak OIDC: canvas and dashboard routes (SSO across multiple identity providers)
- API key: embed routes (sk_live_... tokens)
"""

import hashlib

import structlog
from functools import lru_cache
from uuid import UUID

logger = structlog.stdlib.get_logger(__name__)

import httpx
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.dashboard import APIKey

# Keycloak OIDC discovery endpoint
_KEYCLOAK_REALM_URL = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
_JWKS_URL = f"{_KEYCLOAK_REALM_URL}/protocol/openid-connect/certs"
_ISSUER = _KEYCLOAK_REALM_URL

# Cached JWKS keys (refreshed on cache miss / key rotation)
_jwks_cache: dict | None = None


async def _get_jwks() -> dict:
    """Fetch Keycloak JWKS (JSON Web Key Set) for token verification."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get(_JWKS_URL)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        return _jwks_cache


def _clear_jwks_cache() -> None:
    """Clear cached JWKS — called on key-not-found to handle key rotation."""
    global _jwks_cache
    _jwks_cache = None


async def _decode_token(token: str) -> dict:
    """Decode and validate a Keycloak-issued JWT.

    Validates issuer, audience, and signature against Keycloak's JWKS.
    On key-not-found, clears cache and retries once (handles key rotation).
    """
    jwks = await _get_jwks()
    try:
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.keycloak_client_id,
            issuer=_ISSUER,
        )
        return payload
    except JWTError:
        # Retry once with fresh keys in case of key rotation
        _clear_jwks_cache()
        jwks = await _get_jwks()
        try:
            payload = jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                audience=settings.keycloak_client_id,
                issuer=_ISSUER,
            )
            return payload
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired token: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            )


async def get_current_user_id(request: Request) -> UUID:
    """Extract and validate the current user from a Keycloak Bearer token.

    Used for canvas and dashboard routes.
    In development mode, returns a hardcoded dev user when no auth header is present.
    """
    auth_header = request.headers.get("Authorization")

    # Dev-mode bypass: no auth header and development environment
    if settings.app_env == "development" and (not auth_header or not auth_header.startswith("Bearer ")):
        logger.warning("dev_auth_bypass", msg="Using dev user ID — no auth header in development mode")
        user_id = UUID(settings.dev_user_id)
        structlog.contextvars.bind_contextvars(user_id=str(user_id))
        return user_id

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.removeprefix("Bearer ")
    payload = await _decode_token(token)

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )

    user_id = UUID(sub)
    structlog.contextvars.bind_contextvars(user_id=str(user_id))
    return user_id


async def get_current_tenant_id(request: Request) -> UUID:
    """Extract tenant_id from the Keycloak JWT claims.

    Keycloak must be configured with a protocol mapper that includes
    a 'tenant_id' claim in the access token. This is the single source
    of truth for tenant context — never accept tenant_id from request bodies.
    In development mode, returns a hardcoded dev tenant when no auth header is present.
    """
    auth_header = request.headers.get("Authorization")

    # Dev-mode bypass: no auth header and development environment
    if settings.app_env == "development" and (not auth_header or not auth_header.startswith("Bearer ")):
        logger.warning("dev_auth_bypass", msg="Using dev tenant ID — no auth header in development mode")
        tid = UUID(settings.dev_tenant_id)
        structlog.contextvars.bind_contextvars(tenant_id=str(tid))
        return tid

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.removeprefix("Bearer ")
    payload = await _decode_token(token)

    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token missing tenant_id claim",
        )

    tid = UUID(tenant_id)
    structlog.contextvars.bind_contextvars(tenant_id=str(tid))
    return tid


async def get_current_user_claims(request: Request) -> dict:
    """Extract full Keycloak claims — useful for role/group checks.

    Returns the decoded JWT payload with claims like:
    - sub: user UUID
    - email: user email
    - realm_access.roles: Keycloak realm roles
    - resource_access.<client>.roles: client-specific roles
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.removeprefix("Bearer ")
    return await _decode_token(token)


async def validate_api_key(
    api_key: str,
    db: AsyncSession,
) -> dict:
    """Validate an embed API key and return its scope.

    API keys are scoped to specific widgets or dashboards.
    Format: sk_live_<random>

    Returns dict with: tenant_id, user_id, scoped_widget_ids, rate_limit, key_hash
    """
    if not api_key.startswith("sk_live_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
        )

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    result = await db.execute(
        select(APIKey).where(
            APIKey.key_hash == key_hash,
            APIKey.revoked_at.is_(None),
        )
    )
    api_key_record = result.scalar_one_or_none()

    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    return {
        "tenant_id": api_key_record.tenant_id,
        "user_id": api_key_record.user_id,
        "scoped_widget_ids": api_key_record.scoped_widget_ids,
        "rate_limit": api_key_record.rate_limit,
        "key_hash": key_hash,
    }
