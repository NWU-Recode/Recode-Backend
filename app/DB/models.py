# Import all models here so Alembic can discover them
from app.DB.base import Base

# Import all feature models - User first (referenced by other models)
from app.features.profiles.models import Profile  
from app.features.judge0.models import CodeSubmission, CodeResult
from app.features.topic_detections.slide_extraction.models import SlideExtraction
from app.features.challenges.models import Challenge
from app.features.achievements.badges.models import BadgeAward
from app.features.achievements.elo.models import EloHistory
from app.features.topic_detections.topics.models import Topic

# This ensures all models are registered with SQLAlchemy
__all__ = [
	"Base",
	"Profile",
	"CodeSubmission",
	"CodeResult",
	"SlideExtraction",
	"Challenge",
	"BadgeAward",
	"EloHistory",
    "Topic",
]
