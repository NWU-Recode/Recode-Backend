"""app package initializer.

Expose the FastAPI instance as `app` so process managers that import
`app:app` (e.g., `gunicorn app:app`) can locate it.
"""

from .main import app

__all__ = ["app"]

