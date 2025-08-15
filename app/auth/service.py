"""Authentication service functions."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Optional

from app.Integrations.supabase_session import supabase_session, get_client
from app.Auth.schemas import LoginRequest, TokenResponse, RegisterRequest, PasswordChangeRequest
from app.features.users.service import create_user_in_db, get_user_by_supabase_id, update_user_last_signin
from app.features.users.schemas import UserCreate

security = HTTPBearer()


async def register_user(data: RegisterRequest) -> TokenResponse:
    """Register a new user with Supabase Auth and store in local DB."""
    client = await get_client()
    
    try:
        # Create user in Supabase Auth
        auth_response = await client.auth.sign_up({
            "email": data.email,
            "password": data.password,
            "options": {
                "data": {
                    "full_name": data.full_name,
                    "role": "student"  # Default role for new registrations
                }
            }
        })
        
        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user account"
            )
        
        # Create user in local database
        user_data = UserCreate(
            email=data.email,
            password="",  # IMPORTANT:Not stored locally
            full_name=data.full_name
        )
        
        db_user = await create_user_in_db(
            supabase_id=auth_response.user.id,
            user_data=user_data
        )
        
        # Sign in the user to get access token
        signin_response = await client.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })
        
        if not signin_response.session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to sign in after registration"
            )
        
        return TokenResponse(
            access_token=signin_response.session.access_token,
            user_id=str(db_user.id),
            email=db_user.email,
            role=db_user.role
        )
        
    except Exception as exc:
        if "User already registered" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(exc)}"
        ) from exc


async def authenticate_user(data: LoginRequest) -> TokenResponse:
    """Authenticate user and return token with user info."""
    client = await get_client()
    
    try:
        result = await client.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })
        
        if not result.session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authentication failed"
            )
        
        # Get user from local DB to get role and other info
        db_user = await get_user_by_supabase_id(result.user.id)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found in database"
            )
        
        # Update last sign in
        await update_user_last_signin(db_user.id)
        
        return TokenResponse(
            access_token=result.session.access_token,
            user_id=str(db_user.id),
            email=db_user.email,
            role=db_user.role
        )
        
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication failed"
        ) from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Validate the bearer token and return the associated user."""
    async with supabase_session() as client:
        try:
            user = await client.auth.get_user(credentials.credentials)
            if not user.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials"
                )
            
            # Get user from local DB for complete user info
            db_user = await get_user_by_supabase_id(user.user.id)
            if not db_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found in database"
                )
            
            return db_user
            
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            ) from exc


async def change_password(
    data: PasswordChangeRequest,
    current_user,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Change user password."""
    client = await get_client()
    
    try:
        # Verify current password
        await client.auth.sign_in_with_password({
            "email": current_user.email,
            "password": data.current_password
        })
        
        # Update password
        await client.auth.update_user({
            "password": data.new_password
        })
        
        return {"message": "Password updated successfully"}
        
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to change password"
        ) from exc


async def logout_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Logout user by invalidating the token."""
    # Note: Supabase handles token invalidation automatically
    # This endpoint is mainly for frontend consistency
    return {"message": "Logged out successfully"}


def require_role(required_role: str):
    """Dependency to check if user has required role."""
    def role_checker(current_user = Depends(get_current_user)):
        if current_user.role != required_role and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {required_role}"
            )
        return current_user
    return role_checker


def require_admin():
    """Dependency to check if user is admin."""
    def admin_checker(current_user = Depends(get_current_user)):
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Admin role required."
            )
        return current_user
    return admin_checker
