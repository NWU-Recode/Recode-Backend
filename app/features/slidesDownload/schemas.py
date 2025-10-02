# app/features/slidesDownload/schemas.py

from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from typing import List

class SlideMetadata(BaseModel):
    id: int
    filename: str
    week_number: Optional[int]
    module_code: Optional[str]
    topic_id: Optional[UUID]
    has_file: bool

    class Config:
        orm_mode = True

class SignedURLResponse(BaseModel):
    slide_id: int
    filename: str
    signed_url: str
    expires_in: int

