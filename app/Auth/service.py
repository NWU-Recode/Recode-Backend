import httpx
import time
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from fastapi import HTTPException, Response, status
from .schemas import TokenPair
from app.Core.config import get_settings

settings = get_settings()
if not settings.supabase_url:
    raise RuntimeError("SUPABASE_URL not configured")

AUTH_BASE = f"{settings.supabase_url}/auth/v1"

ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"
COOKIE_DOMAIN = settings.cookie_domain
COOKIE_SECURE = settings.cookie_secure
SAMESITE = settings.cookie_samesite

# Enhanced token management constants
ACCESS_TTL = 60 * 60  # 1 hour; Supabase default
REFRESH_TTL = 30 * 24 * 60 * 60  # 30 days; typical refresh token lifetime
REFRESH_THRESHOLD = 5 * 60  # 5 minutes; refresh when access token expires within this time
REFRESH_PATH = "/auth/refresh"
FORM_CT = "application/x-www-form-urlencoded"

# Dev token persistence (gitignored)
DEV_TOKEN_FILE = Path(".") / ".dev_refresh_token.json"

def _select_key(admin: bool = False) -> str:
    key = settings.supabase_service_role_key if admin and settings.supabase_service_role_key else settings.supabase_anon_key
    if not key:
        raise HTTPException(500, "Supabase keys not configured")
    return key

def _base_headers(admin: bool = False) -> dict:
    key = _select_key(admin)
    return {"apikey": key, "Authorization": f"Bearer {key}"}

def _json_headers(admin: bool = False) -> dict:
    # Dedicated JSON headers to avoid leaking Content-Type to form calls
    return {**_base_headers(admin), "Content-Type": "application/json"}

def _form_headers(admin: bool = False) -> dict:
    # Dedicated form headers
    return {**_base_headers(admin), "Content-Type": "application/x-www-form-urlencoded"}

async def supabase_sign_up(email: str, password: str, full_name: str | None = None, extra_meta: dict | None = None) -> dict:
    payload = {"email": email.lower(), "password": password}
    meta: dict[str, object] = extra_meta.copy() if extra_meta else {}
    if full_name and "full_name" not in meta:
        meta["full_name"] = full_name
    if meta:
        payload["data"] = meta  # becomes raw_user_meta_data
    timeout = httpx.Timeout(connect=3, read=5, write=5, pool=5)
    limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        r = await client.post(
            f"{AUTH_BASE}/signup",
            headers=_json_headers(),
            json=payload,
        )
        if r.status_code not in (200, 201):
            # Extract best available error message
            msg = None
            try:
                data = r.json()
                if isinstance(data, dict):
                    msg = (
                        data.get("msg")
                        or data.get("message")
                        or data.get("error_description")
                        or data.get("error")
                    )
            except Exception:
                pass
            raw = r.text.strip()
            detail = msg or raw or f"HTTP {r.status_code}"
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Registration failed: {detail}")
        try:
            return r.json()
        except ValueError:
            return {"detail": "registered"}

async def supabase_password_grant(email: str, password: str) -> TokenPair:
    payload = {"email": email.strip().lower(), "password": password}
    url = f"{AUTH_BASE}/token?grant_type=password"
    timeout = httpx.Timeout(connect=3, read=5, write=5, pool=5)
    limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        r = await client.post(url, headers=_json_headers(), json=payload)

    if r.status_code != 200:
        detail = "Invalid credentials"
        try:
            if r.headers.get("content-type", "").startswith("application/json"):
                data = r.json()
            else:
                data = {}
            if isinstance(data, dict):
                code = (data.get("error_code") or data.get("code") or "").lower()
                msg = (
                    data.get("msg")
                    or data.get("message")
                    or data.get("error_description")
                    or data.get("error")
                )
                if msg:
                    detail = msg
                if "email_not_confirmed" in code or (
                    isinstance(msg, str)
                    and "confirm" in msg.lower()
                    and "email" in msg.lower()
                ):
                    detail = "Email not confirmed"
        except Exception:
            pass
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail)

    body = r.json()
    return TokenPair(
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
        expires_in=body.get("expires_in"),
    )


async def supabase_refresh(refresh_token: str) -> TokenPair:
    """Refresh tokens using Supabase. 
    
    IMPORTANT: Supabase refresh tokens are single-use and get rotated!
    The returned TokenPair will contain a NEW refresh token.
    """
    # Track token usage for dev
    increment_token_usage_dev()
    
    payload = {"refresh_token": refresh_token}
    url = f"{AUTH_BASE}/token?grant_type=refresh_token"
    timeout = httpx.Timeout(connect=3, read=5, write=5, pool=5)
    limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        r = await client.post(url, headers=_json_headers(), json=payload)

    if r.status_code != 200:
        detail = "Invalid refresh token"
        try:
            if r.headers.get("content-type", "").startswith("application/json"):
                data = r.json()
            else:
                data = {}
            if isinstance(data, dict):
                msg = (
                    data.get("msg")
                    or data.get("message")
                    or data.get("error_description")
                    or data.get("error")
                )
                if msg:
                    detail = msg
        except Exception:
            pass
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail)

    body = r.json()
    new_tokens = TokenPair(
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],  # This is a NEW refresh token!
        expires_in=body.get("expires_in"),
    )
    
    # Save the NEW refresh token for dev use (since old one is now invalid)
    save_refresh_token_dev(new_tokens.refresh_token, "refresh_rotation")
    
    return new_tokens


