# admin_panel/models.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.DB.base import Base

class Enrolment(Base):
    __tablename__ = "enrolments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    semester_id = Column(UUID(as_uuid=True), ForeignKey("semesters.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    module_id = Column(UUID(as_uuid=True), ForeignKey("modules.id"), nullable=False)
    enrolled_on = Column(DateTime, server_default=func.now(), nullable=False)
    status = Column(String, nullable=False, default="enrolled")
