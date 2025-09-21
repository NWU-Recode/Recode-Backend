from __future__ import annotations

import mimetypes
import logging
import inspect
from typing import Dict, Any

from .pathing import build_slide_object_key
from app.DB.supabase import get_supabase
from app.features.topic_detections.slide_extraction.pptx_extraction import extract_pptx_text
from io import BytesIO
from app.features.topic_detections.topics.topic_service import TopicService
from app.adapters.nlp_spacy import extract_primary_topic
from app.features.topic_detections.slide_extraction.repository_supabase import slide_extraction_supabase_repository


async def _maybe_await(val):
    return await val if inspect.isawaitable(val) else val


async def upload_slide_bytes(
    file_bytes: bytes,
    original_filename: str,
    topic_name: str,
    given_at_dt,             # datetime
    semester_start_date,     # date
    module_code: str,
    signed_url_ttl_sec: int = 900,
) -> Dict[str, Any]:
    key = build_slide_object_key(original_filename, topic_name, given_at_dt, semester_start_date)
    content_type = mimetypes.guess_type(original_filename)[0] or "application/octet-stream"

    client = await get_supabase()
    bucket = client.storage.from_("slides")
    # Upload bytes (simple path first to avoid option mismatch across client versions)
    try:
        upload_res = await _maybe_await(
            bucket.upload(
                path=key.object_key,
                file=file_bytes,
            )
        )
        if isinstance(upload_res, dict) and upload_res.get("error"):
            logging.getLogger("slides").error("Supabase upload error: %s", upload_res.get("error"))
    except Exception as e:
        logging.getLogger("slides").exception("Upload to Supabase failed: %s", str(e))
    # Signed URL (if private bucket) — tolerate failures
    signed = None
    try:
        signed = await _maybe_await(bucket.create_signed_url(key.object_key, expires_in=signed_url_ttl_sec))
    except Exception as e:
        logging.getLogger("slides").warning("Create signed URL failed for %s: %s", key.object_key, str(e))
    # supabase-py may return 'signedURL' or 'signed_url'
    signed_url = None
    if isinstance(signed, dict):
        signed_url = signed.get("signedURL") or signed.get("signed_url") or signed.get("signedUrl")
    # Optional: extract text for PPTX and persist a record for later pipelines
    # Use Supabase for slide_extractions to avoid double-writes
    extraction_id: int | None = None
    sup_extraction_id: int | None = None
    detected = None
    topic_row = None
    try:
        if original_filename.lower().endswith(".pptx"):
            slides_map = extract_pptx_text(BytesIO(file_bytes))
            # Detect topic locally (phrase/spaCy/heuristics)
            slide_texts = [line for _, lines in sorted(slides_map.items()) for line in lines]
            primary, subtopics = extract_primary_topic(slide_texts)
            
            # Create Topic first (Supabase)
            topic = await TopicService.create_from_slides(
                slides_url=f"supabase://slides/{key.object_key}",
                week=key.week,
                slide_texts=slide_texts,
                slides_key=key.object_key,
                detected_topic=primary,
                detected_subtopics=subtopics,
                slide_extraction_id=None,  # Will update later
                module_code=module_code,
            )
            topic_row = topic
            topic_uuid = topic.get("id")
            
            # Persist slide extraction to Supabase with topic reference
            try:
                sup_row = await slide_extraction_supabase_repository.create_extraction({
                    "filename": original_filename,
                    "slides_key": key.object_key,
                    "slides": slides_map,
                    "detected_topic": primary,
                    "detected_subtopics": subtopics,
                    "week_number": key.week,
                    "module_code": module_code,
                    "topic_id": topic_uuid,
                })
                if sup_row:
                    sup_extraction_id = sup_row.get("id")
                    # Use Supabase row id as extraction_id to avoid confusion
                    extraction_id = sup_extraction_id
                    
                    # Update topic with slide_extraction_id
                    if topic_uuid:
                        await TopicService.update_slide_extraction_id(topic_uuid, sup_extraction_id)
            except Exception:
                pass
    except Exception as e:
        # Non-fatal: extraction/topic detection is best-effort, but log for visibility
        logging.getLogger("slides").exception("Slide extraction/topic detection failed: %s", str(e))

    return {
        "season": key.season,
        "week": key.week,
        "topic_slug": key.topic_slug,
        "object_key": key.object_key,
        "slides_url": f"supabase://slides/{key.object_key}",
        "signed_url": signed_url,
        "extraction_id": extraction_id,
        "topic": topic_row,
    }
