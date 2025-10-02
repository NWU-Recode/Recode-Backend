from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from datetime import datetime, date, time, timedelta
import os
from typing import Any, List, Optional, Tuple
import asyncio
import logging

from app.common.deps import get_current_user, CurrentUser, require_role
from .upload import upload_slide_bytes
from .upload import create_topic_from_extraction
from .pathing import parse_week_topic_from_filename, SA_TZ
from app.features.admin.repository import ModuleRepository
# Lazy import generate_and_save_tier where it's used to avoid import-time errors
generate_and_save_tier = None
from app.features.challenges.repository import challenge_repository
from app.demo.timekeeper import apply_demo_offset_to_semester_start

DEFAULT_SEMESTER_WEEKS = 12


def _read_semester_start() -> date:
    val = os.environ.get("SEMESTER_START")
    if not val:
        return date(2025, 8, 31)
    try:
        # accept YYYY-MM-DD
        return date.fromisoformat(val)
    except Exception:
        # fallback to default if parsing fails
        return date(2025, 8, 31)


def _coerce_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.split("T")[0])
        except Exception:
            return None
    return None


def _semester_env_window() -> Tuple[date, date]:
    start = _read_semester_start()
    end = start + timedelta(weeks=DEFAULT_SEMESTER_WEEKS) - timedelta(days=1)
    return start, end


async def _resolve_semester_window(module_code: Optional[str]) -> Tuple[date, Optional[date], Optional[str]]:
    env_start, env_end = _semester_env_window()
    resolved_start = env_start
    resolved_end: Optional[date] = env_end
    semester_id: Optional[str] = None

    window: Optional[dict] = None
    if module_code:
        try:
            window = await ModuleRepository.get_semester_window_for_module_code(module_code)
        except Exception:
            window = None
    if not window or not window.get("start_date"):
        try:
            current = await ModuleRepository.get_current_semester()
        except Exception:
            current = None
        if current:
            window = {
                "start_date": current.get("start_date"),
                "end_date": current.get("end_date"),
                "semester_id": current.get("id"),
            }
    if window:
        maybe_start = _coerce_date(window.get("start_date"))
        maybe_end = _coerce_date(window.get("end_date"))
        if maybe_start:
            resolved_start = maybe_start
        if maybe_end:
            resolved_end = maybe_end
        raw_semester_id = window.get("semester_id") or window.get("id")
        if raw_semester_id not in (None, ""):
            semester_id = str(raw_semester_id)

    return resolved_start, resolved_end, semester_id



router = APIRouter(prefix="/slides", tags=["slides"])

