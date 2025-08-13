# Import all models here so Alembic can discover them
from app.db.base import Base

# Import all feature models
from app.features.Judge0.models import CodeSubmission, CodeResult
from app.features.users.models import User  # user model

# This ensures all models are registered with SQLAlchemy
__all__ = ["Base", "User", "CodeSubmission", "CodeResult"]
