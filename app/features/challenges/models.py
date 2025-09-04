"""SQLAlchemy model kept minimal; generation mainly uses Supabase client inserts.

If ORM usage is reintroduced later, extend accordingly.
"""

from sqlalchemy import Column, String, Text, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.DB.base import Base

class Challenge(Base):
    __tablename__ = "challenges"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    lecturer_creator = Column(Integer, nullable=True)
    kind = Column(String(50), nullable=True)
    slug = Column(String(255), nullable=True)
    status = Column(String(50), nullable=True)
    topic_id = Column(Integer, nullable=True)
