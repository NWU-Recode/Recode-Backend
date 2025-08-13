from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class CodeSubmissionCreate(BaseModel):
    """Schema for creating a new code submission"""
    source_code: str
    language_id: int
    stdin: Optional[str] = None
    expected_output: Optional[str] = None

class CodeSubmissionResponse(BaseModel):
    """Schema for code submission response"""
    id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    source_code: str
    language_id: int
    stdin: Optional[str] = None
    expected_output: Optional[str] = None
    judge0_token: Optional[str] = None
    status: str = "pending"
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class Judge0SubmissionRequest(BaseModel):
    """Schema for Judge0 API submission request"""
    source_code: str
    language_id: int
    stdin: Optional[str] = None
    expected_output: Optional[str] = None
    cpu_time_limit: Optional[float] = None
    cpu_extra_time: Optional[float] = None
    wall_time_limit: Optional[float] = None
    memory_limit: Optional[int] = None
    stack_limit: Optional[int] = None
    max_processes_and_or_threads: Optional[int] = None
    enable_per_process_and_thread_time_limit: Optional[bool] = None
    enable_per_process_and_thread_memory_limit: Optional[bool] = None
    max_file_size: Optional[int] = None
    number_of_runs: Optional[int] = None
    redirect_stderr_to_stdout: Optional[bool] = None
    callback_url: Optional[str] = None
    additional_files: Optional[str] = None
    command_line_arguments: Optional[str] = None

class Judge0SubmissionResponse(BaseModel):
    """Schema for Judge0 API submission response"""
    token: str

class Judge0ExecutionResult(BaseModel):
    """Schema for Judge0 execution result.

    Note: Some Judge0 deployments (or specific field filters) may omit the
    nested "language" object. We make it optional to avoid validation errors
    and downstream code will fallback gracefully when absent.
    """
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    compile_output: Optional[str] = None
    message: Optional[str] = None
    time: Optional[str] = None
    memory: Optional[int] = None
    status: dict  # Contains id and description (always expected)
    language: Optional[dict] = None  # May be missing on some responses

class CodeExecutionResult(BaseModel):
    """Final result schema for our API"""
    submission_id: Optional[UUID] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    compile_output: Optional[str] = None
    execution_time: Optional[str] = None
    memory_used: Optional[int] = None
    status_id: int
    status_description: str
    language_id: int
    success: bool
    created_at: Optional[datetime] = None

class LanguageInfo(BaseModel):
    """Schema for programming language information"""
    id: int
    name: str

class Judge0Status(BaseModel):
    """Schema for Judge0 status information"""
    id: int
    description: str
