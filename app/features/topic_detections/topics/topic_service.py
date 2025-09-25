from __future__ import annotations

from typing import Any, Dict, List, Optional
import re
from app.DB.supabase import get_supabase

from app.features.topic_detections.topics.repository import TopicRepository

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
        module_code: Optional[str] = None,
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
        title = primary_key.replace("-", " ").title()
        # Make title unique by including week number
        title = f"Week {week}: {title}"
        slug = f"w{week:02d}-{primary_key}"
        # Resolve module_id if module_code provided
        module_id = None
        if module_code:
            module_id = await TopicService().resolve_module_id_by_code(module_code)
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
            module_code_slidesdeck=module_code,
            module_id=module_id,
        )

    async def resolve_module_id_by_code(self, module_code: str) -> Optional[str]:
        client = await get_supabase()
        # Directly resolve modules.id from modules.code
        try:
            resp = await client.table("modules").select("id").eq("code", str(module_code)).limit(1).execute()
            rows = resp.data or []
            if rows:
                rid = rows[0].get("id")
                if rid:
                    return str(rid)
        except Exception:
            pass
        return None

    async def get_topics_from_slide_extraction(self, slide_stack_id: int) -> List[str]:
        client = await get_supabase()
        #Fetch topics from slide_extraction table for a given slide_stack_id.
        try:
            response = await client.table("slide_extractions").select(
                "detected_topic, detected_subtopics"
            ).eq("id", slide_stack_id).execute()

            if not response.data:
                return []

            topics = []
            for record in response.data:
                # Add main detected topic
                if record.get("detected_topic"):
                    topics.append(record["detected_topic"])

                # Add detected subtopics
                if record.get("detected_subtopics"):
                    if isinstance(record["detected_subtopics"], list):
                        topics.extend(record["detected_subtopics"])
                    elif isinstance(record["detected_subtopics"], str):
                        # If stored as JSON string, try to parse
                        try:
                            import json
                            subtopics = json.loads(record["detected_subtopics"])
                            if isinstance(subtopics, list):
                                topics.extend(subtopics)
                        except:
                            pass

            return list(set(topics))  # Remove duplicates
        except Exception as e:
            print(f"Error fetching topics from slide_extraction: {e}")
            return []



    async def get_slide_extraction_by_week(self, week_number: int, module_code: Optional[str] = None) -> List[Dict[str, Any]]:
        client = await get_supabase()
        # Get all slide extractions for a specific week and optional module_code (not id)
        try:
            query = client.table("slide_extractions").select("id, module_id, week_number, detected_topic, detected_subtopics, module_code").eq("week_number", week_number)
            if module_code is not None:
                query = query.eq("module_code", str(module_code))
            response = await query.execute()
            return response.data if response.data else []
        except Exception as e:
            print(f"Error fetching slide extractions for week {week_number}: {e}")
            return []

    async def get_all_topics_for_week(self, week_number: int, module_code: Optional[str] = None) -> List[str]:
        # Get all unique topics for a specific week and module_code
        slide_extractions = await self.get_slide_extraction_by_week(week_number, module_code)
        all_topics = []
        for extraction in slide_extractions:
            if extraction.get("detected_topic"):
                all_topics.append(extraction["detected_topic"])
            if extraction.get("detected_subtopics"):
                if isinstance(extraction["detected_subtopics"], list):
                    all_topics.extend(extraction["detected_subtopics"])
                elif isinstance(extraction["detected_subtopics"], str):
                    try:
                        import json
                        subtopics = json.loads(extraction["detected_subtopics"])
                        if isinstance(subtopics, list):
                            all_topics.extend(subtopics)
                    except:
                        pass
        return list(set(all_topics))

    async def get_topics_for_module_week(self, module_code: str, week_number: int) -> List[str]:
        client = await get_supabase()
        # Exact query: select topics for given module_code and week number.
        try:
            rows: List[Dict[str, Any]] = []
            base = client.table("slide_extractions").select("detected_topic, detected_subtopics")
            resp = await base.eq("module_code", str(module_code)).eq("week_number", week_number).execute()
            rows = resp.data or []
            topics: List[str] = []
            for row in rows:
                if row.get("detected_topic"):
                    topics.append(row["detected_topic"])
                ds = row.get("detected_subtopics")
                if ds:
                    if isinstance(ds, list):
                        topics.extend(ds)
                    elif isinstance(ds, str):
                        try:
                            import json
                            arr = json.loads(ds)
                            if isinstance(arr, list):
                                topics.extend(arr)
                        except:
                            pass
            return list(set(topics))
        except Exception as e:
            print(f"Error fetching topics for module {module_code}, week {week_number}: {e}")
            return []

    async def update_slide_extraction_id(self, topic_uuid: str, slide_extraction_id: int) -> None:
        """Update the slide_extraction_id for a topic."""
        client = await get_supabase()
        try:
            await client.table("topic").update({
                "slide_extraction_id": slide_extraction_id
            }).eq("id", topic_uuid).execute()
        except Exception as e:
            print(f"Error updating slide_extraction_id for topic {topic_uuid}: {e}")


# Global instance
topic_service = TopicService()
