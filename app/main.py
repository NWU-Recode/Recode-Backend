"""FastAPI heartbeat. Lean core."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
from datetime import datetime, timezone
from typing import Any, Dict
# Removed local DB imports - using Supabase only

from app.Core.config import get_settings

from app.Auth.routes import router as auth_router
from app.features.users.endpoints import router as users_router  # Supabase-backed
from app.features.judge0.endpoints import router as judge0_router
from app.features.questions.endpoints import router as questions_router
from app.features.challenges.endpoints import router as challenges_router
from app.features.slide_extraction.endpoints import router as slide_extraction_router
from app.features.dashboard.endpoints import router as dashboard_router
from app.features.lecturer.endpoints import router as lecturer_router

app = FastAPI(title="Recode Backend")

# Middleware: capture / propagate / generate X-Request-Id consistently
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):  # type: ignore[override]
	import uuid, logging
	incoming = request.headers.get("X-Request-Id") or request.headers.get("X-Request-ID")
	req_id = incoming or str(uuid.uuid4())
	request.state.request_id = req_id
	logger = logging.getLogger("request")
	logger.info("request.start", extra={"request_id": req_id, "path": request.url.path, "method": request.method})
	response = await call_next(request)
	response.headers["X-Request-Id"] = req_id
	logger.info("request.end", extra={"request_id": req_id, "path": request.url.path, "status_code": response.status_code})
	return response
_START_TIME = datetime.now(timezone.utc)
_settings = get_settings()

# Plug the veins
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(judge0_router)
app.include_router(slide_extraction_router)
app.include_router(questions_router)
app.include_router(challenges_router)
app.include_router(dashboard_router)
app.include_router(lecturer_router)


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
	"""Vitals. Quick, clean, fearless."""
	now = datetime.now(timezone.utc)
	uptime_seconds = (now - _START_TIME).total_seconds()

	db_status = "ok"  # Removed DB check
	
	judge0_ready = bool(getattr(_settings, "judge0_api_url", None))

	route_count = len(app.routes)
	tags = sorted({t for r in app.routes for t in getattr(r, 'tags', [])})

	return {
			"status": "ok",  # Simplified status check
		"time_utc": now.isoformat(),
		"uptime_seconds": round(uptime_seconds, 2),
		"version": os.getenv("APP_VERSION", "dev"),
		"environment": "debug" if _settings.debug else "prod",
		"components": {
				"database": "ok",  # Removed DB status
			"judge0": "configured" if judge0_ready else "missing-config",
		},
		"counts": {
			"routes": route_count,
				"models": 0,  # Removed models count
		},
		"tags": tags,
	}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
	real_icon_path = os.path.join(static_dir, "favicon.ico")
	if os.path.isfile(real_icon_path):
		return FileResponse(real_icon_path, media_type="image/x-icon")
	return PlainTextResponse("favicon.ico not found", status_code=404)


