from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime

from .schemas import SubmissionCreate, SubmissionResultCreate
from .repository import submission_repository
from app.features.judge0.schemas import CodeExecutionResult

class SubmissionService:
    
    async def store_submission(self, submission: SubmissionCreate, user_id: str, judge0_token: str) -> Dict[str, Any]:
        """Store a code submission"""
        return await submission_repository.create_submission(submission, user_id, judge0_token)

    async def store_result(self, judge0_token: str, exec_result: CodeExecutionResult) -> Dict[str, Any]:
        """Store execution result for a submission"""
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

    async def process_pending_submission(self, judge0_token: str) -> Optional[Dict[str, Any]]:
        """Process a pending submission by checking Judge0 status"""
        from app.features.judge0.service import judge0_service
        from app.features.questions.repository import question_repository
        
        # Get the submission
        submission = await submission_repository.get_by_token(judge0_token)
        if not submission:
            return None
            
        # Check Judge0 status
        try:
            raw_result = await judge0_service.get_submission_result(judge0_token)
            status_id = raw_result.status.get("id") if raw_result.status else None
            
            # If still pending, return None
            if status_id in [1, 2]:  # In Queue or Processing
                return None
                
            # Convert to execution result
            result = judge0_service._to_code_execution_result(
                raw_result,
                submission.get("expected_output"),
                submission.get("language_id")
            )
            
            # Store the result
            await self.store_result(judge0_token, result)
            
            # Update submission status
            await submission_repository.update_submission_status(
                submission["id"], 
                "completed", 
                datetime.now(timezone.utc)
            )
            
            # If this was part of a question attempt, update that too
            if submission.get("question_id"):
                await self._update_question_attempt_with_result(
                    submission["question_id"],
                    submission["user_id"],
                    judge0_token,
                    result
                )
            
            return {
                "submission": submission,
                "result": result,
                "status": "completed"
            }
            
        except Exception as e:
            # Mark as failed
            await submission_repository.update_submission_status(
                submission["id"],
                "failed",
                datetime.now(timezone.utc)
            )
            raise e

    async def _update_question_attempt_with_result(
        self,
        question_id: str,
        user_id: str,
        judge0_token: str,
        result: CodeExecutionResult
    ):
        """Update question attempt with execution result"""
        from app.features.questions.repository import question_repository
        from app.features.questions.grading import map_app_status
        
        # Find the question attempt by token
        attempt = await question_repository.find_by_token(question_id, user_id, judge0_token)
        if not attempt:
            return
            
        # Update the attempt with results
        is_correct = result.success
        app_status = map_app_status(result.status_id, is_correct)
        
        update_data = {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "status_id": result.status_id,
            "status_description": result.status_description,
            "time": result.execution_time,
            "memory": result.memory_used,
            "is_correct": is_correct,
            "points_awarded": 1 if is_correct else 0
        }
        
        await question_repository.upsert_attempt({
            **attempt,
            **update_data,
            "id": attempt["id"]
        })

    async def batch_process_pending_submissions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Process multiple pending submissions"""
        client = await get_supabase()
        
        # Get pending submissions
        resp = (
            client.table("code_submissions")
            .select("*")
            .eq("status", "submitted")
            .order("created_at")
            .limit(limit)
            .execute()
        )
        
        pending_submissions = resp.data or []
        results = []
        
        # Process each submission
        for submission in pending_submissions:
            try:
                result = await self.process_pending_submission(submission["judge0_token"])
                if result:
                    results.append(result)
            except Exception as e:
                results.append({
                    "submission": submission,
                    "status": "failed",
                    "error": str(e)
                })
        
        return results

    async def get_submission_with_results(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Get submission with all its results"""
        return await submission_repository.get_with_results(submission_id)

    async def get_submission_by_token(self, judge0_token: str) -> Optional[Dict[str, Any]]:
        """Get submission by Judge0 token"""
        return await submission_repository.get_by_token(judge0_token)

    async def list_user_submissions(
        self,
        user_id: str,
        limit: int = 50,
        question_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List submissions for a user with optional filters"""
        client = await get_supabase()
        
        query = (
            client.table("code_submissions")
            .select("*")
            .eq("user_id", user_id)
        )
        
        if question_id:
            query = query.eq("question_id", question_id)
        if status:
            query = query.eq("status", status)
            
        resp = query.order("created_at", desc=True).limit(limit).execute()
        return resp.data or []

    async def delete_submission(self, submission_id: str, user_id: str) -> bool:
        """Delete a submission (with ownership check)"""
        return await submission_repository.delete_submission(submission_id, user_id)

    async def language_statistics(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get language usage statistics"""
        return await submission_repository.language_statistics(user_id)

    async def get_user_submission_stats(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive submission statistics for a user"""
        client = await get_supabase()
        
        # Get all submissions
        all_submissions = (
            client.table("code_submissions")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        ).data or []
        
        # Get question attempts
        attempts = (
            client.table("question_attempts")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        ).data or []
        
        # Calculate statistics
        total_submissions = len(all_submissions)
        total_attempts = len(attempts)
        correct_attempts = len([a for a in attempts if a.get("is_correct")])
        
        # Language distribution
        lang_counts = {}
        for sub in all_submissions:
            lang_id = sub.get("language_id")
            lang_counts[lang_id] = lang_counts.get(lang_id, 0) + 1
        
        # Status distribution
        status_counts = {}
        for sub in all_submissions:
            status = sub.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "user_id": user_id,
            "total_submissions": total_submissions,
            "total_attempts": total_attempts,
            "correct_attempts": correct_attempts,
            "accuracy_rate": correct_attempts / total_attempts if total_attempts > 0 else 0,
            "language_distribution": lang_counts,
            "status_distribution": status_counts
        }

    async def cleanup_old_submissions(self, days_old: int = 30) -> int:
        """Clean up old submissions to save space"""
        client = await get_supabase()
        
        from datetime import timedelta
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        # Delete old submissions
        resp = (
            client.table("code_submissions")
            .delete()
            .lt("created_at", cutoff_date.isoformat())
            .eq("status", "completed")
            .execute()
        )
        
        return len(resp.data or [])

    async def resubmit_failed_submissions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Resubmit failed submissions"""
        client = await get_supabase()
        
        query = client.table("code_submissions").select("*").eq("status", "failed")
        if user_id:
            query = query.eq("user_id", user_id)
        
        failed_submissions = query.execute().data or []
        results = []
        
        from app.features.judge0.service import judge0_service
        from app.features.judge0.schemas import CodeSubmissionCreate
        
        for submission in failed_submissions:
            try:
                # Recreate the submission
                code_sub = CodeSubmissionCreate(
                    source_code=submission["source_code"],
                    language_id=submission["language_id"],
                    stdin=submission.get("stdin"),
                    expected_output=submission.get("expected_output")
                )
                
                # Resubmit to Judge0
                token_resp = await judge0_service.submit_code(code_sub)
                
                # Update the submission record
                await submission_repository.update_submission_status(
                    submission["id"],
                    "submitted"
                )
                
                # Update token if it changed
                if token_resp.token != submission["judge0_token"]:
                    client.table("code_submissions").update({
                        "judge0_token": token_resp.token
                    }).eq("id", submission["id"]).execute()
                
                results.append({
                    "submission_id": submission["id"],
                    "new_token": token_resp.token,
                    "status": "resubmitted"
                })
                
            except Exception as e:
                results.append({
                    "submission_id": submission["id"],
                    "status": "resubmit_failed",
                    "error": str(e)
                })
        
        return results

    async def get_submission_timeline(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get timeline of user's submissions"""
        client = await get_supabase()
        
        # Get submissions with results
        submissions = (
            client.table("code_submissions")
            .select("*, code_results(*)")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        ).data or []
        
        timeline = []
        for sub in submissions:
            results = sub.get("code_results", [])
            latest_result = results[0] if results else None
            
            timeline.append({
                "submission_id": sub["id"],
                "question_id": sub.get("question_id"),
                "language_id": sub["language_id"],
                "status": sub["status"],
                "created_at": sub["created_at"],
                "completed_at": sub.get("completed_at"),
                "execution_time": latest_result.get("execution_time") if latest_result else None,
                "memory_used": latest_result.get("memory_used") if latest_result else None,
                "success": latest_result.get("status_id") == 3 if latest_result else None
            })
        
        return timeline

submission_service = SubmissionService()