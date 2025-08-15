"""ORM nexus. Auto-discover models."""

from __future__ import annotations

import importlib
import pkgutil
import logging
from pathlib import Path

from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base mold."""
    pass


def _discover_feature_models():
    """Sweep feature model modules."""
    import os
    if os.getenv("SKIP_MODEL_DISCOVERY", "false").lower() == "true":
        logger.info("Skip sweep (env flag).")
        return

    root = Path(__file__).resolve().parent.parent  # app/
    features_dir = root / "features"
    if not features_dir.is_dir():
        logger.warning("No features dir: %s", features_dir)
        return

    package_prefix = "app.features"
    discovered = 0
    for pkg in pkgutil.walk_packages([str(features_dir)], prefix=f"{package_prefix}."):
        if not pkg.name.endswith(".models"):
            continue
        try:
            importlib.import_module(pkg.name)
            discovered += 1
        except Exception as e:
            logger.error("Model import fail %s: %s", pkg.name, e)
    logger.debug("Discovered %d model modules", discovered)


def list_models():  # pragma: no cover
    """List model names."""
    try:
        return [cls.__name__ for cls in Base.registry._class_registry.values() if hasattr(cls, "__table__")]
    except Exception:
        return []


_discover_feature_models()

try:  # pragma: no cover
    logger.debug("Registered ORM models: %s", ", ".join(list_models()))
except Exception:
    pass

try:  # pragma: no cover
    from app.DB.session import SessionLocal  # type: ignore
except Exception:
    SessionLocal = None

__all__ = ["Base", "list_models", "SessionLocal"]
