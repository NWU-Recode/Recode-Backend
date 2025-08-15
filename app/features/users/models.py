from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from app.DB.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supabase_id = Column(String(255), unique=True, nullable=False, index=True)  # Supabase auth user ID
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
    user_metadata = Column(JSONB, nullable=True)  # Store preferences
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
