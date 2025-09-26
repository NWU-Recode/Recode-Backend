from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CodeSubmissionCreate(BaseModel):
    source_code: str
    language_id: int
    stdin: Optional[str] = None
    expected_output: Optional[str] = None


class QuickCodeSubmission(BaseModel):
    source_code: str
    language_id: int
    stdin: Optional[str] = None


class CodeSubmissionResponse(BaseModel):
    id: Optional[int] = None
    user_id: Optional[int] = None
    source_code: str
    language_id: Optional[int] = None
    stdin: Optional[str] = None
    expected_output: Optional[str] = None
    token: Optional[str] = None
    status_id: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    time: Optional[float] = None
    memory: Optional[int] = None
    compile_output: Optional[str] = None
    message: Optional[str] = None
    exit_code: Optional[int] = None
    exit_signal: Optional[int] = None
    wall_time: Optional[float] = None
    number_of_runs: Optional[int] = None
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class Judge0SubmissionRequest(BaseModel):
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
    token: str


class Judge0ExecutionResult(BaseModel):
    token: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    compile_output: Optional[str] = None
    message: Optional[str] = None
    time: Optional[str] = None
    memory: Optional[int] = None
    status: dict
    language: Optional[dict] = None


class CodeExecutionResult(BaseModel):
    submission_id: Optional[str] = None
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


class Judge0SubmissionResponseWithMeta(BaseModel):
    token: str
    submission_id: Optional[int] = None
    created_at: Optional[datetime] = None


class LanguageInfo(BaseModel):
    id: int
    name: str


class Judge0Status(BaseModel):
    id: int
    description: str
