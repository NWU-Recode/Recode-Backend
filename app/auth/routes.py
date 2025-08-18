from fastapi import APIRouter, Depends, Response, Request, status, HTTPException
from .schemas import RegisterRequest, LoginRequest, ProfileOut
from .service import (
    supabase_sign_up,
    supabase_password_grant,
    supabase_refresh,
    supabase_revoke,
    set_auth_cookies,
    clear_auth_cookies,
)
from .deps import get_current_user
from app.features.profiles.models import Profile  

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest):
    # Sign up with Supabase; email confirm may be required depending on project settings
    await supabase_sign_up(payload.email, payload.password, payload.full_name)
    return {"detail": "Registration successful. Check your email to confirm your account."}

@router.post("/login", status_code=status.HTTP_200_OK)
async def login(payload: LoginRequest, resp: Response):
    print(">>> ROUTE sees supabase_password_grant:",
      supabase_password_grant,
      "| module:", getattr(supabase_password_grant, "__module__", "?"),
      "| file:", getattr(getattr(supabase_password_grant, "__code__", None), "co_filename", "?"))

    """Authenticate user with JSON body (email, password)."""
    tokens = await supabase_password_grant(payload.email, payload.password)
    set_auth_cookies(resp, tokens)
    return {"detail": "Logged in"}

@router.post("/refresh", response_model=None)
async def refresh(request: Request, resp: Response, refresh_token: str | None = None):
    # Prefer cookie; allow body param for tooling.
    token = refresh_token or request.cookies.get("refresh_token")
    if not token:
        return {"detail": "No refresh token"}
    tokens = await supabase_refresh(token)
    set_auth_cookies(resp, tokens)
    return {"detail": "Refreshed"}

@router.post("/logout", response_model=None)
async def logout(resp: Response):
    # Optionally call services.supabase_revoke(refresh_cookie) if wired.
    clear_auth_cookies(resp)
    return {"detail": "Logged out"}

@router.get("/me", response_model=ProfileOut)
async def me(user: Profile = Depends(get_current_user)):
    return ProfileOut(
        id=str(user.id),
        email=user.email,
        role=user.role,
        full_name=getattr(user, "full_name", None),
        avatar_url=getattr(user, "avatar_url", None),
    )
