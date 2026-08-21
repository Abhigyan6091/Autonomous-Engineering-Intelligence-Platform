"""
JWT-based authentication utilities.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token extractor
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a plain-text password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(UTC), "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """
    FastAPI dependency: extract and validate the current user from JWT.
    Returns the user ID string.

    For development mode (DEBUG=True), returns a default user ID if no token provided.
    """
    if settings.DEBUG and credentials is None:
        return "dev-user"

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )
        return user_id
    except JWTError as exc:
        logger.warning("JWT validation failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def redact_secrets(content: str) -> str:
    """
    Remove secrets, API keys, and passwords from content before
    passing to the LLM. This is a critical security control.
    """
    import re

    patterns = [
        # API keys
        (r'(?i)(api[_\-]?key|apikey)\s*[=:]\s*[\'"]?[\w\-]{16,}', r'\1=[REDACTED]'),
        # Passwords
        (r'(?i)(password|passwd|pwd|secret)\s*[=:]\s*[\'"]?.{6,}[\'"]?', r'\1=[REDACTED]'),
        # Tokens
        (r'(?i)(token|auth[_\-]?token|access[_\-]?token)\s*[=:]\s*[\'"]?[\w\-]{16,}', r'\1=[REDACTED]'),
        # AWS keys
        (r'(?i)(aws[_\-]?access[_\-]?key[_\-]?id)\s*[=:]\s*[A-Z0-9]{20}', r'\1=[REDACTED]'),
        (r'(?i)(aws[_\-]?secret[_\-]?access[_\-]?key)\s*[=:]\s*[A-Za-z0-9/+]{40}', r'\1=[REDACTED]'),
        # Private keys
        (r'-----BEGIN [A-Z ]+ KEY-----[\s\S]+?-----END [A-Z ]+ KEY-----', '[REDACTED_KEY_BLOCK]'),
        # DB connection strings with passwords
        (r'(postgres|postgresql|mysql|mongodb)://([^:]+):([^@]+)@', r'\1://\2:[REDACTED]@'),
        # Redis with password
        (r'redis://:([^@]+)@', r'redis://:[REDACTED]@'),
    ]

    redacted = content
    for pattern, replacement in patterns:
        redacted = re.sub(pattern, replacement, redacted, flags=re.MULTILINE)
    return redacted
