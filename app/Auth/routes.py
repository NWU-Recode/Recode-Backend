from fastapi import APIRouter, Depends, Response, Request, status, HTTPException
from .schemas import RegisterRequest, LoginRequest, ProfileOut
from .service import (
    supabase_sign_up,
    supabase_password_grant,
    supabase_refresh,
    supabase_revoke,
    set_auth_cookies,
    clear_auth_cookies,
    load_refresh_token_dev,
)
from .deps import get_current_user
from app.features.profiles.models import Profile  

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest):
    await supabase_sign_up(payload.email, payload.password, payload.full_name, payload.student_number)
    return {"detail": "Registration successful. Check your email to confirm your account."}

@router.post("/login", status_code=status.HTTP_200_OK)
async def login(payload: LoginRequest, resp: Response):
    """Authenticate user with JSON body (email, password)."""
    tokens = await supabase_password_grant(payload.email, payload.password)
    set_auth_cookies(resp, tokens)  # Set HttpOnly cookies for access and refresh tokens
    return {
        "detail": "Logged in",
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token  # Include refresh token in response
    }

@router.post("/refresh", response_model=None)
async def refresh(request: Request, resp: Response, refresh_token: str | None = None):
    # Prefer cookie; allow body param for tooling.
    token = refresh_token or request.cookies.get("refresh_token")
    if not token:
        return {"detail": "No refresh token"}
    tokens = await supabase_refresh(token)
    set_auth_cookies(resp, tokens)  # Update cookies with new tokens
    return {
        "detail": "Refreshed",
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token  # Include refresh token in response
    }

@router.post("/logout", response_model=None)
async def logout(resp: Response):
    # Optionally call services.supabase_revoke(refresh_cookie) if wired.
    clear_auth_cookies(resp)  # Clear HttpOnly cookies for access and refresh tokens
    return {"detail": "Logged out"}


@router.post("/dev/refresh-from-file", response_model=None, include_in_schema=False)
async def dev_refresh_from_file(resp: Response):
    """DEV ONLY: Refresh using token from .dev_refresh_token.json file.
    
    This endpoint is for development testing when your access token expires.
    It loads the latest refresh token from the dev file and uses it to get new tokens.
    """
    from app.Core.config import get_settings
    settings = get_settings()
    
    if not getattr(settings, "debug", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    
    refresh_token = load_refresh_token_dev()
    if not refresh_token:
        return {"error": "No dev refresh token found", "hint": "Login first to generate tokens"}
    
    try:
        tokens = await supabase_refresh(refresh_token)
        set_auth_cookies(resp, tokens)
        return {
            "detail": "Refreshed from dev file", 
            "access_token": tokens.access_token,
            "hint": "New refresh token saved to dev file automatically"
        }
    except Exception as e:
        return {"error": f"Refresh failed: {str(e)}", "hint": "Login again to get fresh tokens"}

@router.get("/me", response_model=ProfileOut)
async def me(user: Profile = Depends(get_current_user)):
    return ProfileOut(
        id=str(user.id),
        email=user.email,
        role=user.role,
        full_name=getattr(user, "full_name", None),
        avatar_url=getattr(user, "avatar_url", None),
    )
