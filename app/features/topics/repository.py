from __future__ import annotations

from typing import Optional, Dict, Any
from app.DB.supabase import get_supabase


class TopicRepository:
    table = "topics"

    @staticmethod
    async def get_by_slug(slug: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = client.table(TopicRepository.table).select("*").eq("slug", slug).limit(1).execute()
        return (resp.data[0] if resp.data else None)

    @staticmethod
    async def create(week: int, slug: str, title: str, subtopics: Optional[list[str]] = None) -> Dict[str, Any]:
        client = await get_supabase()
        payload: Dict[str, Any] = {"week": week, "slug": slug, "title": title}
        if subtopics is not None:
            payload["subtopics"] = subtopics
        resp = client.table(TopicRepository.table).insert(payload).execute()
        if not resp.data:
            raise RuntimeError("Failed to create topic")
        return resp.data[0]
