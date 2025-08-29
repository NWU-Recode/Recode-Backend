from sqlalchemy.orm import Session
from app.features.topics.models import Topic

class TopicRepository:
    @staticmethod
    def get_by_slug(db: Session, slug: str) -> Topic:
        return db.query(Topic).filter(Topic.slug == slug).first()

    @staticmethod
    def create(db: Session, week: int, slug: str, title: str) -> Topic:
        topic = Topic(week=week, slug=slug, title=title)
        db.add(topic)
        db.commit()
        db.refresh(topic)
        return topic
