"""Pydantic models for user resources."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel


class User(BaseModel):
    """Represents a user stored in the database."""

    id: UUID
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2
