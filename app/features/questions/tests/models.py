from sqlalchemy import Column, Integer, String, Enum, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.DB.base import Base
import enum

class QuestionTestVisibility(enum.Enum):
    public = "public"
    hidden = "hidden"

class QuestionTest(Base):
    __tablename__ = 'question_test'
    __table_args__ = (
        Index('ix_question_test_question_id', 'question_id'),
    )

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("question.id"), nullable=False)
    input = Column(String, nullable=False)
    expected = Column(String, nullable=False)
    visibility = Column(Enum(QuestionTestVisibility), nullable=False, index=True)

    question = relationship("Question", back_populates="tests")
