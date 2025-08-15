# Import all models here so Alembic can discover them
from app.DB.base import Base

# Import all feature models - User first (referenced by other models)
from app.features.users.models import User  # Updated user model
from app.features.judge0.models import CodeSubmission, CodeResult
from app.features.slide_extraction.models import SlideExtraction

# This ensures all models are registered with SQLAlchemy
__all__ = ["Base", "User", "CodeSubmission", "CodeResult", "SlideExtraction"]
