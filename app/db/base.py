"""Central SQLAlchemy Declarative Base and dynamic model discovery.

Provides:
 - Base: Declarative base for all ORM models
 - Automatic import of every app.features.*.models module so models register
 - list_models(): helper to inspect currently loaded ORM classes
 - Safe for Alembic autogenerate (env.py should import this module)
"""

from __future__ import annotations

import importlib
import pkgutil
import logging
from pathlib import Path

from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    # Future common mixins or naming conventions can be placed here.
    pass


def _discover_feature_models():
    """
    Dynamically import every models.py inside app.features.* so that
    their declarative classes register with Base.metadata.

    Skipped if env var SKIP_MODEL_DISCOVERY=true (for some fast tests).
    """
    import os
    if os.getenv("SKIP_MODEL_DISCOVERY", "false").lower() == "true":
        logger.info("Skipping dynamic model discovery (env override).")
        return

    root = Path(__file__).resolve().parent.parent  # app/
    features_dir = root / "features"
    if not features_dir.is_dir():
        logger.warning("Features directory not found: %s", features_dir)
        return

    package_prefix = "app.features"
    discovered = 0
    for pkg in pkgutil.walk_packages([str(features_dir)], prefix=f"{package_prefix}."):
        # We only want modules explicitly named *.models
        if not pkg.name.endswith(".models"):
            continue
        try:
            importlib.import_module(pkg.name)
            discovered += 1
        except Exception as e:
            logger.error("Failed importing models module %s: %s", pkg.name, e)
    logger.debug("Discovered %d model modules", discovered)


def list_models():  # pragma: no cover - utility helper
    """Return list of ORM model class names currently registered on Base.metadata."""
    try:
        return [cls.__name__ for cls in Base.registry._class_registry.values() if hasattr(cls, "__table__")]
    except Exception:
        return []


# Run discovery at import time (Alembic & app startup)
_discover_feature_models()

# Debug log of currently registered models (non-fatal if it fails)
try:  # pragma: no cover
    logger.debug("Registered ORM models: %s", ", ".join(list_models()))
except Exception:
    pass

try:  # optional backward compatibility re-export
    from app.db.session import SessionLocal  # type: ignore
except Exception:  # pragma: no cover
    SessionLocal = None  # placeholder if session not yet configured

__all__ = ["Base", "list_models", "SessionLocal"]
