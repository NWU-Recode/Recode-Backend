"""Minimal models placeholder copied from module models (if present)."""

from sqlalchemy import Column, String, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.DB.base import Base




class Module(Base):
    __tablename__ = 'modules'
    id = Column(PGUUID(as_uuid=True), primary_key=True)
    code = Column(String)
    name = Column(String)
    description = Column(String)
    lecturer_id = Column(Integer)
    is_active = Column(Boolean, default=True)
