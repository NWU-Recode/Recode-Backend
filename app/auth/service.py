import httpx
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

ACCESS_TTL = 60 * 60  # ~1h; Supabase default
REFRESH_PATH = "/auth/refresh"
FORM_CT = "application/x-www-form-urlencoded"

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

async def supabase_sign_up(email: str, password: str, full_name: str | None = None) -> dict:
    payload = {"email": email.lower(), "password": password}
    if full_name:
        payload["data"] = {"full_name": full_name}  # appears as user_metadata
    async with httpx.AsyncClient(timeout=15) as client:
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
    async with httpx.AsyncClient(timeout=15) as client:
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
    payload = {"refresh_token": refresh_token}
    url = f"{AUTH_BASE}/token?grant_type=refresh_token"
    async with httpx.AsyncClient(timeout=15) as client:
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
    return TokenPair(
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
        expires_in=body.get("expires_in"),
    )


async def supabase_revoke(refresh_token: str) -> None:
    # GoTrue doesn't always expose revoke; fallback is to rotate and delete cookie.
    # If you enable gotrue's signout endpoint, call it here. Otherwise, best-effort.
    return None

def set_auth_cookies(resp: Response, tokens: TokenPair) -> None:
    # Access token for all routes
    resp.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=tokens.access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=SAMESITE,
        domain=COOKIE_DOMAIN,
        max_age=ACCESS_TTL,
        path="/",
    )
    # Refresh token only sent to /auth/refresh
    resp.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=tokens.refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=SAMESITE,
        domain=COOKIE_DOMAIN,
        path=REFRESH_PATH,
    )

def clear_auth_cookies(resp: Response) -> None:
    for name, path in ((ACCESS_COOKIE_NAME, "/"), (REFRESH_COOKIE_NAME, REFRESH_PATH)):
        resp.delete_cookie(
            key=name,
            domain=COOKIE_DOMAIN,
            path=path,
        )
