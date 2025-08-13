"""Pydantic models for user resources."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class User(BaseModel):
    """Represents a user stored in the database."""

    id: UUID
    email: str
    created_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2 compatibility
