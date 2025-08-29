from sqlalchemy import Column, Integer, String, DateTime, JSON
from app.DB.base import Base
from datetime import datetime

class EloHistory(Base):
    __tablename__ = 'elo_history'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    delta = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        {'extend_existing': True},
    )
