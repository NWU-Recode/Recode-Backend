"""app package initializer.

Expose the FastAPI application as ``app`` lazily so scripts that only
need configuration can import without pulling all dependencies."""

from __future__ import annotations

__all__ = ["app"]


def __getattr__(name: str):
    if name == "app":
        from .main import app as fastapi_app
        return fastapi_app
    raise AttributeError(f"module {__name__} has no attribute {name!r}")
