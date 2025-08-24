from sqlalchemy import Column, String, ForeignKey, Index, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.db.base import Base

class Module(Base):
    __tablename__ = "modules"

    module_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module_code = Column(String, unique=True, nullable=False, index=True)
    module_name = Column(String, nullable=False)
    lecturer_id = Column(UUID(as_uuid=True), ForeignKey("lecturers.id", ondelete="CASCADE"), nullable=False)
    semester_id = Column(UUID(as_uuid=True), ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lecturer = relationship("Lecturer", back_populates="modules")
    semester = relationship("Semester", back_populates="modules")

    def __repr__(self):
        return f"<Module(module_id={self.module_id}, module_code='{self.module_code}', module_name='{self.module_name}')>"

# Optionally, add indexes for performance
Index("ix_module_code", Module.module_code)
