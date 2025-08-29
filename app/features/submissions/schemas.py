from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

class SubmissionCreate(BaseModel):
    source_code: str
    language_id: int
    stdin: Optional[str] = None
    expected_output: Optional[str] = None
    question_id: Optional[str] = None  # UUID string; optional join to question

class SubmissionRecord(BaseModel):
    id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    source_code: str
    language_id: int
    stdin: Optional[str] = None
    expected_output: Optional[str] = None
    judge0_token: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class SubmissionWithResults(BaseModel):
    submission: Dict[str, Any]
    results: List[Dict[str, Any]]

class SubmissionResultCreate(BaseModel):
    submission_id: str
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    compile_output: Optional[str] = None
    execution_time: Optional[str] = None
    memory_used: Optional[int] = None
    status_id: int
    status_description: str
    language_id: int

class LanguageStat(BaseModel):
    language_id: int
    submission_count: int

class SubmissionSchema(BaseModel):
    id: int
    user_id: int
    question_id: int
    status: str
    score: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
