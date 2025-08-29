from __future__ import annotations

from typing import Dict, Any, Optional, List
import re

from app.features.topics.repository import TopicRepository
from app.adapters.nlp_spacy import extract_primary_topic


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


class TopicService:
    @staticmethod
    async def create_from_slides(
        slides_url: str,
        week: int,
        slide_texts: Optional[List[str]] = None,
        slides_key: Optional[str] = None,
        detected_topic: Optional[str] = None,
        detected_subtopics: Optional[List[str]] = None,
        slide_extraction_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create or return a topic derived from slides for a given week.

        - Slug format: w{week}-{topic_key}
        - Title from primary topic key (Title Case)
        - Subtopics saved when provided or derivable
        """
        base = slides_url.strip().split("/")[-1] or "topic"
        base = re.sub(r"\.[A-Za-z0-9]+$", "", base)
        primary_key = _slugify(base) or "topic"
        # Prefer basic NLP extraction if texts are present
        if slide_texts:
            key, subs = extract_primary_topic(slide_texts)
            primary_key = key or primary_key
            subtopics = subs
        else:
            subtopics = []
        slug = f"w{week:02d}-{primary_key}"
        existing = await TopicRepository.get_by_slug(slug)
        if existing:
            return existing
        title = primary_key.replace("-", " ").title()
        # Use detected_* overrides if provided
        det_topic = detected_topic or primary_key
        det_subs = detected_subtopics or subtopics
        return await TopicRepository.create(
            week=week,
            slug=slug,
            title=title,
            subtopics=subtopics,
            slides_key=slides_key,
            detected_topic=det_topic,
            detected_subtopics=det_subs,
            slide_extraction_id=slide_extraction_id,
        )


# Backwards-compatible entry point used by endpoints
async def create_from_slides(db, slides_url: str, week: int):  # noqa: ARG001 (db unused)
    return await TopicService.create_from_slides(slides_url, week)
