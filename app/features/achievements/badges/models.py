from sqlalchemy import Column, Integer, String, Enum, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from app.DB.base import Base
from datetime import datetime
import enum

class BadgeType(enum.Enum):
    bronze = "bronze"
    silver = "silver"
    gold = "gold"
    ruby = "ruby"
    emerald = "emerald"
    diamond = "diamond"

class BadgeAward(Base):
    __tablename__ = 'badge_award'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenge.id"))
    badge_type = Column(Enum(BadgeType), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    challenge = relationship("Challenge", back_populates="badges")

    __table_args__ = (
        Index('idx_user_challenge', 'user_id', 'challenge_id', unique=True),
    )
