from __future__ import annotations

import mimetypes
import logging
import inspect
from typing import Dict, Any

from .pathing import build_slide_object_key, to_topic_slug
from app.DB.supabase import get_supabase
from app.features.topic_detections.slide_extraction.pptx_extraction import extract_pptx_text
from io import BytesIO
from app.features.topic_detections.topics.topic_service import TopicService, topic_service
from app.features.topic_detections.topics.repository import TopicRepository
from datetime import datetime, timezone
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
    sup_row = None
    try:
        if original_filename.lower().endswith(".pptx"):
            slides_map = extract_pptx_text(BytesIO(file_bytes))
            # Detect topic locally (phrase/spaCy/heuristics)
            slide_texts = [line for _, lines in sorted(slides_map.items()) for line in lines]
            # Defaults if NLP fails
            primary = topic_name or key.topic_slug or "Coding"
            subtopics = []
            try:
                det_primary, det_subs = extract_primary_topic(slide_texts)
                if det_primary:
                    primary = det_primary
                if det_subs:
                    subtopics = det_subs
            except Exception:
                logging.getLogger("slides").exception("Primary topic extraction failed; falling back to filename/topic param")

            # Only filter noisy subtopics when the primary is a CS topic; preserve non-CS primaries/subtopics
            try:
                text_all = "\n".join(slide_texts).lower()
                from app.adapters.nlp_spacy import PHRASES

                CS_ALLOWED = set(PHRASES.keys()) | {"data-structures", "variables-and-loops", "control-flow", "functions-and-recursion", "algorithms"}

                def _is_cs_candidate(tok: str) -> bool:
                    # exact allowed keys
                    if tok in CS_ALLOWED:
                        return True
                    # common CS substrings
                    substrings = (
                        "list", "array", "tuple", "string", "dict", "dictionary", "set",
                        "stack", "queue", "graph", "tree", "loop", "for-loop", "while",
                        "function", "recursion", "sort", "search", "algorithm", "complexity",
                        "variable", "operator", "conditional",
                    )
                    for s in substrings:
                        if s in tok:
                            return True
                    return False

                primary_norm = to_topic_slug(primary) if primary else None

                # If primary looks like CS, filter subtopics. Otherwise preserve adapter output.
                if primary_norm and _is_cs_candidate(primary_norm):
                    filtered_subs: list[str] = []
                    for s in subtopics:
                        s_norm = to_topic_slug(s)
                        if _is_cs_candidate(s_norm):
                            filtered_subs.append(s_norm)
                    subtopics = filtered_subs
                    primary = primary_norm
                else:
                    # Keep non-CS primary and its subtopics as returned by the adapter
                    primary = primary_norm or to_topic_slug(primary or key.topic_slug or "Coding")
            except Exception:
                logging.getLogger("slides").debug("Filtering/normalization of topic/subtopics failed")
            
            # Persist slide extraction to Supabase first (so extraction row exists)
            now_iso = datetime.now(timezone.utc).isoformat()
            extraction_payload = {
                "filename": original_filename,
                "slides_key": key.object_key,
                "slides": slides_map,
                "detected_topic": primary,
                "detected_subtopics": subtopics,
                "week_number": key.week,
                "module_code": module_code,
                "created_at": now_iso,
            }
            # Strictly raise if persistence fails so the upload endpoint surfaces errors
            sup_row = await slide_extraction_supabase_repository.create_extraction(extraction_payload)
            sup_extraction_id = sup_row.get("id")
            extraction_id = sup_extraction_id

            # Create Topic and reference the extraction (create topic after extraction)
            # Create Topic in a strict manner; if TopicService can't create it, try repository.create directly
            topic_uuid = None
            topic_row = None
            try:
                topic = await TopicService.create_from_slides(
                    slides_url=f"supabase://slides/{key.object_key}",
                    week=key.week,
                    slide_texts=slide_texts,
                    slides_key=key.object_key,
                    detected_topic=primary,
                    detected_subtopics=subtopics,
                    slide_extraction_id=sup_extraction_id,
                    module_code=module_code,
                )
                topic_row = topic
            except Exception:
                # Try a direct repository create as a fallback to ensure a topic row exists
                logging.getLogger("slides").exception("TopicService.create_from_slides failed, attempting direct create")
                try:
                    topic_row = await TopicRepository.create(
                        week=key.week,
                        slug=f"w{key.week:02d}-{to_topic_slug(primary or key.topic_slug or 'topic')}",
                        title=f"Week {key.week}: {(primary or 'Topic').replace('-', ' ').title()}",
                        subtopics=subtopics,
                        slides_key=key.object_key,
                        detected_topic=primary,
                        detected_subtopics=subtopics,
                        slide_extraction_id=sup_extraction_id,
                        module_code_slidesdeck=module_code,
                        module_id=None,
                    )
                except Exception:
                    logging.getLogger("slides").exception("Direct TopicRepository.create also failed")
                    # Surface error to caller rather than silently continuing
                    raise

            topic_uuid = topic_row.get("id") if topic_row else None

            # If we have both extraction and topic, update the extraction row to point to the topic
            # Update the extraction row to set topic_id; if this fails raise an error
            if sup_extraction_id and topic_uuid:
                client = await get_supabase()
                resp = await client.table("slide_extractions").update({"topic_id": topic_uuid}).eq("id", sup_extraction_id).execute()
                # supabase-py returns dict-like responses; ensure data exists
                data = getattr(resp, "data", None) or (resp.get("data") if isinstance(resp, dict) else None)
                if not data:
                    logging.getLogger("slides").error("Failed to update slide_extractions.topic_id for id=%s with topic_id=%s", sup_extraction_id, topic_uuid)
                    raise RuntimeError("Failed to update slide_extractions.topic_id")
    except Exception as e:
        # Surface extraction/topic errors to caller so callers can decide fail vs. continue
        logging.getLogger("slides").exception("Slide extraction/topic detection failed: %s", str(e))
        raise

    # Ensure detection variables exist for non-pptx or failure paths
    slide_texts = locals().get("slide_texts", [])
    slides_map = locals().get("slides_map", {})
    primary = locals().get("primary", topic_name or key.topic_slug or "Coding")
    subtopics = locals().get("subtopics", [])
    now_iso = locals().get("now_iso", datetime.now(timezone.utc).isoformat())

    # Ensure topic_row is present (best-effort) so response never contains null
    if topic_row is None:
        try:
            # Build a conservative fallback topic slug
            fallback_slug = key.topic_slug or (primary or "Coding")
            fallback_slug = to_topic_slug(fallback_slug)
        except Exception:
            fallback_slug = to_topic_slug(primary or key.topic_slug or "Coding")
        topic_row = {
            "id": None,
            "week": key.week,
            "slug": f"w{key.week:02d}-{fallback_slug}",
            "title": f"Week {key.week}: {(primary or fallback_slug).replace('-', ' ').title()}",
            "subtopics": subtopics,
            "slides_key": key.object_key,
            "detected_topic": primary,
            "detected_subtopics": subtopics,
            "slide_extraction_id": sup_extraction_id,
            "module_code_slidesdeck": module_code,
            "module_id": None,
        }

    # Build a normalized extraction dict to return (prefer DB row when available)
    extraction_data = None
    if sup_row:
        extraction_data = sup_row
    else:
        extraction_data = {
            "id": extraction_id,
            "filename": original_filename,
            "slides_key": key.object_key,
            "slides": slides_map,
            "detected_topic": primary,
            "detected_subtopics": subtopics,
            "week_number": key.week,
            "module_code": module_code,
            "created_at": now_iso if 'now_iso' in locals() else None,
        }

    return {
        "season": key.season,
        "week": key.week,
        "topic_slug": key.topic_slug,
        "object_key": key.object_key,
        "slides_url": f"supabase://slides/{key.object_key}",
        "signed_url": signed_url,
        "extraction": extraction_data,
        "topic": topic_row,
    }
