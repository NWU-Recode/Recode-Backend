# Import all models here so Alembic can discover them
from app.DB.base import Base

# Import all feature models - User first (referenced by other models)
from app.features.profiles.models import Profile  
from app.features.judge0.models import CodeSubmission, CodeResult
from app.features.slide_extraction.models import SlideExtraction
from app.features.challenges.models import Challenge
from app.features.questions.models import Question
from app.features.submissions.models import QuestionAttempt, ChallengeAttempt

# This ensures all models are registered with SQLAlchemy
__all__ = [
	"Base",
	"Profile",
	"CodeSubmission",
	"CodeResult",
	"SlideExtraction",
	"Challenge",
	"Question",
	"QuestionAttempt",
	"ChallengeAttempt",
]
