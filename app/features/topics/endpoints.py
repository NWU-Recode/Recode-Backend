from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.features.topics.schemas import TopicCreate, TopicResponse
from app.features.topics.service import TopicService

router = APIRouter()

@router.post("/topics/", response_model=TopicResponse)
def create_topic(topic: TopicCreate, db: Session = Depends(get_db)):
    try:
        return TopicService.create_from_slides(db, slides_url=topic.slides_url, week=topic.week)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
