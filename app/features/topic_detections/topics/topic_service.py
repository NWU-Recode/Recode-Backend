from __future__ import annotations

from typing import Any, Dict, List, Optional
import re
from app.DB.supabase import get_supabase
from app.features.topic_detections.topics.repository import TopicRepository
from app.features.topic_detections.topics.extractor import extract_topics_from_slides

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

        primary_key = "programming-concepts"  #Safe default
        subtopics = []
        
        #extract topics using slide structure
        if slide_texts and len(slide_texts) > 0:
            print(f"[TopicService] Processing {len(slide_texts)} slides for week {week}")
            
            try:
                # Use structure-aware extraction
                validated_topics, domain = extract_topics_from_slides(
                    slide_texts, 
                    top_n=5
                )
                
                print(f"[TopicService] Extracted: {validated_topics}")
                print(f"[TopicService] Domain: {domain}")
                
                if validated_topics and len(validated_topics) > 0:
                    #first topic is primary (most relevant)
                    primary_key = validated_topics[0]
                    
                    #rest are subtopics
                    subtopics = validated_topics[1:4]
                    
                    print(f"[TopicService] Primary: {primary_key}")
                    print(f"[TopicService] Subtopics: {subtopics}")
                else:
                    print(f"[TopicService] WARNING: No topics extracted for week {week}")
                    #fallback: try to get something from first slide title
                    if slide_texts[0]:
                        first_slide = slide_texts[0].lower()
                        #look for common topic indicators
                        for indicator in ["file", "loop", "function", "class", "array", "list"]:
                            if indicator in first_slide:
                                primary_key = indicator
                                print(f"[TopicService] Using fallback topic from first slide: {primary_key}")
                                break
                                
            except Exception as e:
                print(f"[TopicService] Extraction error: {e}")
                primary_key = "programming-concepts"
        else:
            print("[TopicService] No slide_texts provided")
            #extract from filename as last resort if possible
            base = slides_url.strip().split("/")[-1] or "topic"
            base = re.sub(r"\.[A-Za-z0-9]+$", "", base)
            filename_hint = _slugify(base)
            if filename_hint and filename_hint != "topic":
                primary_key = filename_hint
                print(f"[TopicService] Using filename hint: {primary_key}")
        
        #Use overrides ONLY as fallback else it gives inaccurate topics (very vague)
        if not primary_key or primary_key == "programming-concepts":
            if detected_topic:
                primary_key = detected_topic
                print(f"[TopicService] Fallback: using detected_topic = {primary_key}")

        if not subtopics:
            if detected_subtopics:
                subtopics = detected_subtopics
        #slugified versions
        primary_slug = _slugify(primary_key)
        subtopics_slugs = [_slugify(st) for st in subtopics if st]
        
        #building the title
        title = primary_slug.replace("-", " ").title()
        title = f"Week {week}: {title}"
        slug = f"w{week:02d}-{primary_slug}"
        
        #resolve module_id
        module_id = None
        if module_code:
            module_id = await TopicService().resolve_module_id_by_code(module_code)
        
        return await TopicRepository.create(
            week=week,
            slug=slug,
            title=title,
            subtopics=subtopics_slugs,
            slides_key=slides_key,
            detected_topic=primary_slug,
            detected_subtopics=subtopics_slugs,
            slide_extraction_id=slide_extraction_id,
            module_code_slidesdeck=module_code,
            module_id=module_id,
        )

    async def resolve_module_id_by_code(self, module_code: str) -> Optional[str]:
        client = await get_supabase()
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
        try:
            response = await client.table("slide_extractions").select(
                "detected_topic, detected_subtopics"
            ).eq("id", slide_stack_id).execute()

            if not response.data:
                return []

            topics = []
            for record in response.data:
                if record.get("detected_topic"):
                    topics.append(record["detected_topic"])

                if record.get("detected_subtopics"):
                    if isinstance(record["detected_subtopics"], list):
                        topics.extend(record["detected_subtopics"])
                    elif isinstance(record["detected_subtopics"], str):
                        try:
                            import json
                            subtopics = json.loads(record["detected_subtopics"])
                            if isinstance(subtopics, list):
                                topics.extend(subtopics)
                        except:
                            pass

            return list(set(topics))
        except Exception as e:
            print(f"Error fetching topics from slide_extraction: {e}")
            return []

    async def get_slide_extraction_by_week(self, week_number: int, module_code: Optional[str] = None) -> List[Dict[str, Any]]:
        client = await get_supabase()
        try:
            query = client.table("slide_extractions").select(
                "id, module_id, week_number, detected_topic, detected_subtopics, module_code"
            ).eq("week_number", week_number)
            if module_code is not None:
                query = query.eq("module_code", str(module_code))
            response = await query.execute()
            return response.data if response.data else []
        except Exception as e:
            print(f"Error fetching slide extractions for week {week_number}: {e}")
            return []

    async def get_all_topics_for_week(self, week_number: int, module_code: Optional[str] = None) -> List[str]:
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
        client = await get_supabase()
        try:
            await client.table("topic").update({
                "slide_extraction_id": slide_extraction_id
            }).eq("id", topic_uuid).execute()
        except Exception as e:
            print(f"Error updating slide_extraction_id for topic {topic_uuid}: {e}")


# Global instance
topic_service = TopicService()