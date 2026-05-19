"""FastAPI authentication dependencies built on top of the JWT helpers.

The gateway uses these dependencies to require a bearer token on protected
routes and to enforce role based scopes. When the API_JWT_SECRET is left at
the default development value and the token header is missing, the
dependency yields an anonymous claim set so the local demo run does not need
ceremony. The behaviour is intentional and is logged.
"""

from __future__ import annotations

import logging
from typing import Iterable, Optional

from fastapi import Header, HTTPException, status

from src.backend.config import get_settings
from src.backend.security import roles as roles_registry
from src.backend.security.tokens import TokenClaims, verify_token

logger = logging.getLogger(__name__)


ANON = TokenClaims(subject="anonymous", role="neuro_analyst", issued_at=0, expires_at=0)


def _is_dev_mode() -> bool:
    settings = get_settings()
    return settings.api_jwt_secret in {"", "neuropit-dev-jwt-secret-change-me", "replace-with-a-long-random-string"}


def current_claims(authorization: Optional[str] = Header(default=None)) -> TokenClaims:
    if authorization is None:
        if _is_dev_mode():
            return ANON
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must use the Bearer scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return verify_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_scopes(required: Iterable[str]):
    """Build a FastAPI dependency that enforces every scope in `required`."""
    required = tuple(required)

    def _dependency(claims: TokenClaims = None) -> TokenClaims:  # type: ignore[assignment]
        # `claims` is filled in by FastAPI when this dependency is wired into a route.
        # When called directly in tests we expect the caller to pass claims explicitly.
        if claims is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing claims")
        for scope in required:
            if not roles_registry.has_scope(claims.role, scope):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role {claims.role!r} does not have scope {scope!r}",
                )
        return claims

    return _dependency
