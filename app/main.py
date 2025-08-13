#FastAPI application entry point.

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import base64  # (can be removed if no future inline assets)
from datetime import datetime, timezone
from typing import Any, Dict
from sqlalchemy import text

from app.db.session import SessionLocal
from app.db.base import list_models
from app.core.config import get_settings

from app.auth.routes import router as auth_router
from app.features.users.endpoints import router as users_router
from app.features.Judge0.endpoints import router as judge0_router
from app.features.slide_extraction.endpoints import router as slide_extraction_router

app = FastAPI(title="Recode Backend")
_START_TIME = datetime.now(timezone.utc)
_settings = get_settings()

#Register routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(judge0_router)
app.include_router(slide_extraction_router)

# Mount static directory (place your favicon.ico inside ./static)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
	app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", tags=["meta"], summary="API Root")
async def root():
	return {
		"name": "Recode Backend",
		"status": "ok",
		"docs": "/docs",
		"redoc": "/redoc",
		"health": "/healthz"
	}


@app.get("/healthz", tags=["meta"], summary="Liveness / readiness probe")
async def healthz() -> Dict[str, Any]:
	"""Return extended health & readiness diagnostics.

	Includes simple DB connectivity check, configuration presence flags, uptime, and
	basic app metadata. Avoids heavy queries to stay fast.
	"""
	now = datetime.now(timezone.utc)
	uptime_seconds = (now - _START_TIME).total_seconds()

	db_status: str
	try:
		with SessionLocal() as session:  # type: ignore
			session.execute(text("SELECT 1"))
		db_status = "ok"
	except Exception as e:  # pragma: no cover
		db_status = f"error: {e.__class__.__name__}"[:120]

	# Judge0 configuration readiness
	judge0_ready = bool(getattr(_settings, "judge0_api_url", None))

	# Gather route stats
	route_count = len(app.routes)
	tags = sorted({t for r in app.routes for t in getattr(r, 'tags', [])})

	return {
		"status": "ok" if db_status == "ok" else "degraded",
		"time_utc": now.isoformat(),
		"uptime_seconds": round(uptime_seconds, 2),
		"version": os.getenv("APP_VERSION", "dev"),
		"environment": "debug" if _settings.debug else "prod",
		"components": {
			"database": db_status,
			"judge0": "configured" if judge0_ready else "missing-config",
		},
		"counts": {
			"routes": route_count,
			"models": len(list_models()),
		},
		"tags": tags,
	}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
	# Prefer real file if user added one: app/static/favicon.ico
	real_icon_path = os.path.join(static_dir, "favicon.ico")
	if os.path.isfile(real_icon_path):
		return FileResponse(real_icon_path, media_type="image/x-icon")
	# No favicon present
	return PlainTextResponse("favicon.ico not found", status_code=404)


