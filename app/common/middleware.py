"""Middleware for session management and automatic token refresh."""

import logging
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.auth.service import (
    refresh_tokens_if_needed,
    set_auth_cookies,
    ACCESS_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    should_refresh_token
)

logger = logging.getLogger("session_middleware")


class SessionManagementMiddleware(BaseHTTPMiddleware):
    """Middleware that handles automatic token refresh and session management."""
    
    def __init__(self, app: ASGIApp, auto_refresh: bool = True):
        super().__init__(app)
        self.auto_refresh = auto_refresh
        # Paths that should not trigger token refresh
        self.excluded_paths = {
            "/auth/login",
            "/auth/register", 
            "/auth/refresh",
            "/auth/logout",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/healthz",
            "/",
            "/favicon.ico"
        }
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip processing for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Skip if auto refresh is disabled
        if not self.auto_refresh:
            return await call_next(request)
        
        # Get tokens from cookies
        access_token = request.cookies.get(ACCESS_COOKIE_NAME)
        refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
        
        # Only attempt refresh if we have both tokens
        if access_token and refresh_token and should_refresh_token(access_token):
            try:
                new_tokens = await refresh_tokens_if_needed(access_token, refresh_token)
                if new_tokens:
                    # Process the request normally
                    response = await call_next(request)
                    
                    # Set new cookies in the response
                    set_auth_cookies(response, new_tokens)
                    
                    logger.info(f"Auto-refreshed tokens for request to {request.url.path}")
                    return response
            except Exception as e:
                logger.warning(f"Failed to auto-refresh tokens: {e}")
                # Continue with original tokens
        
        # Process request normally
        return await call_next(request)


class SessionExtensionMiddleware(BaseHTTPMiddleware):
    """Middleware that determines when sessions should be extended."""
    
    def __init__(self, app: ASGIApp, extension_threshold: int = 1800):  # 30 minutes
        super().__init__(app)
        self.extension_threshold = extension_threshold
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Add session extension logic here if needed
        # For now, just pass through
        response = await call_next(request)
        
        # Could add logic to extend session based on user activity
        # E.g., if user has been active and token expires soon, extend it
        
        return response
