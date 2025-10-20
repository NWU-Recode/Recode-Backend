# C:\Repos\Recode-Backend\app\main.py
"""FastAPI Heartbeat. Lean."""

from __future__ import annotations

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles

import os
import re
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.Core.config import get_settings
from app.Auth.routes import router as auth_router
from app.features.slidesDownload.endpoints import router as slides_download_router
from app.features.notifications.endpoints import router as notifications_router
from app.features.slides.endpoints import router as slides_router
from app.features.profiles.endpoints import router as profiles_router
from app.features.judge0.endpoints import public_router as judge0_public_router
from app.features.judge0.endpoints import protected_router as judge0_protected_router
from app.features.challenges.endpoints import router as challenges_router, questions_router as challenge_questions_router
from app.features.dashboard.endpoints import router as dashboard_router
from app.features.submissions.endpoints import router as submissions_router, router_mixed as submissions_router_mixed
from app.features.analytics.endpoints import router as analytics_router
from app.common.deps import get_current_user
from app.common.middleware import SessionManagementMiddleware
from app.features.admin.endpoints import router as admin_router
from app.features.students.endpoints import router as student_router
from app.features.semester.endpoints import router as semester_router
from routes.debug import router as debug_router
from app.api.notifications_schedule import router as notifications_schedule_router
from app.jobs.notification_scheduler import start_notification_scheduler

app = FastAPI(title="Recode Backend")
_settings = get_settings()
_START_TIME = datetime.now(timezone.utc)


# ------------------------
# CORS Setup
# ------------------------
def _split_env_csv(name: str, default: str = ""):
    raw = os.getenv(name, default)
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


_FRONTEND_ORIGINS = _split_env_csv(
    "ALLOW_ORIGINS",
    "https://recode-frontend.vercel.app,http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000",
)

_CORS_ORIGIN_REGEX = re.compile(r"https?://(.+\.)?vercel\.app|https?://(localhost|127\.0\.0\.1)(:\d+)?", re.I)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_FRONTEND_ORIGINS,
    allow_origin_regex=_CORS_ORIGIN_REGEX.pattern,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
            response.headers.setdefault("Access-Control-Allow-Origin", origin)
            response.headers.setdefault("Access-Control-Allow-Credentials", "true")
            vary = response.headers.get("Vary")
            if vary:
                if "Origin" not in [v.strip() for v in vary.split(",")]:
                    response.headers["Vary"] = vary + ", Origin"
            else:
                response.headers["Vary"] = "Origin"
    except Exception:
        pass
    return response


# ------------------------
# Custom Middlewares
# ------------------------
app.add_middleware(SessionManagementMiddleware, auto_refresh=True)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    import uuid

    incoming = request.headers.get("X-Request-Id") or request.headers.get("X-Request-ID")
    req_id = incoming or str(uuid.uuid4())
    request.state.request_id = req_id
    logger = logging.getLogger("request")
    logger.info("request.start", extra={"request_id": req_id, "path": request.url.path, "method": request.method})
    response = await call_next(request)
    response.headers["X-Request-Id"] = req_id
    logger.info("request.end", extra={"request_id": req_id, "path": request.url.path, "status_code": response.status_code})
    return response


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    from time import perf_counter

    t0 = perf_counter()
    resp = await call_next(request)
    dt = int((perf_counter() - t0) * 1000)
    print(f"{request.method} {request.url.path} {dt}ms {resp.status_code}")
    return resp


# ------------------------
# Routers
# ------------------------
protected_deps = [Depends(get_current_user)]

app.include_router(auth_router)
app.include_router(profiles_router, dependencies=protected_deps)
app.include_router(judge0_public_router)
app.include_router(judge0_protected_router, dependencies=protected_deps)
app.include_router(challenges_router, dependencies=protected_deps)
app.include_router(challenge_questions_router, dependencies=protected_deps)
app.include_router(dashboard_router, dependencies=protected_deps)
app.include_router(slides_router, dependencies=protected_deps)
app.include_router(slides_download_router, dependencies=protected_deps)
app.include_router(notifications_router, dependencies=protected_deps)
app.include_router(notifications_schedule_router, dependencies=protected_deps)
app.include_router(submissions_router, dependencies=protected_deps)
app.include_router(submissions_router_mixed, dependencies=protected_deps)
app.include_router(analytics_router)
app.include_router(admin_router)
app.include_router(semester_router)
app.include_router(student_router)
app.include_router(debug_router, prefix="/debug", tags=["debug"])


# ------------------------
# Static files
# ------------------------
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ------------------------
# Meta endpoints
# ------------------------
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
    import time
    from app.DB.session import engine

    now = datetime.now(timezone.utc)
    uptime_seconds = (now - _START_TIME).total_seconds()
    db_status: str = "unknown"
    db_latency_ms: float | None = None

    try:
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
        "counts": {"routes": route_count, "models": 0},
        "tags": tags,
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    real_icon_path = os.path.join(static_dir, "favicon.ico")
    if os.path.isfile(real_icon_path):
        return FileResponse(real_icon_path, media_type="image/x-icon")
    return PlainTextResponse("favicon.ico not found", status_code=404)


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_catch_all(request: Request, full_path: str):
    try:
        if request.method != "GET":
            return PlainTextResponse("Not Found", status_code=404)
        index_file = os.path.join(static_dir, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file, media_type="text/html")
    except Exception:
        pass
    return PlainTextResponse("Not Found", status_code=404)


# ------------------------
# Background Tasks
# ------------------------
@app.on_event("startup")
async def _start_background_tasks():
    import logging

    logger = logging.getLogger("publisher")

    # Publisher loop
    async def _publisher_loop():
        from app.features.admin.repository import ModuleRepository
        from app.features.challenges.repository import challenge_repository
        from app.demo.timekeeper import apply_demo_offset_to_semester_start
        from datetime import datetime, timezone
        import os

        while True:
            try:
                client = await __import__("app.DB.supabase", fromlist=["get_supabase"]).get_supabase()
                all_modules_resp = await client.table("modules").select("code, semester_id").execute()
                modules = all_modules_resp.data or []

                for mod in modules:
                    try:
                        module_code = mod.get("code")
                        semester_id = mod.get("semester_id")
                        window = await ModuleRepository.get_semester_window_for_module_code(module_code)
                        start_date = window.get("start_date")
                        try:
                            start_date = apply_demo_offset_to_semester_start(start_date, module_code)
                        except Exception:
                            pass

                        today = datetime.now(timezone.utc).date()
                        if isinstance(start_date, str):
                            start_date = datetime.fromisoformat(start_date).date()
                        delta_days = (today - start_date).days
                        week = max(1, min(12, (delta_days // 7) + 1))

                        pub_fn = getattr(challenge_repository, "publish_for_week", None)
                        if callable(pub_fn):
                            await pub_fn(week, module_code=module_code, semester_id=semester_id)

                        enforce_fn = getattr(challenge_repository, "enforce_active_limit", None)
                        if callable(enforce_fn):
                            await enforce_fn(module_code=module_code, semester_id=semester_id, keep_count=2)
                    except Exception as e:
                        logger.exception("Module loop error: %s", e)

                await asyncio.sleep(int(os.getenv("PUBLISHER_INTERVAL_SEC", "60")))
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Publisher loop failed")
                await asyncio.sleep(60)

    try:
        asyncio.create_task(_publisher_loop())
    except Exception:
        logging.getLogger("publisher").exception("Failed to start background publisher")

    try:
        asyncio.create_task(start_notification_scheduler())
    except Exception:
        logging.getLogger("notification_scheduler").exception(
            "Failed to start background notification scheduler"
        )
