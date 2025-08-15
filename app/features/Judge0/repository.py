from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.DB.session import get_db
from .models import CodeSubmission, CodeResult
from .schemas import CodeSubmissionCreate, CodeExecutionResult


class Judge0Repository:
    """SQLAlchemy-based repository for Judge0 operations."""

    def __init__(self):
        pass

    def get_submission_by_token(self, judge0_token: str) -> Optional[CodeSubmission]:
        """Get submission by Judge0 token."""
        db = next(get_db())
        try:
            return db.query(CodeSubmission).filter(
                CodeSubmission.judge0_token == judge0_token
            ).first()
        finally:
            db.close()

    def create_result(self, submission_id: UUID, result: CodeExecutionResult) -> CodeResult:
        """Create a new execution result."""
        db = next(get_db())
        try:
            result_data = CodeResult(
                submission_id=submission_id,
                stdout=result.stdout,
                stderr=result.stderr,
                compile_output=result.compile_output,
                execution_time=result.execution_time,
                memory_used=result.memory_used,
                status_id=result.status_id,
                status_description=result.status_description,
                created_at=datetime.now(timezone.utc)
            )
            db.add(result_data)
            db.commit()
            db.refresh(result_data)
            return result_data
        except Exception as e:
            db.rollback()
            raise RuntimeError(f"Failed to create result record: {e}")
        finally:
            db.close()

    def create_submission(self, submission: CodeSubmissionCreate, user_id: UUID, judge0_token: str) -> CodeSubmission:
        """Create new submission record."""
        db = next(get_db())
        try:
            submission_data = CodeSubmission(
                user_id=user_id,
                source_code=submission.source_code,
                language_id=submission.language_id,
                stdin=submission.stdin,
                expected_output=submission.expected_output,
                judge0_token=judge0_token,
                status="submitted",
                created_at=datetime.now(timezone.utc)
            )
            db.add(submission_data)
            db.commit()
            db.refresh(submission_data)
            return submission_data
        except Exception as e:
            db.rollback()
            raise RuntimeError(f"Failed to create submission record: {e}")
        finally:
            db.close()

    def get_user_submissions(self, user_id: UUID, limit: int = 50) -> List[CodeSubmission]:
        """Get user's submissions with pagination."""
        db = next(get_db())
        try:
            return db.query(CodeSubmission).filter(
                CodeSubmission.user_id == user_id
            ).order_by(desc(CodeSubmission.created_at)).limit(limit).all()
        finally:
            db.close()

    def get_submission_with_results(self, submission_id: UUID) -> Optional[Dict[str, Any]]:
        """Get submission with all related results."""
        db = next(get_db())
        try:
            submission = db.query(CodeSubmission).filter(
                CodeSubmission.id == submission_id
            ).first()
            
            if not submission:
                return None
                
            results = db.query(CodeResult).filter(
                CodeResult.submission_id == submission_id
            ).order_by(desc(CodeResult.created_at)).all()
            
            return {
                "submission": submission,
                "results": results
            }
        finally:
            db.close()

    def delete_submission(self, submission_id: UUID, user_id: UUID) -> bool:
        """Delete submission and related results if user owns it."""
        db = next(get_db())
        try:
            # Check ownership
            submission = db.query(CodeSubmission).filter(
                CodeSubmission.id == submission_id,
                CodeSubmission.user_id == user_id
            ).first()
            
            if not submission:
                return False
                
            # Delete results first (cascade should handle this, but being explicit)
            db.query(CodeResult).filter(
                CodeResult.submission_id == submission_id
            ).delete()
            
            # Delete submission
            db.delete(submission)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise RuntimeError(f"Failed to delete submission: {e}")
        finally:
            db.close()

    def get_language_statistics(self, user_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        """Get language usage statistics."""
        db = next(get_db())
        try:
            query = db.query(
                CodeSubmission.language_id,
                func.count(CodeSubmission.id).label('submission_count')
            ).group_by(CodeSubmission.language_id)
            
            if user_id:
                query = query.filter(CodeSubmission.user_id == user_id)
                
            results = query.order_by(desc('submission_count')).all()
            
            return [
                {
                    "language_id": result.language_id,
                    "submission_count": result.submission_count
                }
                for result in results
            ]
        finally:
            db.close()

    def update_submission_status(self, submission_id: UUID, status: str, completed_at: Optional[datetime] = None) -> bool:
        """Update submission status and completion time."""
        db = next(get_db())
        try:
            submission = db.query(CodeSubmission).filter(
                CodeSubmission.id == submission_id
            ).first()
            
            if not submission:
                return False
                
            submission.status = status
            if completed_at:
                submission.completed_at = completed_at
                
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise RuntimeError(f"Failed to update submission status: {e}")
        finally:
            db.close()


# Repository instance
judge0_repository = Judge0Repository()

