from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.client import get_supabase 
from app.db.session import SessionLocal 
from .models import CodeSubmission, CodeResult
from .schemas import CodeSubmissionCreate, CodeExecutionResult

class Judge0Repository:
    """Database operations for Judge0"""
    
    def __init__(self):
        self.supabase = get_supabase
    
    # Using SQLAlchemy for new operations
    def create_submission_sql(self, submission: CodeSubmissionCreate, user_id: str, judge0_token: str, db: Session = None) -> CodeSubmission:
        """Create submission using SQLAlchemy"""
        if not db:
            db = SessionLocal()
            close_db = True
        else:
            close_db = False
            
        try:
            db_submission = CodeSubmission(
                user_id=user_id,
                source_code=submission.source_code,
                language_id=submission.language_id,
                stdin=submission.stdin,
                expected_output=submission.expected_output,
                judge0_token=judge0_token,
                status="submitted"
            )
            db.add(db_submission)
            db.commit()
            db.refresh(db_submission)
            return db_submission
        finally:
            if close_db:
                db.close()
    
    def get_submission_by_token_sql(self, judge0_token: str, db: Session = None) -> Optional[CodeSubmission]:
        """Get submission by token using SQLAlchemy"""
        if not db:
            db = SessionLocal()
            close_db = True
        else:
            close_db = False
            
        try:
            return db.query(CodeSubmission).filter(CodeSubmission.judge0_token == judge0_token).first()
        finally:
            if close_db:
                db.close()
    
    def create_result_sql(self, submission_id: str, result: CodeExecutionResult, db: Session = None) -> CodeResult:
        """Create result using SQLAlchemy"""
        if not db:
            db = SessionLocal()
            close_db = True
        else:
            close_db = False
            
        try:
            db_result = CodeResult(
                submission_id=submission_id,
                stdout=result.stdout,
                stderr=result.stderr,
                compile_output=result.compile_output,
                execution_time=result.execution_time,
                memory_used=result.memory_used,
                status_id=result.status_id,
                status_description=result.status_description
            )
            db.add(db_result)
            db.commit()
            db.refresh(db_result)
            return db_result
        finally:
            if close_db:
                db.close()
    
    # Keep existing Supabase methods for backward compatibility
    async def create_submission(self, submission: CodeSubmissionCreate, user_id: str, judge0_token: str) -> Dict[str, Any]:
        """Create new submission record"""
        try:
            submission_data = {
                "user_id": user_id,
                "source_code": submission.source_code,
                "language_id": submission.language_id,
                "stdin": submission.stdin,
                "expected_output": submission.expected_output,
                "judge0_token": judge0_token,
                "status": "submitted",
                "created_at": datetime.utcnow().isoformat()
            }
            
            response = self.supabase.table("code_submissions").insert(submission_data).execute()
            
            if response.data:
                return response.data[0]
            else:
                raise Exception("Failed to create submission record")
                
        except Exception as e:
            print(f"Error creating submission: {e}")
            raise e

    # --- Async (Supabase) query utilities used by service endpoints ---
    async def get_user_submissions(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            resp = self.supabase.table("code_submissions").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
            return resp.data or []
        except Exception as e:
            print(f"Error fetching user submissions: {e}")
            raise e

    async def get_submission_with_results(self, submission_id: str) -> Optional[Dict[str, Any]]:
        try:
            # Fetch submission
            submission_resp = self.supabase.table("code_submissions").select("*").eq("id", submission_id).single().execute()
            if not submission_resp.data:
                return None
            # Fetch related results
            results_resp = self.supabase.table("code_results").select("*").eq("submission_id", submission_id).order("created_at", desc=True).execute()
            return {"submission": submission_resp.data, "results": results_resp.data or []}
        except Exception as e:
            print(f"Error fetching submission details: {e}")
            raise e

    async def delete_submission(self, submission_id: str, user_id: str) -> bool:
        try:
            # Ensure ownership then delete (Supabase RLS may enforce this too)
            sub_resp = self.supabase.table("code_submissions").select("id,user_id").eq("id", submission_id).single().execute()
            if not sub_resp.data or sub_resp.data.get("user_id") != user_id:
                return False
            # Delete results first (if no cascade)
            self.supabase.table("code_results").delete().eq("submission_id", submission_id).execute()
            self.supabase.table("code_submissions").delete().eq("id", submission_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting submission: {e}")
            raise e

    async def get_language_statistics(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Aggregate submissions per language (basic fallback implementation)."""
        try:
            query = self.supabase.table("code_submissions").select("language_id").order("created_at", desc=True)
            if user_id:
                query = query.eq("user_id", user_id)
            resp = query.execute()
            counts: Dict[int, int] = {}
            for row in resp.data or []:
                lang_id = row.get("language_id")
                if lang_id is not None:
                    counts[lang_id] = counts.get(lang_id, 0) + 1
            return [ {"language_id": k, "submission_count": v} for k, v in sorted(counts.items(), key=lambda kv: kv[1], reverse=True) ]
        except Exception as e:
            print(f"Error computing language statistics: {e}")
            raise e

# Repository instance
judge0_repository = Judge0Repository()

