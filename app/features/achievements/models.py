from sqlalchemy import Column, String, Text, Integer, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.DB.base import Base

class Achievements(Base): #not sure if right
    __tablename__ = "achievements"
    achievements_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    elo_points = Column(Integer, default=0, nullable=False)
    badges = Column(JSON, nullable=True) #to show multiple diff badges or maybe just derive from userBadge
    title_id = Column(UUID(as_uuid=True), ForeignKey("titles.id", ondelete="SET NULL"), nullable=True)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# ELO
class UserElo(Base):
    __tablename__ = "user_elo"
    userElo_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    elo = Column(Integer, default=0, nullable=False)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

#Badges
class Badge(Base):
    __tablename__ = "badges"
    badge_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    badge_name = Column(String, nullable=False)
    badge_descrip = Column(Text, nullable=True)
    elo_threshold = Column(Integer, nullable=False) 
    special_actions = Column(JSON, nullable=True)   #not sure if correct but basically allows badge to be awarded after certain aftion (eg. submitted 5 challenges)

#composite - one user can have many badges & one badge can be obtained by many users
class UserBadge(Base):
    __tablename__ = "user_badges"
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    badge_id = Column(UUID(as_uuid=True), ForeignKey("badges.id", ondelete="CASCADE"), primary_key=True)
    date_earned = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

#Titles
class Title(Base):
    __tablename__ = "titles"
    title_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title_name = Column(String, nullable=False)
    elo_threshold = Column(Integer, nullable=False)  # minimum Elo required to unlock

class UserTitle(Base):
    __tablename__ = "user_titles"
    userTitle_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title_id = Column(UUID(as_uuid=True), ForeignKey("titles.id", ondelete="CASCADE"), nullable=False)
    date_awarded = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

