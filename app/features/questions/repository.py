from __future__ import annotations
from typing import Optional, Dict, Any, List
from uuid import UUID
from app.DB.supabase import get_supabase

class QuestionRepository:
    async def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = client.table("questions").select("*").eq("id", question_id).single().execute()
        return resp.data or None

    async def upsert_attempt(self, attempt: Dict[str, Any]) -> Dict[str, Any]:
        client = await get_supabase()
        # If id provided treat as update, else insert
        if attempt.get("id"):
            aid = attempt.pop("id")
            resp = client.table("question_attempts").update(attempt).eq("id", aid).execute()
        else:
            resp = client.table("question_attempts").insert(attempt).execute()
        if not resp.data:
            raise RuntimeError("Failed to persist question attempt")
        return resp.data[0]

    async def mark_previous_not_latest(self, question_id: str, user_id: str):
        client = await get_supabase()
        client.table("question_attempts").update({"latest": False}).eq("question_id", question_id).eq("user_id", user_id).eq("latest", True).execute()

    async def get_existing_attempt(self, question_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = (
            client.table("question_attempts")
            .select("*")
            .eq("question_id", question_id)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return None

    async def find_by_code_hash(self, question_id: str, user_id: str, code_hash: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = (
            client.table("question_attempts")
            .select("*")
            .eq("question_id", question_id)
            .eq("user_id", user_id)
            .eq("code_hash", code_hash)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return None

    async def find_by_idempotency_key(self, question_id: str, user_id: str, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Return existing attempt matching idempotency key (latest semantics implicit via unique constraint)."""
        client = await get_supabase()
        resp = (
            client.table("question_attempts")
            .select("*")
            .eq("question_id", question_id)
            .eq("user_id", user_id)
            .eq("idempotency_key", idempotency_key)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return None

    async def find_by_token(self, question_id: str, user_id: str, token: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = (
            client.table("question_attempts")
            .select("*")
            .eq("question_id", question_id)
            .eq("user_id", user_id)
            .eq("judge0_token", token)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return None

    async def list_attempts_for_challenge(self, challenge_id: str, user_id: str) -> List[Dict[str, Any]]:
        client = await get_supabase()
        resp = (
            client.table("question_attempts")
            .select("*")
            .eq("user_id", user_id)
            .eq("challenge_id", challenge_id)
            .execute()
        )
        return resp.data or []

    async def list_latest_attempts_for_challenge(self, challenge_id: str, user_id: str) -> List[Dict[str, Any]]:
        client = await get_supabase()
        resp = (
            client.table("question_attempts")
            .select("*")
            .eq("user_id", user_id)
            .eq("challenge_id", challenge_id)
            .eq("latest", True)
            .execute()
        )
        return resp.data or []
    
    async def create_question(self, question_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new question"""
        client = await get_supabase()
        resp = client.table("questions").insert(question_data).execute()
        if not resp.data:
            raise RuntimeError("Failed to create question")
        return resp.data[0]

    async def update_question(self, question_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing question"""
        client = await get_supabase()
        resp = client.table("questions").update(update_data).eq("id", question_id).execute()
        if not resp.data:
            raise RuntimeError("Failed to update question")
        return resp.data[0]

    async def delete_question(self, question_id: str) -> bool:
        """Delete a question"""
        client = await get_supabase()
        resp = client.table("questions").delete().eq("id", question_id).execute()
        return bool(resp.data)

    async def list_questions(
        self, 
        topic: Optional[str] = None,
        tier: Optional[str] = None,
        language_id: Optional[int] = None,
        is_active: bool = True
    ) -> List[Dict[str, Any]]:
        """List questions with optional filters"""
        client = await get_supabase()
        query = client.table("questions").select("*")
        
        if is_active:
            query = query.eq("is_active", True)
        if topic:
            query = query.ilike("topic", f"%{topic}%")
        if tier:
            query = query.eq("tier", tier)
        if language_id:
            query = query.eq("language_id", language_id)
            
        resp = query.execute()
        return resp.data or []

    async def get_questions_by_tags(self, tags: List[str], tier: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get questions that match any of the provided tags"""
        client = await get_supabase()
        query = client.table("questions").select("*").eq("is_active", True)
        
        if tier:
            query = query.eq("tier", tier)
        
        # For tag matching, we'll use OR conditions
        if tags:
            # This is a simplified approach - you might want to implement more sophisticated tag matching
            conditions = []
            for tag in tags:
                conditions.append(f"topic.ilike.%{tag}%")
            # Note: Supabase doesn't directly support OR with multiple ilike, 
            # so you might need to make multiple queries and merge results
        
        resp = query.execute()
        return resp.data or []

    async def get_question_stats(self) -> Dict[str, Any]:
        """Get statistics about questions"""
        client = await get_supabase()
        
        # Get all questions
        all_questions = client.table("questions").select("tier, topic, is_active").execute()
        questions = all_questions.data or []
        
        # Get usage stats
        usage_stats = client.table("question_usage").select("question_id, times_attempted, times_passed").execute()
        usage = usage_stats.data or []
        
        return {
            "questions": questions,
            "usage": usage
        }

    # HINT MANAGEMENT
    async def create_hint(self, hint_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a hint for a question"""
        client = await get_supabase()
        resp = client.table("question_hints").insert(hint_data).execute()
        if not resp.data:
            raise RuntimeError("Failed to create hint")
        return resp.data[0]

    async def update_hint(self, hint_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a hint"""
        client = await get_supabase()
        resp = client.table("question_hints").update(update_data).eq("id", hint_id).execute()
        if not resp.data:
            raise RuntimeError("Failed to update hint")
        return resp.data[0]

    async def delete_hint(self, hint_id: str) -> bool:
        """Delete a hint"""
        client = await get_supabase()
        resp = client.table("question_hints").delete().eq("id", hint_id).execute()
        return bool(resp.data)

    async def get_hints_for_question(self, question_id: str) -> List[Dict[str, Any]]:
        """Get all hints for a question"""
        client = await get_supabase()
        resp = client.table("question_hints").select("*").eq("question_id", question_id).order("order_index").execute()
        return resp.data or []

    async def get_hint(self, hint_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific hint"""
        client = await get_supabase()
        resp = client.table("question_hints").select("*").eq("id", hint_id).single().execute()
        return resp.data or None

    # HINT USAGE TRACKING
    async def record_hint_usage(self, user_id: str, challenge_id: str, question_id: str, hint_id: str) -> Dict[str, Any]:
        """Record that a student used a hint"""
        client = await get_supabase()
        usage_data = {
            "user_id": user_id,
            "challenge_id": challenge_id,
            "question_id": question_id,
            "hint_id": hint_id,
            "used_at": datetime.now().isoformat()
        }
        resp = client.table("hint_usage").insert(usage_data).execute()
        if not resp.data:
            raise RuntimeError("Failed to record hint usage")
        return resp.data[0]

    async def get_hint_usage(self, user_id: str, challenge_id: str, question_id: str) -> List[Dict[str, Any]]:
        """Get hints used by a student for a specific question"""
        client = await get_supabase()
        resp = (
            client.table("hint_usage")
            .select("*")
            .eq("user_id", user_id)
            .eq("challenge_id", challenge_id)
            .eq("question_id", question_id)
            .execute()
        )
        return resp.data or []

    async def count_hints_used(self, user_id: str, challenge_id: str, question_id: str) -> int:
        """Count how many hints a student has used for a question"""
        usage = await self.get_hint_usage(user_id, challenge_id, question_id)
        return len(usage)

    # EDITOR EVENT TRACKING
    async def record_editor_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record an editor event for plagiarism detection"""
        client = await get_supabase()
        resp = client.table("editor_events").insert(event_data).execute()
        if not resp.data:
            raise RuntimeError("Failed to record editor event")
        return resp.data[0]

    async def get_editor_events(
        self, 
        user_id: str, 
        challenge_id: str, 
        question_id: str,
        event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get editor events for a user/question"""
        client = await get_supabase()
        query = (
            client.table("editor_events")
            .select("*")
            .eq("user_id", user_id)
            .eq("challenge_id", challenge_id)
            .eq("question_id", question_id)
        )
        
        if event_type:
            query = query.eq("event_type", event_type)
            
        resp = query.order("occurred_at", desc=True).execute()
        return resp.data or []

    # QUESTION USAGE STATISTICS
    async def update_question_usage(self, question_id: str, challenge_id: Optional[str] = None, passed: bool = False):
        """Update question usage statistics"""
        client = await get_supabase()
        
        # Try to get existing usage record
        query = client.table("question_usage").select("*").eq("question_id", question_id)
        if challenge_id:
            query = query.eq("challenge_id", challenge_id)
        
        resp = query.execute()
        
        if resp.data:
            # Update existing record
            existing = resp.data[0]
            update_data = {
                "times_attempted": existing["times_attempted"] + 1,
                "times_passed": existing["times_passed"] + (1 if passed else 0),
                "updated_at": datetime.now().isoformat()
            }
            client.table("question_usage").update(update_data).eq("id", existing["id"]).execute()
        else:
            # Create new record
            usage_data = {
                "question_id": question_id,
                "challenge_id": challenge_id,
                "times_attempted": 1,
                "times_passed": 1 if passed else 0
            }
            client.table("question_usage").insert(usage_data).execute()

    async def get_question_difficulty_distribution(self) -> Dict[str, int]:
        """Get count of questions by difficulty tier"""
        client = await get_supabase()
        resp = client.table("questions").select("tier").eq("is_active", True).execute()
        questions = resp.data or []
        
        distribution = {}
        for q in questions:
            tier = q.get("tier", "unknown")
            distribution[tier] = distribution.get(tier, 0) + 1
            
        return distribution

    async def get_questions_for_challenge(self, challenge_id: str) -> List[Dict[str, Any]]:
        """Get all questions associated with a challenge"""
        client = await get_supabase()
        resp = (
            client.table("challenge_questions")
            .select("*, questions(*)")
            .eq("challenge_id", challenge_id)
            .order("order_index")
            .execute()
        )
        return resp.data or []

    async def assign_question_to_challenge(self, challenge_id: str, question_id: str, order_index: int = 0) -> Dict[str, Any]:
        """Assign a question to a challenge"""
        client = await get_supabase()
        assignment_data = {
            "challenge_id": challenge_id,
            "question_id": question_id,
            "order_index": order_index
        }
        resp = client.table("challenge_questions").insert(assignment_data).execute()
        if not resp.data:
            raise RuntimeError("Failed to assign question to challenge")
        return resp.data[0]

    async def remove_question_from_challenge(self, challenge_id: str, question_id: str) -> bool:
        """Remove a question from a challenge"""
        client = await get_supabase()
        resp = (
            client.table("challenge_questions")
            .delete()
            .eq("challenge_id", challenge_id)
            .eq("question_id", question_id)
            .execute()
        )
        return bool(resp.data)

question_repository = QuestionRepository()
