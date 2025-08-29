# Import all models here so Alembic can discover them
from app.DB.base import Base

# Import all feature models - User first (referenced by other models)
from app.features.profiles.models import Profile  
from app.features.judge0.models import CodeSubmission, CodeResult
from app.features.questions.slide_extraction.models import SlideExtraction
from app.features.challenges.models import Challenge
from app.features.questions.models import Question, QuestionTest
from app.features.submissions.models import Submission
from app.features.badges.models import BadgeAward
from app.features.elo.models import EloHistory

# This ensures all models are registered with SQLAlchemy
__all__ = [
	"Base",
	"Profile",
	"CodeSubmission",
	"CodeResult",
	"SlideExtraction",
	"Challenge",
	"Question",
	"QuestionTest",
	"Submission",
	"BadgeAward",
	"EloHistory",
]
