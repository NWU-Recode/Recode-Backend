"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

from app.auth.routes import router as auth_router
from app.features.users.endpoints import router as users_router
from app.features.Judge0.endpoints import router as judge0_router

app = FastAPI(title="Recode Backend")

# Register routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(judge0_router)