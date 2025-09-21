from __future__ import annotations

from typing import Optional, Dict, Any
import logging
import uuid
from app.DB.supabase import get_supabase
from app.common import cache
import asyncio, time, os
try:
    from postgrest.exceptions import APIError  # type: ignore
except Exception:  # pragma: no cover - optional import for resilience
    APIError = Exception  # type: ignore


class TopicRepository:
    # Supabase project uses singular table name 'topic'
    table = "topic"

    @staticmethod
    async def get_by_title(title: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = await client.table(TopicRepository.table).select("*").eq("title", title).limit(1).execute()
        return (resp.data[0] if resp.data else None)

    @staticmethod
    async def create(
        week: int,
        slug: str,
        title: str,
        subtopics: Optional[list[str]] = None,
        slides_key: Optional[str] = None,
        detected_topic: Optional[str] = None,
        detected_subtopics: Optional[list[str]] = None,
        slide_extraction_id: Optional[int] = None,
        module_code_slidesdeck: Optional[str] = None,
        module_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        client = await get_supabase()
        payload: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "week": week, 
            "slug": slug, 
            "title": title
        }
        if subtopics is not None:
            payload["subtopics"] = subtopics
        if slides_key is not None:
            payload["slides_key"] = slides_key
        if detected_topic is not None:
            payload["detected_topic"] = detected_topic
        if detected_subtopics is not None:
            payload["detected_subtopics"] = detected_subtopics
        if slide_extraction_id is not None:
            payload["slide_extraction_id"] = slide_extraction_id
        if module_code_slidesdeck is not None:
            payload["module_code_slidesdeck"] = module_code_slidesdeck
        if module_id is not None:
            payload["module_id"] = module_id
        resp = await client.table(TopicRepository.table).insert(payload).execute()
        if not getattr(resp, "data", None):
            raise RuntimeError("Failed to create topic")
        return resp.data[0]
