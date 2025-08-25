from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from jose import JWTError
from typing import Any, TypedDict
from app.db.session import get_db
from app.features.profiles.models import Profile
from .jwks_cache import JWKSCache
from app.core.config import get_settings

settings = get_settings()
# Ensure no trailing slash duplication when constructing certs URL
_base_supabase = settings.supabase_url.rstrip('/') if settings.supabase_url else ""
JWKS_URL = f"{_base_supabase}/auth/v1/certs" if _base_supabase else ""
JWKS = JWKSCache(JWKS_URL, ttl_seconds=3600)
ACCESS_COOKIE_NAME = "access_token"

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
    # Profile PK (id) is not the Supabase auth user id; we stored that in supabase_id
    # so look it up by supabase_id column.
    profile = db.execute(select(Profile).where(Profile.supabase_id == user_id)).scalar_one_or_none()
    if not profile:
        # If the trigger somehow lagged, you can decide to insert a minimal row here.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return profile

def require_roles(*allowed: str):
    async def _dep(user: Profile = Depends(get_current_user)) -> Profile:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user
    return _dep
