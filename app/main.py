"""FastAPI Heartbeat. Lean."""

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
from app.features.slidesDownload.endpoint import router as slides_download_router  # Your slides endpoint
from app.features.slides.endpoints import router as slides_router  # Legacy slides
from app.features.profiles.endpoints import router as profiles_router  # Supabase-backed
from app.features.judge0.endpoints import public_router as judge0_public_router
from app.features.judge0.endpoints import protected_router as judge0_protected_router
from app.features.challenges.endpoints import router as challenges_router, questions_router as challenge_questions_router
from app.features.dashboard.endpoints import router as dashboard_router
from app.features.submissions.endpoints import router as submissions_router
from app.features.analytics.endpoints import router as analytics_router
from app.common.deps import get_current_user
from app.common.middleware import SessionManagementMiddleware
# vonani routers
from app.features.admin.endpoints import router as admin_router
from app.features.students.endpoints import router as student_router
from app.features.semester.endpoints import router as semester_router


app = FastAPI(title="Recode Backend")

def _split_env_csv(name: str, default: str = ""):
    raw = os.getenv(name, default)
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]

_FRONTEND_ORIGINS = _split_env_csv(
    "ALLOW_ORIGINS",
    "https://recode-frontend.vercel.app,http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000",
)


# CORS middleware
import re

# compile origin regex once for reuse
_CORS_ORIGIN_REGEX = re.compile(r"https?://(.+\.)?vercel\.app|https?://(localhost|127\.0\.0\.1)(:\d+)?", re.I)

print("DEBUG: CORS allowed origins:", _FRONTEND_ORIGINS)
print("DEBUG: CORS origin regex:", _CORS_ORIGIN_REGEX.pattern)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_FRONTEND_ORIGINS,
    allow_origin_regex=_CORS_ORIGIN_REGEX.pattern,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Fallback middleware: ensure CORS headers are present on responses when the origin
# matches the allowed origins or regex. This is defensive: some serverless/proxy
# setups may alter headers; this middleware sets them if missing.
@app.middleware("http")
async def _ensure_cors_headers(request: Request, call_next):
    origin = request.headers.get("origin")
    response = await call_next(request)
    try:
        allowed = False
        if origin:
            if origin in _FRONTEND_ORIGINS:
                allowed = True
            elif _CORS_ORIGIN_REGEX.match(origin):
                allowed = True
        if allowed:
            # Respect any existing header values set by CORSMiddleware but ensure they exist
            response.headers.setdefault("Access-Control-Allow-Origin", origin)
            response.headers.setdefault("Access-Control-Allow-Credentials", "true")
            # Vary by Origin to prevent caching issues at proxies/CDNs
            vary = response.headers.get("Vary")
            if vary:
                if "Origin" not in [v.strip() for v in vary.split(",")]:
                    response.headers["Vary"] = vary + ", Origin"
            else:
                response.headers["Vary"] = "Origin"
    except Exception:
        # Don't break request flow on CORS helper failure
        pass
    return response

# Session middleware
app.add_middleware(SessionManagementMiddleware, auto_refresh=True)

# Middleware: request id
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
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

# Middleware: timing
@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    from time import perf_counter
    t0 = perf_counter()
    resp = await call_next(request)
    dt = int((perf_counter() - t0) * 1000)
    print(f"{request.method} {request.url.path} {dt}ms {resp.status_code}")
    return resp

_START_TIME = datetime.now(timezone.utc)
_settings = get_settings()

# Routers
app.include_router(auth_router)
protected_deps = [Depends(get_current_user)]
app.include_router(profiles_router, dependencies=protected_deps)
app.include_router(judge0_public_router)
app.include_router(judge0_protected_router, dependencies=protected_deps)
app.include_router(challenges_router, dependencies=protected_deps)
app.include_router(challenge_questions_router, dependencies=protected_deps)
app.include_router(dashboard_router, dependencies=protected_deps)
app.include_router(slides_router, dependencies=protected_deps)           # Legacy slides
app.include_router(slides_download_router, dependencies=protected_deps)  # Your new slides endpoint
app.include_router(submissions_router, dependencies=protected_deps)
app.include_router(analytics_router)
# vonani
app.include_router(admin_router)
app.include_router(semester_router)
app.include_router(student_router)

# Static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Root & health
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
    now = datetime.now(timezone.utc)
    uptime_seconds = (now - _START_TIME).total_seconds()
    db_status: str = "unknown"
    db_latency_ms: float | None = None
    try:
        import time
        from app.DB.session import engine
        start = time.perf_counter()
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


# Catch-all to serve SPA index for unknown GET routes (useful for client-side routing / SPA reloads)
@app.get("/{full_path:path}", include_in_schema=False)
async def spa_catch_all(request: Request, full_path: str):
    # Only serve index.html for GET requests and when static dir exists
    try:
        if request.method != "GET":
            return PlainTextResponse("Not Found", status_code=404)
        index_file = os.path.join(static_dir, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file, media_type="text/html")
    except Exception:
        pass
    return PlainTextResponse("Not Found", status_code=404)
