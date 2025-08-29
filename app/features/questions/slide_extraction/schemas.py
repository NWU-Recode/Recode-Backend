"""Pydantic schemas for the slide extraction feature."""

from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel, ConfigDict


class SlideExtractionBase(BaseModel):
    filename: str
    slides: Dict[int, List[str]]


class SlideExtractionCreate(SlideExtractionBase):
    """Schema for creating a new slide extraction record."""

    pass


class SlideExtractionRead(SlideExtractionBase):
    """Schema returned to API consumers."""

    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
