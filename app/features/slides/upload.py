from __future__ import annotations

import mimetypes
import logging
import inspect
from typing import Dict, Any, Optional

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


async def create_topic_from_extraction(
    extraction_row: dict,
    module_code: str,
):
    """Create a topic row from an existing persisted extraction and update the extraction.topic_id.

    Returns the topic row dict.
    """
    if not extraction_row:
        raise ValueError("extraction_row is required")

    # Unpack required fields
    sup_extraction_id = extraction_row.get("id")
    slides_map = extraction_row.get("slides", {})
    slide_texts = [line for _, lines in sorted(slides_map.items()) for line in lines]
    detected_topic = extraction_row.get("detected_topic")
    detected_subtopics = extraction_row.get("detected_subtopics") or []
    slides_key = extraction_row.get("slides_key")
    week = extraction_row.get("week_number")

    # Try TopicService then fallback to TopicRepository (same logic as single upload)
    try:
        topic = await TopicService.create_from_slides(
            slides_url=f"supabase://slides/{slides_key}",
            week=week,
            slide_texts=slide_texts,
            slides_key=slides_key,
            detected_topic=detected_topic,
            detected_subtopics=detected_subtopics,
            slide_extraction_id=sup_extraction_id,
            module_code=module_code,
        )
        topic_row = topic
    except Exception:
        logging.getLogger("slides").exception("TopicService.create_from_slides failed in batch, attempting direct create")
        try:
            topic_row = await TopicRepository.create(
                week=week,
                slug=f"w{week:02d}-{to_topic_slug(detected_topic or 'topic')}",
                title=f"Week {week}: {(detected_topic or 'Topic').replace('-', ' ').title()}",
                subtopics=detected_subtopics,
                slides_key=slides_key,
                detected_topic=detected_topic,
                detected_subtopics=detected_subtopics,
                slide_extraction_id=sup_extraction_id,
                module_code_slidesdeck=module_code,
                module_id=None,
            )
        except Exception:
            logging.getLogger("slides").exception("Direct TopicRepository.create also failed in batch")
            raise

    topic_uuid = topic_row.get("id") if topic_row else None
    if sup_extraction_id and topic_uuid:
        client = await get_supabase()
        resp = await client.table("slide_extractions").update({"topic_id": topic_uuid}).eq("id", sup_extraction_id).execute()
        data = getattr(resp, "data", None) or (resp.get("data") if isinstance(resp, dict) else None)
        if not data:
            logging.getLogger("slides").error("Failed to update slide_extractions.topic_id in batch for id=%s with topic_id=%s", sup_extraction_id, topic_uuid)
            raise RuntimeError("Failed to update slide_extractions.topic_id in batch")

    return topic_row


async def upload_slide_bytes(
    file_bytes: bytes,
    original_filename: str,
    topic_name: str,
    given_at_dt,             # datetime
    semester_start_date,     # date
    module_code: str,
    signed_url_ttl_sec: int = 900,
    create_topic: bool = True,
    semester_end_date: Optional[date] = None,
) -> Dict[str, Any]:
    key = build_slide_object_key(original_filename, topic_name, given_at_dt, semester_start_date, semester_end_date)
    content_type = mimetypes.guess_type(original_filename)[0] or "application/octet-stream"
    client = await get_supabase()

    # Prevent duplicate slide_extraction rows for the same week and module_code.
    # This enforces the invariant that a given (module_code, week_number) only has one extraction.
    try:
        exist_resp = await client.table("slide_extractions").select("id").eq("week_number", key.week).eq("module_code", module_code).limit(1).execute()
        exist_data = getattr(exist_resp, "data", None) or (exist_resp.get("data") if isinstance(exist_resp, dict) else None)
        if exist_data:
            # Raise a clear runtime error that the endpoint will surface as HTTP 400
            raise RuntimeError(f"Slides for week {key.week} already exist for module {module_code}")
    except Exception as e:
        # If we raised the duplicate error, re-raise to surface to caller. If the select itself failed for other reasons,
        # propagate that error so callers can see the failure instead of silently proceeding.
        if isinstance(e, RuntimeError) and str(e).startswith("Slides for week"):
            raise
        # Unexpected DB/select failure: raise to surface the issue to the endpoint caller
        raise
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
            # Detect topic locally (phrase/spaCy/heuristics) and augment with dynamic extractor
            slide_texts = [line for _, lines in sorted(slides_map.items()) for line in lines]
            # Defaults if NLP fails
            primary = topic_name or key.topic_slug or "Coding"
            subtopics = []
            try:
                det_primary, det_subs = extract_primary_topic(slide_texts)
            except Exception:
                logging.getLogger("slides").exception("Primary topic extraction failed; falling back to filename/topic param")
                det_primary, det_subs = (None, [])

            # Use dynamic extractor for additional candidate phrases (no env vars, dynamic models)
            try:
                from app.features.topic_detections.topics.extractor import extract_topics_from_text
                dyn_phrases, dyn_domain = extract_topics_from_text("\n".join(slide_texts), top_n=4)
            except Exception:
                dyn_phrases, dyn_domain = ([], "unknown")

            # Normalize primary and subtopics
            if det_primary:
                primary = det_primary
            if det_subs:
                subtopics = det_subs

            # Combine dynamic phrases: prefer coding-domain signals; otherwise augment conservatively
            try:
                dyn_slugs = []
                from app.features.topic_detections.topics.topic_service import _slugify as _t_slug
                for p in dyn_phrases:
                    if p:
                        dyn_slugs.append(_t_slug(p))
            except Exception:
                dyn_slugs = dyn_phrases or []

            if dyn_domain == "coding":
                for s in dyn_slugs:
                    if s not in subtopics and len(subtopics) < 3:
                        subtopics.append(s)
            else:
                # If adapter gave nothing useful, adopt the first dyn phrase as primary
                if (not det_primary or det_primary in ("topic", "topic")) and dyn_slugs:
                    primary = dyn_slugs[0] or primary
                    subtopics = dyn_slugs[1:4]
                else:
                    for s in dyn_slugs:
                        if s not in subtopics and len(subtopics) < 3:
                            subtopics.append(s)

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

            topic_uuid = None
            topic_row = None
            # Create topic only when requested (batch flow will call topic creation in a second phase)
            if create_topic:
                # Create Topic in a strict manner; if TopicService can't create it, try repository.create directly
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
