"""Middleware for managing session cookies and refreshing tokens."""

import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.Auth.service import (
    refresh_tokens_if_needed,
    set_auth_cookies,
    ACCESS_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    should_refresh_token
)

logger = logging.getLogger("session_middleware")


class SessionManagementMiddleware(BaseHTTPMiddleware):
    """Refresh authentication cookies when access tokens are close to expiring."""
    
    def __init__(self, app: ASGIApp, auto_refresh: bool = True):
        super().__init__(app)
        self.auto_refresh = auto_refresh
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
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        if not self.auto_refresh:
            return await call_next(request)

        access_token = request.cookies.get(ACCESS_COOKIE_NAME)
        refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)

        if access_token and refresh_token and should_refresh_token(access_token):
            try:
                new_tokens = await refresh_tokens_if_needed(access_token, refresh_token)
                if new_tokens:
                    response = await call_next(request)

                    set_auth_cookies(response, new_tokens)

                    logger.info(f"Auto-refreshed tokens for request to {request.url.path}")
                    return response
            except Exception as e:
                logger.warning(f"Failed to auto-refresh tokens: {e}")

        return await call_next(request)
