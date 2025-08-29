from fastapi import APIRouter, HTTPException
from app.features.topics.schemas import TopicCreate, TopicResponse
from app.features.topics.service import create_from_slides

router = APIRouter()

@router.post("/topics/", response_model=TopicResponse)
async def create_topic(topic: TopicCreate):
    try:
        return await create_from_slides(None, slides_url=topic.slides_url, week=topic.week)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