async def supabase_revoke(refresh_token: str) -> None:
    # GoTrue doesn't always expose revoke; fallback is to rotate and delete cookie.
    # If you enable gotrue's signout endpoint, call it here. Otherwise, best-effort.
    return None

def save_refresh_token_dev(refresh_token: str, note: str = "login") -> None:
    """Save refresh token for dev use only (guarded by settings.debug).
    
    Args:
        refresh_token: The new refresh token to save
        note: Context about when this token was saved (login, refresh, etc.)
    """
    if not getattr(settings, "debug", False):
        return
    try:
        payload = {
            "refresh_token": refresh_token, 
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "note": note,
            "usage_count": 0  # Track how many times this token has been used
        }
        
        # Try to preserve usage count from previous token
        if DEV_TOKEN_FILE.exists():
            try:
                old_data = json.loads(DEV_TOKEN_FILE.read_text())
                if old_data.get("refresh_token") == refresh_token:
                    payload["usage_count"] = old_data.get("usage_count", 0)
            except Exception:
                pass
        
        DEV_TOKEN_FILE.write_text(json.dumps(payload, indent=2))
        print(f"🔑 Dev: Saved refresh token ({note}) to {DEV_TOKEN_FILE}")
    except Exception as e:
        print(f"⚠️  Dev: Failed to save refresh token: {e}")


def load_refresh_token_dev() -> str | None:
    """Load the latest refresh token for dev use."""
    if not getattr(settings, "debug", False) or not DEV_TOKEN_FILE.exists():
        return None
    try:
        data = json.loads(DEV_TOKEN_FILE.read_text())
        token = data.get("refresh_token")
        if token:
            print(f"🔑 Dev: Loaded refresh token from {DEV_TOKEN_FILE}")
            print(f"    Saved: {data.get('saved_at', 'unknown')}")
            print(f"    Note: {data.get('note', 'no note')}")
            print(f"    Usage count: {data.get('usage_count', 0)}")
        return token
    except Exception as e:
        print(f"⚠️  Dev: Failed to load refresh token: {e}")
        return None


def increment_token_usage_dev() -> None:
    """Increment usage counter for dev token tracking."""
    if not getattr(settings, "debug", False) or not DEV_TOKEN_FILE.exists():
        return
    try:
        data = json.loads(DEV_TOKEN_FILE.read_text())
        data["usage_count"] = data.get("usage_count", 0) + 1
        data["last_used"] = datetime.now(timezone.utc).isoformat()
        DEV_TOKEN_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass

def get_token_expiry(token: str) -> datetime | None:
    """Extract expiration time from JWT token without verification."""
    try:
        from jose import jwt
        claims = jwt.get_unverified_claims(token)
        exp = claims.get("exp")
        if exp:
            return datetime.fromtimestamp(exp)
    except Exception:
        pass
    return None

def should_refresh_token(access_token: str) -> bool:
    """Check if access token should be refreshed based on expiration time."""
    expiry = get_token_expiry(access_token)
    if not expiry:
        return False
    
    # Refresh if token expires within threshold
    threshold_time = datetime.utcnow() + timedelta(seconds=REFRESH_THRESHOLD)
    return expiry <= threshold_time

def calculate_cookie_max_age(token: str, default_ttl: int) -> int:
    """Calculate appropriate max_age for cookie based on token expiration."""
    expiry = get_token_expiry(token)
    if not expiry:
        return default_ttl
    
    # Calculate seconds until expiration
    remaining = (expiry - datetime.utcnow()).total_seconds()
    return max(0, int(remaining))

def set_auth_cookies(resp: Response, tokens: TokenPair) -> None:
    """Set secure HTTP-only cookies with appropriate expiration times."""
    # Calculate dynamic max_age based on actual token expiration
    access_max_age = calculate_cookie_max_age(tokens.access_token, ACCESS_TTL)
    
    # Access token for all routes
    resp.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=tokens.access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=SAMESITE.lower(),  # type: ignore
        domain=COOKIE_DOMAIN,
        max_age=access_max_age,
        path="/",
    )
    
    # Refresh token only sent to /auth/refresh with longer expiration
    resp.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=tokens.refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=SAMESITE.lower(),  # type: ignore
        domain=COOKIE_DOMAIN,
        max_age=REFRESH_TTL,
        path=REFRESH_PATH,
    )
    
    # Save refresh token for dev use (this handles token rotation)
    save_refresh_token_dev(tokens.refresh_token, "set_cookies")

async def refresh_tokens_if_needed(access_token: str, refresh_token: str) -> TokenPair | None:
    """Automatically refresh access token if it's close to expiring."""
    if not should_refresh_token(access_token):
        return None
    
    try:
        return await supabase_refresh(refresh_token)
    except HTTPException:
        # Refresh token might be expired or invalid
        return None

def clear_auth_cookies(resp: Response) -> None:
    """Clear authentication cookies."""
    for name, path in ((ACCESS_COOKIE_NAME, "/"), (REFRESH_COOKIE_NAME, REFRESH_PATH)):
        resp.delete_cookie(
            key=name,
            domain=COOKIE_DOMAIN,
            path=path,
        )
