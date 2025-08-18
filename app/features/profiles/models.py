from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from app.DB.base import Base

class Profile(Base):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Supabase auth user id (UUID) with FK to auth.users for cascade cleanup
    supabase_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    bio = Column(Text, nullable=True)
    role = Column(String(50), nullable=False, server_default="student", index=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    is_superuser = Column(Boolean, nullable=False, server_default="false")
    email_verified = Column(Boolean, nullable=False, server_default="false")
    last_sign_in = Column(DateTime(timezone=True), nullable=True)
    user_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Profile id={self.id} email={self.email} role={self.role}>"
