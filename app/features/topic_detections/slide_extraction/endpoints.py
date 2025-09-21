from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.adapters.nlp_spacy import extract_primary_topic
from .service import extract_slides_from_upload
from .repository_supabase import slide_extraction_supabase_repository
from ..topics.service import TopicService
from .topic_service import slide_extraction_topic_service

router = APIRouter(prefix="/topic-detections/slides", tags=["topic-detections:slides"]) 


def _flatten_texts(slides: Dict[int, List[str]]) -> List[str]:
    texts: List[str] = []
    for arr in slides.values():
        texts.extend(arr)
    return texts


@router.post("/extract")
async def extract_and_persist(
    file: UploadFile = File(...),
    week_number: int = Form(...),
    module_code: Optional[str] = Form(None),
) -> Dict[str, Any]:
    try:
        slides_map = await extract_slides_from_upload(file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    texts = _flatten_texts(slides_map)
    topic_key, subtopics = extract_primary_topic(texts)

    payload: Dict[str, Any] = {
        "filename": file.filename,
        "slides": slides_map,
        "detected_topic": topic_key,
        "detected_subtopics": subtopics,
        "week_number": week_number,
    }
    if module_code:
        payload["module_code"] = str(module_code)

    created = await slide_extraction_supabase_repository.create_extraction(payload)
    if not created:
        raise HTTPException(status_code=500, detail="Failed to save slide extraction")

    extraction_id = int(created.get("id"))

    if module_code:
        module_id = await slide_extraction_topic_service.resolve_module_id_by_code(module_code)
        if module_id is not None:
            await slide_extraction_supabase_repository.update_extraction(extraction_id, {"module_id": module_id})

    topic = await TopicService.create_from_slides(
        slides_url=file.filename,
        week=week_number,
        slide_texts=texts,
        slides_key=None,
        detected_topic=topic_key,
        detected_subtopics=subtopics,
        slide_extraction_id=extraction_id,
    )

    return {
        "extraction_id": extraction_id,
        "detected_topic": topic_key,
        "detected_subtopics": subtopics,
        "topic": topic,
        "week_number": week_number,
        "module_code": module_code,
    }


@router.get("/topics")
async def list_topics_for_module_week(module_code: str, week_number: int) -> Dict[str, Any]:
    try:
        topics = await slide_extraction_topic_service.get_topics_for_module_week(module_code, week_number)
        return {"module_code": module_code, "week_number": week_number, "topics": topics}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
