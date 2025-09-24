"""FastAPI heartbeat. Lean core."""

from __future__ import annotations

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
from datetime import datetime, timezone
from typing import Any, Dict
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.Core.config import get_settings

from app.Auth.routes import router as auth_router
from app.features.profiles.endpoints import router as profiles_router  # Supabase-backed
from app.features.judge0.endpoints import public_router as judge0_public_router
from app.features.judge0.endpoints import protected_router as judge0_protected_router
from app.features.challenges.endpoints import router as challenges_router
from app.features.dashboard.endpoints import router as dashboard_router
from app.features.slides.endpoints import router as slides_router
from app.features.submissions.endpoints import router as submissions_router
from app.common.deps import get_current_user_from_cookie
from app.common.middleware import SessionManagementMiddleware
#just added(vonani)
from app.features.admin_panel.endpoints import router as admin_router
from app.features.module.endpoints import router as module_router
from app.features.semester.endpoints import router as semester_router
#end (vonani)

app = FastAPI(title="Recode Backend")

def _split_env_csv(name: str, default: str = ""):
    raw = os.getenv(name, default)
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]

_FRONTEND_ORIGINS = _split_env_csv(
    "ALLOW_ORIGINS",
    "http://localhost:5173,http://localhost:3000",
)

app.add_middleware(
	CORSMiddleware,
	allow_origins=_FRONTEND_ORIGINS,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# Add session management middleware for automatic token refresh
app.add_middleware(SessionManagementMiddleware, auto_refresh=True)

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

# Tiny request timing middleware for quick visibility
@app.middleware("http")
async def timing_middleware(request: Request, call_next):  # type: ignore[override]
    from time import perf_counter
    t0 = perf_counter()
    resp = await call_next(request)
    dt = int((perf_counter() - t0) * 1000)
    # Print once per request to spot 30s stalls
    print(f"{request.method} {request.url.path} {dt}ms {resp.status_code}")
    return resp
_START_TIME = datetime.now(timezone.utc)
_settings = get_settings()

# Plug the veins
app.include_router(auth_router)
# Protect all non-auth routers with cookie-based auth by default
protected_deps = [Depends(get_current_user_from_cookie)]
app.include_router(profiles_router, dependencies=protected_deps)
app.include_router(judge0_public_router)
app.include_router(judge0_protected_router, dependencies=protected_deps)
app.include_router(challenges_router, dependencies=protected_deps)
app.include_router(dashboard_router, dependencies=protected_deps)
app.include_router(slides_router, dependencies=protected_deps)
app.include_router(submissions_router, dependencies=protected_deps)



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
    """Vitals with lightweight DB ping."""
    now = datetime.now(timezone.utc)
    uptime_seconds = (now - _START_TIME).total_seconds()

    db_status: str = "unknown"
    db_latency_ms: float | None = None

    try:
        import time
        from app.DB.session import engine
        start = time.perf_counter()
        # AUTOCOMMIT isolation for a 1-row ping
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("SELECT 1"))
        db_latency_ms = round((time.perf_counter() - start) * 1000, 2)
        db_status = "ok"
    except SQLAlchemyError as e:
        db_status = f"error:{type(e).__name__}"
    except Exception as e:
        db_status = f"error:{type(e).__name__}"

    judge0_ready = bool(getattr(_settings, "judge0_api_url", None))
    route_count = len(app.routes)
    tags = sorted({t for r in app.routes for t in getattr(r, "tags", [])})

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "time_utc": now.isoformat(),
        "uptime_seconds": round(uptime_seconds, 2),
        "version": os.getenv("APP_VERSION", "dev"),
        "environment": "debug" if _settings.debug else "prod",
        "components": {
            "database": (
                {"status": db_status, "latency_ms": db_latency_ms}
                if db_status == "ok"
                else {"status": db_status}
            ),
            "judge0": "configured" if judge0_ready else "missing-config",
        },
        "counts": {
            "routes": route_count,
            "models": 0,
        },
        "tags": tags,
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
	real_icon_path = os.path.join(static_dir, "favicon.ico")
	if os.path.isfile(real_icon_path):
		return FileResponse(real_icon_path, media_type="image/x-icon")
	return PlainTextResponse("favicon.ico not found", status_code=404)


