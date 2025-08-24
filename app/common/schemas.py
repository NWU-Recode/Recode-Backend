from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

# LANGUAGE SUPPORT SCHEMAS

class LanguageInfo(BaseModel):
    """Programming language information"""
    language_id: int
    name: str
    version: Optional[str]
    compile_cmd: Optional[str]
    run_cmd: Optional[str]
    source_file: Optional[str]
    is_archived: bool = False

class SupportedLanguagesResponse(BaseModel):
    """List of supported programming languages"""
    languages: List[LanguageInfo]
    total_count: int

# ERROR AND STATUS SCHEMAS

class ErrorResponse(BaseModel):
    """Standard error response"""
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime

class StatusResponse(BaseModel):
    """Generic status response"""
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None

class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    services: Dict[str, str]  # service_name -> status
    version: str

#  SCHEMAS

class UserAnalytics(BaseModel):
    """User performance analytics"""
    user_id: str
    total_challenges: int
    completed_challenges: int
    average_score: float
    total_time_spent_minutes: int
    preferred_language: Optional[str]
    improvement_trend: str  # "improving", "stable", "declining"
    strengths: List[str]  # topic areas
    weaknesses: List[str]  # topic areas

class ChallengeAnalytics(BaseModel):
    """Challenge performance analytics"""
    challenge_id: str
    total_attempts: int
    completion_rate: float
    average_score: float
    average_time_minutes: float
    difficult_questions: List[str]  # question IDs with low success rate
    language_distribution: Dict[str, int]

class SystemAnalytics(BaseModel):
    """System-wide analytics"""
    total_users: int
    active_users_today: int
    total_submissions: int
    submissions_today: int
    average_response_time_ms: float
    error_rate: float
    popular_languages: List[Dict[str, Any]]