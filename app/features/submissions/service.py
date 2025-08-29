from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime

from .schemas import SubmissionCreate, SubmissionResultCreate
from .repository import submission_repository
from app.features.judge0.schemas import CodeExecutionResult
from app.DB.session import get_db
from app.features.submissions.schemas import SubmissionSchema

class SubmissionService:
    async def store_submission(self, submission: SubmissionCreate, user_id: str, judge0_token: str) -> Dict[str, Any]:
        return await submission_repository.create_submission(submission, user_id, judge0_token)

    async def store_result(self, judge0_token: str, exec_result: CodeExecutionResult) -> Dict[str, Any]:
        sub = await submission_repository.get_by_token(judge0_token)
        if not sub:
            raise RuntimeError("Submission not found for token")
        payload = SubmissionResultCreate(
            submission_id=sub["id"],
            stdout=exec_result.stdout,
            stderr=exec_result.stderr,
            compile_output=exec_result.compile_output,
            execution_time=exec_result.execution_time,
            memory_used=exec_result.memory_used,
            status_id=exec_result.status_id,
            status_description=exec_result.status_description,
            language_id=exec_result.language_id,
        )
        return await submission_repository.create_result(payload)

    async def get_submission_with_results(self, submission_id: str) -> Optional[Dict[str, Any]]:
        return await submission_repository.get_with_results(submission_id)

    async def get_submission_by_token(self, judge0_token: str) -> Optional[Dict[str, Any]]:
        return await submission_repository.get_by_token(judge0_token)

    async def list_user_submissions(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        return await submission_repository.list_user_submissions(user_id, limit)

    async def delete_submission(self, submission_id: str, user_id: str) -> bool:
        return await submission_repository.delete_submission(submission_id, user_id)

    async def language_statistics(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await submission_repository.language_statistics(user_id)

class SubmissionsService:
    def __init__(self, db):
        self.db = db

    def submit(self, user_id: int, question_id: int, submission_data: dict):
        """
        Handle submission creation.
        :param user_id: The ID of the user making the submission.
        :param question_id: The ID of the question being answered.
        :param submission_data: The submission data.
        """
        submission = SubmissionSchema(
            user_id=user_id,
            question_id=question_id,
            status="submitted",
            **submission_data
        )
        self.db.add(submission)
        self.db.commit()
        self.db.refresh(submission)

        # Notify relevant parties (mocked for now)
        print(f"Submission {submission.id} created for user {user_id}")

        return submission

    def create_submission(self, submission_data: SubmissionSchema):
        # Logic to create a submission
        pass

    def get_submission(self, submission_id: int):
        # Logic to retrieve a submission
        pass

    def update_submission(self, submission_id: int, submission_data: SubmissionSchema):
        # Logic to update a submission
        pass

    def delete_submission(self, submission_id: int):
        # Logic to delete a submission
        pass

    def execute(self, submission_id: int):
        """
        Execute a submission by running tests.
        :param submission_id: The ID of the submission to execute.
        """
        submission = self.db.query(SubmissionSchema).get(submission_id)
        if not submission:
            raise ValueError("Submission not found")

        # Run tests (mocked for now)
        results = {
            "passed": True,
            "score": 100,
        }

        # Update submission with results
        submission.status = "executed"
        submission.score = results["score"]
        self.db.add(submission)
        self.db.commit()
        self.db.refresh(submission)

        return results

submission_service = SubmissionService()
