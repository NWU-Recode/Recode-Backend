from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from jose import JWTError
from typing import Any, TypedDict
from app.DB.session import get_db
from app.features.profiles.models import Profile
from .jwks_cache import JWKSCache
from app.Core.config import get_settings
import os, time

settings = get_settings()
# Ensure no trailing slash duplication when constructing certs URL
_base_supabase = settings.supabase_url.rstrip('/') if settings.supabase_url else ""
JWKS_URL = f"{_base_supabase}/auth/v1/certs" if _base_supabase else ""
JWKS = JWKSCache(JWKS_URL, ttl_seconds=3600)
ACCESS_COOKIE_NAME = "access_token"

# Lightweight in-memory cache to avoid hitting DB on every /auth/me.
_CACHE_TTL = int(os.getenv("AUTH_ME_CACHE_SECONDS", "60"))  # seconds
_PROFILE_CACHE: dict[str, tuple[dict[str, Any], float]] = {}

def _cache_get(user_id: str) -> dict[str, Any] | None:
    now = time.time()
    entry = _PROFILE_CACHE.get(user_id)
    if not entry:
        return None
    data, exp = entry
    if now < exp:
        return data
    # expired
    _PROFILE_CACHE.pop(user_id, None)
    return None

def _cache_set(user_id: str, data: dict[str, Any]) -> None:
    _PROFILE_CACHE[user_id] = (data, time.time() + _CACHE_TTL)

async def _extract_bearer_or_cookie(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.removeprefix("Bearer ").strip()
    cookie = request.cookies.get(ACCESS_COOKIE_NAME)
    return cookie

class Claims(TypedDict, total=False):
    sub: str
    email: str
    user_metadata: dict[str, Any]


async def get_current_claims(request: Request) -> Claims:
    token = await _extract_bearer_or_cookie(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")
    try:
        claims = await JWKS.verify(token)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    except Exception as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token verification failed: {e}")
    return claims

async def get_current_user(
    claims: dict = Depends(get_current_claims),
    db: Session = Depends(get_db),
) -> Profile:
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing sub")
    # Cache path: return minimal profile fields if available
    cached = _cache_get(user_id)
    if cached:
        class _Lite:
            pass
        obj = _Lite()
        # Required attributes used downstream
        obj.id = cached.get("id")
        obj.email = cached.get("email")
        obj.role = cached.get("role")
        obj.full_name = cached.get("full_name")
        obj.avatar_url = cached.get("avatar_url")
        return obj  # type: ignore[return-value]
    # Profile PK (id) is not the Supabase auth user id; we stored that in supabase_id
    # so look it up by supabase_id column.
    profile = db.execute(select(Profile).where(Profile.supabase_id == user_id)).scalar_one_or_none()
    if not profile:
        # If the trigger somehow lagged, you can decide to insert a minimal row here.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    # Update cache with minimal fields
    try:
        _cache_set(user_id, {
            "id": getattr(profile, "id", None),
            "email": getattr(profile, "email", None),
            "role": getattr(profile, "role", None),
            "full_name": getattr(profile, "full_name", None),
            "avatar_url": getattr(profile, "avatar_url", None),
        })
    except Exception:
        pass
    return profile

def require_roles(*allowed: str):
    async def _dep(user: Profile = Depends(get_current_user)) -> Profile:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user
    return _dep
