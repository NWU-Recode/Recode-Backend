from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Integer, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy import Enum
from sqlalchemy.orm import relationship
import uuid
import enum
from datetime import datetime

from app.DB.base import Base

# relationship definitions for User must be attributes on the mapped class.
# They will be defined on the User class below.

class UserRole(enum.Enum):
    admin = "admin"
    lecturer = "lecturer"
    student = "student"

class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, nullable=False)
    supabase_id = Column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        index=True,
    )
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    bio = Column(Text, nullable=True)
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")
    is_superuser = Column(Boolean, nullable=False, server_default="false")
    email_verified = Column(Boolean, nullable=False, server_default="false")
    last_sign_in = Column(DateTime(timezone=True), nullable=True)
    user_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        CheckConstraint('id >= 10000000 AND id <= 99999999', name='check_student_number_8_digits'),
    )

    def __repr__(self) -> str:
        return f"<Profile id={self.id} supabase_id={self.supabase_id} email={self.email} role={self.role}>"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    display_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # relationships
    # Modules a user (student) is enrolled in. student_module table
    # links users.id to modules.id
    #modules = relationship("Module", secondary="student_module", back_populates="students")(vonani)

    # Note: LecturerProfile relationship was removed because no mapped
    # LecturerProfile class exists in the codebase. If you later add a
    # LecturerProfile model, reintroduce this relationship (after both
    # classes are defined) or configure it dynamically to avoid import-time
    # mapper resolution errors.
