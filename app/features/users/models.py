from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.base import Base


class User(Base):
	__tablename__ = "users"

	id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	email = Column(String(255), unique=True, nullable=False, index=True)
	full_name = Column(String(255), nullable=True)
	hashed_password = Column(String(255), nullable=True)  # nullable if using external auth provider
	role = Column(String(50), nullable=False, server_default="user", index=True)  # roles: student, lecturer, admin, etc.
	is_active = Column(Boolean, nullable=False, server_default="true")
	is_superuser = Column(Boolean, nullable=False, server_default="false")
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

	def __repr__(self) -> str:  # pragma: no cover - repr utility
		return f"<User id={self.id} email={self.email} role={self.role}>"
