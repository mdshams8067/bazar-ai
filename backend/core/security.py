"""
core/security.py — Verifies Supabase-issued auth tokens and resolves the
current user's profile.

Signup/login themselves happen entirely on the frontend, directly against
Supabase's Auth API (supabase-js) — this backend never sees a password and
issues no tokens of its own. Its only job here is: given a bearer token the
frontend already obtained from Supabase, confirm it's genuine and figure out
who it belongs to.

Supabase signs tokens with ES256 (asymmetric) for this project, not a
shared secret — verification uses their public JWKS endpoint, so there is
no secret value for this backend to protect at all. The JWKS is small and
rotates rarely, so it's cached in-process rather than fetched per request.
"""
from __future__ import annotations

import time
import uuid

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import SUPABASE_URL
from core.database import get_db
from models.profile import Profile

_JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
_JWKS_TTL_SECONDS = 3600  # keys rotate rarely; an hourly refetch is plenty
_jwks_cache: dict = {"keys": [], "fetched_at": 0.0}

bearer_scheme = HTTPBearer()


async def _get_jwks(*, force_refresh: bool = False) -> list[dict]:
    stale = time.monotonic() - _jwks_cache["fetched_at"] > _JWKS_TTL_SECONDS
    if force_refresh or not _jwks_cache["keys"] or stale:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_JWKS_URL)
        resp.raise_for_status()
        _jwks_cache["keys"] = resp.json()["keys"]
        _jwks_cache["fetched_at"] = time.monotonic()
    return _jwks_cache["keys"]


async def verify_supabase_token(token: str) -> dict:
    """Verifies a Supabase-issued JWT against their public signing key.
    Raises jose.JWTError on any failure (bad signature, expired, wrong
    audience, unknown key)."""
    kid = jwt.get_unverified_header(token).get("kid")

    keys = await _get_jwks()
    key = next((k for k in keys if k.get("kid") == kid), None)
    if key is None:
        # Could be a genuinely rotated key we haven't seen yet — refetch
        # once before giving up, rather than caching a false negative.
        keys = await _get_jwks(force_refresh=True)
        key = next((k for k in keys if k.get("kid") == kid), None)
    if key is None:
        raise JWTError(f"No matching JWKS key for kid={kid!r}")

    return jwt.decode(token, key, algorithms=["ES256"], audience="authenticated")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Profile:
    """FastAPI dependency: verifies the bearer token against Supabase, then
    loads (or lazily creates) this user's app-specific profile row —
    Supabase owns the account itself (email, password, id); this table only
    holds the extra fields our app needs (name, phone) that Supabase's own
    schema doesn't have a place for.

    `profile.email` is set here from the token's claims, not from a stored
    column — Supabase is the source of truth for email, and duplicating it
    into our own table would just be one more place it could go stale."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = await verify_supabase_token(credentials.credentials)
    except JWTError:
        raise credentials_exception from None

    # JWT claims are always JSON-safe scalars — "sub" is a string even
    # though it's a UUID's text form, never a native UUID object. SQLAlchemy's
    # Uuid column type needs the real thing to bind/compare correctly.
    raw_user_id = payload.get("sub")
    if raw_user_id is None:
        raise credentials_exception
    try:
        user_id = uuid.UUID(raw_user_id)
    except ValueError:
        raise credentials_exception from None

    profile = await db.get(Profile, user_id)
    if profile is None:
        metadata = payload.get("user_metadata") or {}
        email = payload.get("email") or ""
        profile = Profile(
            id=user_id,
            name=metadata.get("name") or email.split("@")[0] or "Shopper",
            phone=metadata.get("phone"),
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    profile.email = payload.get("email") or ""
    return profile
