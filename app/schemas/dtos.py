from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class TopicDTO(BaseModel):
    id: str
    week: int
    slug: str
    title: str
    created_at: str

class ChallengeKind(str, Enum):
    common = "common"
    ruby = "ruby"
    emerald = "emerald"
    diamond = "diamond"

class ChallengeStatus(str, Enum):
    draft = "draft"
    published = "published"

class ChallengeDTO(BaseModel):
    id: int
    topic_id: Optional[int]
    kind: ChallengeKind
    slug: str
    title: str
    status: ChallengeStatus
    created_at: str

class QuestionDifficulty(str, Enum):
    bronze = "bronze"
    silver = "silver"
    gold = "gold"
    ruby = "ruby"
    emerald = "emerald"
    diamond = "diamond"

class QuestionDTO(BaseModel):
    id: int
    challenge_id: int
    slug: str
    difficulty: QuestionDifficulty
    prompt_md: str
    starter_code: str
    reference_solution: str
    language: str
    time_limit_ms: int
    memory_kb: int
    created_at: str

class QuestionTestVisibility(str, Enum):
    public = "public"
    hidden = "hidden"

class QuestionTestDTO(BaseModel):
    id: int
    question_id: int
    input: str
    expected: str
    visibility: QuestionTestVisibility

class SubmissionStatus(str, Enum):
    pending = "pending"
    passed = "passed"
    failed = "failed"
    partial = "partial"

class SubmissionDTO(BaseModel):
    id: int
    user_id: int
    question_id: int
    status: SubmissionStatus
    tests_passed: int
    tests_total: int
    exec_ms: int
    mem_kb: int
    executes_used: int
    hints_used: int
    created_at: str

class BadgeType(str, Enum):
    bronze = "bronze"
    silver = "silver"
    gold = "gold"
    ruby = "ruby"
    emerald = "emerald"
    diamond = "diamond"

class BadgeAwardDTO(BaseModel):
    id: int
    user_id: int
    challenge_id: int
    badge_type: BadgeType
    created_at: str

class EloHistoryDTO(BaseModel):
    id: int
    user_id: int
    delta: int
    reason: str
    meta: Optional[dict]
    created_at: str

class UserRole(str, Enum):
    admin = "admin"
    lecturer = "lecturer"
    student = "student"

class UserDTO(BaseModel):
    id: int
    email: str
    role: UserRole
    display_name: str
    created_at: str
