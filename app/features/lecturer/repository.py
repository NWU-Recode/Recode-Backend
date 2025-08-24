from __future__ import annotations
from typing import Any, Dict, List, Optional
import uuid
import asyncio

class LecturerRepository:
    def __init__(self, client, executor):
        self._client = client
        self._executor = executor

    async def create_class(self, name: str, code: Optional[str], description: Optional[str]) -> Dict[str, Any]:
        def _work():
            return self._client.table("classes").insert({
                "id": str(uuid.uuid4()),
                "name": name,
                "code": code,
                "description": description
            }).execute()
        res = await asyncio.get_running_loop().run_in_executor(self._executor, _work)
        return (res.data or [])[0]

    async def list_classes(self) -> List[Dict[str, Any]]:
        def _work():
            return self._client.table("classes").select("id,name,code").order("name").execute()
        res = await asyncio.get_running_loop().run_in_executor(self._executor, _work)
        return res.data or []

    async def add_student_to_class(self, class_id: str, student_id: str) -> None:
        def _work():
            return self._client.table("class_students").upsert({
                "class_id": class_id,
                "student_id": student_id
            }).execute()
        await asyncio.get_running_loop().run_in_executor(self._executor, _work)

    async def remove_student_from_class(self, class_id: str, student_id: str) -> None:
        def _work():
            return self._client.table("class_students").delete().eq("class_id", class_id).eq("student_id", student_id).execute()
        await asyncio.get_running_loop().run_in_executor(self._executor, _work)

    async def assign_challenge(self, class_id: str, challenge_id: str, due_at: Optional[str]) -> None:
        def _work():
            return self._client.table("class_assignments").upsert({
                "class_id": class_id,
                "challenge_id": challenge_id,
                "due_at": due_at
            }).execute()
        await asyncio.get_running_loop().run_in_executor(self._executor, _work)

    # --- Slides & Generation ---
    async def store_upload_record(self, file_name: str, page_count: int, concepts: int) -> Dict[str, Any]:
        def _work():
            return self._client.table("slides_uploads").insert({
                "id": str(uuid.uuid4()),
                "file_name": file_name,
                "page_count": page_count,
                "concepts": concepts
            }).execute()
        res = await asyncio.get_running_loop().run_in_executor(self._executor, _work)
        return (res.data or [])[0]

    async def create_exercise_draft(self, title: str, prompt: str, difficulty: str, tier: str) -> Dict[str, Any]:
        def _work():
            return self._client.table("exercises").insert({
                "id": str(uuid.uuid4()),
                "title": title,
                "prompt": prompt,
                "difficulty": difficulty,
                "tier": tier,
                "status": "draft"
            }).execute()
        res = await asyncio.get_running_loop().run_in_executor(self._executor, _work)
        return (res.data or [])[0]

    async def list_exercises(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        def _work():
            q = self._client.table("exercises").select("id,title,prompt,difficulty,tier,status").order("title")
            if status:
                q = q.eq("status", status)
            return q.execute()
        res = await asyncio.get_running_loop().run_in_executor(self._executor, _work)
        return res.data or []

    async def publish_exercises(self, ids: List[str]) -> None:
        def _work():
            return self._client.table("exercises").update({"status": "published"}).in_("id", ids).execute()
        await asyncio.get_running_loop().run_in_executor(self._executor, _work)

    # --- Submissions ---
    async def list_challenge_submissions(self, challenge_id: str) -> List[Dict[str, Any]]:
        def _work():
            return self._client.table("submissions").select(
                "id,user_id,challenge_id,result_status,runtime_ms,created_at"
            ).eq("challenge_id", challenge_id).order("created_at", desc=True).execute()
        res = await asyncio.get_running_loop().run_in_executor(self._executor, _work)
        return res.data or []

    async def get_submission(self, submission_id: str) -> Optional[Dict[str, Any]]:
        def _work():
            res = self._client.table("submissions").select("*").eq("id", submission_id).limit(1).execute()
            rows = res.data or []
            return rows[0] if rows else None
        return await asyncio.get_running_loop().run_in_executor(self._executor, _work)