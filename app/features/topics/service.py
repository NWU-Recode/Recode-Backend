from app.features.topics.repository import TopicRepository
from app.features.topics.schemas import TopicSchema  # type: ignore
from app.features.questions.schemas import QuestionSchema  # type: ignore

class TopicService:
    @staticmethod
    def create_from_slides(db, slides_url: str, week: int):
        """Create a topic from a slides URL using a simple heuristic.

        Derives a slug from the filename and persists via repository.
        """
        import re
        base = slides_url.strip().split("/")[-1] or "Topic"
        base = re.sub(r"\.[A-Za-z0-9]+$", "", base)
        primary_topic = base.replace("_", " ").replace("-", " ").title() or "Topic"
        slug = f"w{week:02d}-{re.sub(r'[^a-z0-9]+', '-', base.lower()).strip('-') or 'topic'}"
        return TopicRepository.create(db, week=week, slug=slug, title=primary_topic)

class TopicsService:
    def __init__(self, db):
        self.db = db

    def create_topic(self, topic_data: TopicSchema):
        # Logic to create a topic
        pass

    def get_topic(self, topic_id: int):
        # Logic to retrieve a topic
        pass

    def update_topic(self, topic_id: int, topic_data: TopicSchema):
        # Logic to update a topic
        pass

    def delete_topic(self, topic_id: int):
        # Logic to delete a topic
        pass

    def create_from_slides(self, slide_data: list):
        """
        Create topics and questions from slide data.
        :param slide_data: List of slide content.
        """
        topics = []
        for slide in slide_data:
            # Extract topic title and questions from slide
            topic_title = slide.get("title")
            questions = slide.get("questions", [])

            # Create topic
            topic = TopicSchema(name=topic_title, description="Generated from slides")  # type: ignore
            # Persist via repository when models are available

            # Create questions for the topic
            for question_data in questions:
                question = QuestionSchema(  # type: ignore
                    challenge_id=topic.id,
                    text=question_data.get("text"),
                    difficulty=question_data.get("difficulty"),
                    tier=question_data.get("tier"),
                )
                # Persist via repository when models are available

            topics.append(topic)
        return topics
