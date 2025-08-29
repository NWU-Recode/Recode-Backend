from __future__ import annotations

from typing import Optional, Dict, Any
import logging
from app.DB.supabase import get_supabase
try:
    from postgrest.exceptions import APIError  # type: ignore
except Exception:  # pragma: no cover - optional import for resilience
    APIError = Exception  # type: ignore


class TopicRepository:
    # Supabase project uses singular table name 'topic'
    table = "topic"

    @staticmethod
    async def get_by_slug(slug: str) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = await client.table(TopicRepository.table).select("*").eq("slug", slug).limit(1).execute()
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
    ) -> Dict[str, Any]:
        client = await get_supabase()
        payload: Dict[str, Any] = {"week": week, "slug": slug, "title": title}
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
        try:
            resp = await client.table(TopicRepository.table).insert(payload).execute()
            if not getattr(resp, "data", None):
                raise RuntimeError("Failed to create topic")
            return resp.data[0]
        except APIError as e:  # Missing columns in Supabase schema: fallback to minimal payload
            msg = getattr(e, "message", str(e))
            code = getattr(e, "code", None)
            logging.getLogger("topics.repo").warning("Supabase topic insert failed (%s): %s", code, msg)
            # Retry without optional detection fields
            minimal = {k: v for k, v in payload.items() if k in ("week", "slug", "title", "subtopics", "slides_key")}
            resp2 = await client.table(TopicRepository.table).insert(minimal).execute()
            if not getattr(resp2, "data", None):
                raise
            return resp2.data[0]