@router.post(
    "/upload",
    summary="Upload slides, extract topics and trigger challenge generation",
    description=(
        "Upload a slide file for a module. The server will extract topics from the file, "
        "create a topic record, and trigger automatic challenge generation for the week computed "
        "from the provided datetime (or now) relative to the module's semester start. "
        "Generation rules: base always; ruby on weeks 2,6,10; emerald on weeks 4,8; diamond on week 12. "
        "Optionally returns a signed URL for the uploaded file when requested."
    ),
)
async def upload_slide(
    module_code: str = Query(..., description="Module code for the slides"),
    topic_name: str | None = Query(None, description="Optional topic override; inferred from filename/slides if omitted"),
    given_at_iso: str | None = Query(None, description="Optional ISO datetime; inferred from filename week or uses now if omitted"),
    include_signed_url: bool = Query(False, description="Include a short-lived signed URL in the response (not stored)"),
    signed_ttl_sec: int = Query(900, ge=60, le=86400, description="TTL (seconds) for the signed URL if requested"),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_role('admin','lecturer')),
):
    try:
        data = await file.read()
        # Topic may still be provided but we DO NOT use filename week to determine week.
        # Always derive the week from the provided datetime (given_at_iso) or now, relative to current semester start.
        _, parsed_topic = parse_week_topic_from_filename(file.filename)
        tn = topic_name or parsed_topic or "Coding"
        if given_at_iso:
            given_at_dt = datetime.fromisoformat(given_at_iso)
        else:
            # Use now; week will be derived from SEMESTER_START in pathing.build_slide_object_key
            given_at_dt = datetime.now(tz=SA_TZ)
        # Resolve the active semester window for this module (DB first, env fallback)
        raw_semester_start, raw_semester_end, semester_id = await _resolve_semester_window(module_code)
        semester_start = apply_demo_offset_to_semester_start(raw_semester_start, module_code)
        semester_end = raw_semester_end
        if semester_end and raw_semester_start:
            semester_end = semester_end + (semester_start - raw_semester_start)
        out = await upload_slide_bytes(
            data,
            file.filename,
            tn,
            given_at_dt,
            semester_start,
            module_code=module_code,
            signed_url_ttl_sec=signed_ttl_sec,
            semester_end_date=semester_end,
        )
        if isinstance(out, dict):
            out.setdefault("semester_context", {
                "module_code": module_code,
                "semester_id": semester_id,
                "start_date": semester_start.isoformat(),
                "end_date": semester_end.isoformat() if semester_end else None,
            })
        # After successful extraction/topic creation, trigger challenge generation according to week rules.
        try:
            week_num = None
            extraction = out.get("extraction") if isinstance(out, dict) else None
            if extraction and isinstance(extraction, dict):
                week_num = int(extraction.get("week_number") or out.get("week") or 0)
                slide_stack_id = extraction.get("id")
            else:
                week_num = int(out.get("week") or 0)
                slide_stack_id = None
            lecturer_id = int(getattr(current_user, "id", 0) or 0)
            if week_num and 0 < week_num <= 12:
                # Import generator lazily to avoid importing heavy/fragile modules at app import time
                from importlib import import_module
                gen_mod = import_module("app.features.challenges.challenge_pack_generator")
                generate_and_save_tier = getattr(gen_mod, "generate_and_save_tier")
                await generate_and_save_tier("base", week_num, slide_stack_id=slide_stack_id, module_code=module_code, lecturer_id=lecturer_id, semester_id=semester_id)
                optional_generators = []
                if week_num % 2 == 0:
                    optional_generators.append(
                        generate_and_save_tier("ruby", week_num, slide_stack_id=slide_stack_id, module_code=module_code, lecturer_id=lecturer_id, semester_id=semester_id)
                    )
                if week_num % 4 == 0:
                    optional_generators.append(
                        generate_and_save_tier("emerald", week_num, slide_stack_id=slide_stack_id, module_code=module_code, lecturer_id=lecturer_id, semester_id=semester_id)
                    )
                if week_num == 12:
                    optional_generators.append(
                        generate_and_save_tier("diamond", week_num, slide_stack_id=slide_stack_id, module_code=module_code, lecturer_id=lecturer_id, semester_id=semester_id)
                    )
                for coro in optional_generators:
                    try:
                        await coro
                    except Exception as gen_exc:
                        logging.getLogger("slides").exception("Challenge generation failed for week %s tier task: %s", week_num, gen_exc)
                # publish the week challenges we just generated
                try:
                    await challenge_repository.publish_for_week(week_num)
                except Exception:
                    logging.getLogger("slides").exception("Failed to publish generated challenges for week %s", week_num)
        except Exception:
            logging.getLogger("slides").exception("Automatic challenge generation failed for uploaded slide")
        # Do not expose signed URL unless explicitly requested
        if not include_signed_url:
            out.pop("signed_url", None)
        return out
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/batch-upload",
    summary="Batch upload slides, create topics and optionally assign weeks by file order",
    description=(
        "Upload multiple slide files for a module. By default each file is processed with the current datetime, "
        "but when `assign_weeks_by_order=true` files are assigned successive weeks starting at the module's semester start. "
        "Each uploaded file will result in an extraction and topic creation, and will trigger challenge generation for the resolved week."
    ),
)
async def batch_upload_slides(
    module_code: str = Query(..., description="Module code for all slides"),
    topic_name: str | None = Query(None, description="Optional topic override; inferred from filename/slides if omitted"),
    include_signed_url: bool = Query(False, description="Include a short-lived signed URL in the response (not stored)"),
    signed_ttl_sec: int = Query(900, ge=60, le=86400, description="TTL (seconds) for the signed URL if requested"),
    files: List[UploadFile] = File(...),
    current_user: CurrentUser = Depends(require_role('admin','lecturer')),
    assign_weeks_by_order: bool = Query(True, description="If true, assign weeks sequentially starting at SEMESTER_START based on file order (useful for batch uploads)") ,
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    base_semester_start, base_semester_end, semester_id = await _resolve_semester_window(module_code)
    semester_start = apply_demo_offset_to_semester_start(base_semester_start, module_code)
    semester_end = base_semester_end
    if semester_end:
        semester_end = semester_end + (semester_start - base_semester_start)

    # Limit concurrency to prevent overwhelming the server/storage
    semaphore = asyncio.Semaphore(14)  # Max 14 concurrent uploads
    
    async def process_file(file: UploadFile):
        async with semaphore:
            try:
                data = await file.read()
                # Topic may still be provided but we DO NOT use filename week to determine week.
                _, parsed_topic = parse_week_topic_from_filename(file.filename)
                tn = topic_name or parsed_topic or "Coding"
                # Always derive the week from given_at_dt (provided or now) relative to SEMESTER_START
                # For batch uploads we may want to assign weeks by order later; default behavior here
                # is to use now. The outer dispatcher will override given_at_dt when assign_weeks_by_order=True.
                given_at_dt = datetime.now(tz=SA_TZ)
                result = await upload_slide_bytes(
                    data,
                    file.filename,
                    tn,
                    given_at_dt,
                    semester_start,
                    module_code=module_code,
                    signed_url_ttl_sec=signed_ttl_sec,
                    semester_end_date=semester_end,
                )
                if isinstance(result, dict):
                    result.setdefault("semester_context", {
                        "module_code": module_code,
                        "semester_id": semester_id,
                        "start_date": semester_start.isoformat(),
                        "end_date": semester_end.isoformat() if semester_end else None,
                    })
                # Do not expose signed URL unless explicitly requested
                if not include_signed_url:
                    result.pop("signed_url", None)
                return {"filename": file.filename, "success": True, "data": result}
            except Exception as e:
                return {"filename": file.filename, "success": False, "error": str(e)}
    
    # If assign_weeks_by_order is True, compute given_at_dt for each file sequentially
    # so uploads are stamped to successive weeks starting at SEMESTER_START.
    if assign_weeks_by_order:
        # Use file order as provided. Week 1 corresponds to SEMESTER_START.
        tasks = []
        for idx, file in enumerate(files):
            # compute week offset (0-based index -> week 1..)
            week_offset = idx
            target_date = semester_start + timedelta(weeks=week_offset)
            given_at_dt = datetime.combine(target_date, time(10, 0)).astimezone(SA_TZ)

            async def process_with_given(file=file, given_at_dt=given_at_dt):
                async with semaphore:
                    try:
                        data = await file.read()
                        _, parsed_topic = parse_week_topic_from_filename(file.filename)
                        tn = topic_name or parsed_topic or "Coding"
                        result = await upload_slide_bytes(
                            data,
                            file.filename,
                            tn,
                            given_at_dt,
                            semester_start,
                            module_code=module_code,
                            signed_url_ttl_sec=signed_ttl_sec,
                            semester_end_date=semester_end,
                        )
                        if isinstance(result, dict):
                            result.setdefault("semester_context", {
                                "module_code": module_code,
                                "semester_id": semester_id,
                                "start_date": semester_start.isoformat(),
                                "end_date": semester_end.isoformat() if semester_end else None,
                            })
                        if not include_signed_url:
                            result.pop("signed_url", None)
                        return {"filename": file.filename, "success": True, "data": result}
                    except Exception as e:
                        return {"filename": file.filename, "success": False, "error": str(e)}
            tasks.append(process_with_given())
        results = await asyncio.gather(*tasks, return_exceptions=True)
    else:
        # Process all files concurrently with controlled concurrency
        # Phase 1: persist all extractions without creating topics
        tasks = [process_file(file) for file in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect successful extractions for phase 2
    extractions = []  # list of tuples (filename, extraction_dict)
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({"filename": files[i].filename, "success": False, "error": str(result)})
        else:
            processed_results.append(result)
            if result.get("success") and isinstance(result.get("data"), dict):
                # extraction is in result['data']['extraction']
                extraction = result["data"].get("extraction")
                if extraction and isinstance(extraction, dict):
                    extractions.append((result["filename"], extraction))
    
    # Phase 2: create topics from persisted extractions
    topic_tasks = []
    for filename, extraction in extractions:
        topic_tasks.append(asyncio.create_task(create_topic_from_extraction(extraction, module_code)))

    topic_results = []
    if topic_tasks:
        topic_results = await asyncio.gather(*topic_tasks, return_exceptions=True)

    # Merge topic creation results back into processed_results
    # For simplicity, match by filename order collected in extractions
    for idx, tr in enumerate(topic_results):
        fname = extractions[idx][0]
        for pr in processed_results:
            if pr.get("filename") == fname:
                if isinstance(tr, Exception):
                    pr["topic_created"] = False
                    pr["topic_error"] = str(tr)
                else:
                    pr["topic_created"] = True
                    pr["topic"] = tr
                break

    return {"results": processed_results}
