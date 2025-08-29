from sqlalchemy import Column, String, Text, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.DB.base import Base

import enum

class ChallengeTier(enum.Enum):
    plain = "plain"      # weekly bundle (bronze/silver/gold questions)
    ruby = "ruby"        # released after every 2 plain challenges
    emerald = "emerald"  # released alongside every 2nd ruby (i.e., after 4 plain)
    diamond = "diamond"  # final capstone

class ChallengeKind(enum.Enum):
    common = "common"
    ruby = "ruby"
    platinum = "platinum"
    diamond = "diamond"

class ChallengeStatus(enum.Enum):
    draft = "draft"
    published = "published"

class Challenge(Base):
    __tablename__ = "challenges"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    lecturer_creator = Column(Integer, ForeignKey("profiles.id"), nullable=False)  # Changed to Integer to match profiles.id
    linked_module = Column(String(255), nullable=True)
    duration = Column(Integer, nullable=True)  # in minutes
    tier = Column(Enum(ChallengeTier), nullable=False, default=ChallengeTier.plain, index=True)
    mark = Column(Integer, nullable=True)  # optional weighting or override
    badge_rule = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    topic_id = Column(Integer, ForeignKey("topic.id"), nullable=True)
    kind = Column(Enum(ChallengeKind), nullable=False)
    slug = Column(String, unique=True, index=True)
    status = Column(Enum(ChallengeStatus), nullable=False)

    def __repr__(self):
        return f"<Challenge(id={self.id}, title={self.title}, tier={self.tier})>"
