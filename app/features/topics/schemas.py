from pydantic import BaseModel

class TopicCreate(BaseModel):
    slides_url: str
    week: int

class TopicResponse(BaseModel):
    id: int
    week: int
    slug: str
    title: str
    created_at: str
