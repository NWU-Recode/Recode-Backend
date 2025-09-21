from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Body
from app.common.deps import get_current_user, CurrentUser
from .schemas import ChallengeSubmitRequest, ChallengeSubmitResponse, GetChallengeAttemptResponse, ChallengeAttemptQuestionStatus
from .service import challenge_service
from app.features.challenges.repository import challenge_repository
from app.features.challenges.claude_generator import (
    generate_challenges_with_claude,
    generate_tier_preview,
    generate_and_save_tier,
    fetch_topic_context_summary,
)
from app.features.challenges.semester_orchestrator import semester_orchestrator
from app.features.slides.pathing import parse_week_topic_from_filename
from typing import Dict, Any, Optional

router = APIRouter(prefix="/challenges", tags=["challenges"])

# ---------------------------------------------
# Generation of challenges for different 4 tiers
# ---------------------------------------------
class _GenerateReq:
    def __init__(self, slides_url: str, force: bool = False):
        self.slides_url = slides_url
        self.force = force


@router.post("/create")
async def create_from_slides(req: dict = Body(...), current_user: CurrentUser = Depends(get_current_user)):
    try:
        if getattr(current_user, "role", "student") != "lecturer":
            raise HTTPException(status_code=403, detail={"error_code": "E_FORBIDDEN", "message": "lecturer_only"})
        gr = _GenerateReq(slides_url=req.get("slides_url"), force=bool(req.get("force", False)))
        if not isinstance(gr.slides_url, str) or not gr.slides_url:
            raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_INPUT", "message": "slides_url required"})

        slide_stack_id, inferred_module_code = await _infer_slide_context(gr.slides_url)
        explicit_module_code = req.get("module_code")
        resolved_module_code = explicit_module_code or inferred_module_code

        week_number = req.get("week_number")
        if not week_number:
            if gr.slides_url.startswith("supabase://"):
                rest = gr.slides_url.split("://", 1)[1]
                parts = rest.split("/", 1)
                object_key = parts[1] if len(parts) == 2 else parts[0]
                filename = object_key.split("/")[-1]
            else:
                filename = gr.slides_url.split("/")[-1]
            derived, _ = parse_week_topic_from_filename(filename)
            if derived:
                week_number = int(derived)

        if not week_number:
            raise HTTPException(status_code=400, detail={
                "error_code": "E_INVALID_INPUT",
                "message": "week_number required or could not be derived from slides_url",
            })

        return await generate_challenges_with_claude(int(week_number), slide_stack_id, module_code=resolved_module_code)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error_code": "E_UNKNOWN", "message": str(e)})


@router.post("/{week_number}/create")
async def create_for_week(week_number: int, req: dict = Body(...), current_user: CurrentUser = Depends(get_current_user)):
    if getattr(current_user, "role", "student") != "lecturer":
        raise HTTPException(status_code=403, detail={"error_code": "E_FORBIDDEN", "message": "lecturer_only"})
    if week_number <= 0:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_WEEK", "message": "week must be > 0"})

    slide_stack_id = req.get("slide_stack_id")
    if slide_stack_id is not None and not isinstance(slide_stack_id, int):
        try:
            slide_stack_id = int(slide_stack_id)
        except Exception:
            slide_stack_id = None

    if slide_stack_id is None and isinstance(req.get("slides_url"), str):
        inferred_id, inferred_code = await _infer_slide_context(req.get("slides_url"))
        slide_stack_id = slide_stack_id or inferred_id
        req.setdefault("module_code", inferred_code)

    resolved_code = await _resolve_module_code_value(req.get("module_code"), req.get("module_id"))

    return await generate_challenges_with_claude(int(week_number), slide_stack_id, module_code=resolved_code)


@router.post("/publish/{week_number}")
async def publish_week_challenges(week_number: int, current_user: CurrentUser = Depends(get_current_user)):
    if getattr(current_user, "role", "student") != "lecturer":
        raise HTTPException(status_code=403, detail={"error_code":"E_FORBIDDEN","message":"lecturer_only"})
    if week_number <= 0:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_WEEK", "message": "week must be > 0"})
    res = await challenge_repository.publish_for_week(week_number)
    return {"week": week_number, "status": "published", "updated": res.get("updated", 0)}


@router.get("/semester/overview")
async def get_semester_overview(current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await semester_orchestrator.get_release_overview(str(current_user.id))
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error_code":"E_UNKNOWN","message":str(e)})


# -----------------------------
# TIER-SPECIFIC GENERATION ENDPOINTS



async def _resolve_module_code_value(module_code: Optional[str], module_id: Optional[int]) -> Optional[str]:
    if module_code:
        return module_code
    if module_id is None:
        return None
    try:
        client = await get_supabase()
        resp = await client.table("modules").select("code").eq("id", module_id).limit(1).execute()
        rows = resp.data or []
        if rows:
            code = rows[0].get("code")
            if code:
                return str(code)
    except Exception:
        pass
    return None


async def _infer_slide_context(slides_url: Optional[str]) -> tuple[Optional[int], Optional[str]]:
    if not slides_url:
        return None, None
    if slides_url.startswith("supabase://"):
        _, _, rest = slides_url.partition("://")
        _, _, object_key = rest.partition("/")
        if object_key:
            try:
                client = await get_supabase()
                query = client.table("slide_extractions").select("id, module_code").eq("slides_key", object_key)
                try:
                    query = query.order("id", desc=True)
                except Exception:
                    pass
                resp = await query.limit(1).execute()
                rows = resp.data or []
                if rows:
                    row = rows[0]
                    sid = row.get("id")
                    module_code = row.get("module_code")
                    if isinstance(sid, str) and sid.isdigit():
                        sid = int(sid)
                    return sid, module_code
            except Exception:
                pass
    digits = "".join(ch for ch in slides_url if ch.isdigit())
    if digits:
        try:
            return int(digits), None
        except ValueError:
            pass
    return None, None


@router.post("/generate/{tier}/save")
async def generate_and_save(
    tier: str,
    module_code: Optional[str] = Body(None, embed=True),
    module_id: Optional[int] = Body(None, embed=True),
    week_number: int = Body(..., embed=True),
    slide_stack_id: Optional[int] = Body(None, embed=True),
    current_user: CurrentUser = Depends(get_current_user)
):
    if getattr(current_user, "role", "student") != "lecturer":
        raise HTTPException(status_code=403, detail={"error_code": "E_FORBIDDEN", "message": "lecturer_only"})
    if tier not in {"base", "ruby", "emerald", "diamond", "common"}:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_TIER", "message": "invalid tier"})

    resolved_code = await _resolve_module_code_value(module_code, module_id)
    result = await generate_and_save_tier(tier, week_number, slide_stack_id=slide_stack_id, module_code=resolved_code)
    return {"status": "saved", **result}


@router.post("/generate/base")
async def generate_base_challenge(
    module_code: Optional[str] = Body(None, embed=True),
    module_id: Optional[int] = Body(None, embed=True),
    week_number: int = Body(..., embed=True),
    current_user: CurrentUser = Depends(get_current_user)
):
    if getattr(current_user, "role", "student") != "lecturer":
        raise HTTPException(status_code=403, detail={"error_code": "E_FORBIDDEN", "message": "lecturer_only"})
    resolved_code = await _resolve_module_code_value(module_code, module_id)
    preview = await generate_tier_preview("base", week_number, module_code=resolved_code)
    return {"tier": "base", **preview}


@router.post("/generate/ruby")
async def generate_ruby_challenge(
    module_code: Optional[str] = Body(None, embed=True),
    module_id: Optional[int] = Body(None, embed=True),
    week_number: int = Body(..., embed=True),
    current_user: CurrentUser = Depends(get_current_user)
):
    if getattr(current_user, "role", "student") != "lecturer":
        raise HTTPException(status_code=403, detail={"error_code": "E_FORBIDDEN", "message": "lecturer_only"})
    resolved_code = await _resolve_module_code_value(module_code, module_id)
    preview = await generate_tier_preview("ruby", week_number, module_code=resolved_code)
    return {"tier": "ruby", **preview}


@router.post("/generate/emerald")
async def generate_emerald_challenge(
    module_code: Optional[str] = Body(None, embed=True),
    module_id: Optional[int] = Body(None, embed=True),
    week_number: int = Body(..., embed=True),
    current_user: CurrentUser = Depends(get_current_user)
):
    if getattr(current_user, "role", "student") != "lecturer":
        raise HTTPException(status_code=403, detail={"error_code": "E_FORBIDDEN", "message": "lecturer_only"})
    resolved_code = await _resolve_module_code_value(module_code, module_id)
    preview = await generate_tier_preview("emerald", week_number, module_code=resolved_code)
    return {"tier": "emerald", **preview}


@router.post("/generate/diamond")
async def generate_diamond_challenge(
    module_code: Optional[str] = Body(None, embed=True),
    module_id: Optional[int] = Body(None, embed=True),
    week_number: int = Body(..., embed=True),
    current_user: CurrentUser = Depends(get_current_user)
):
    if getattr(current_user, "role", "student") != "lecturer":
        raise HTTPException(status_code=403, detail={"error_code": "E_FORBIDDEN", "message": "lecturer_only"})
    resolved_code = await _resolve_module_code_value(module_code, module_id)
    preview = await generate_tier_preview("diamond", week_number, module_code=resolved_code)
    return {"tier": "diamond", **preview}


@router.get("/generate/preview-topics")
async def preview_topics(
    module_code: Optional[str] = None,
    module_id: Optional[int] = None,
    week_number: int = 1,
    current_user: CurrentUser = Depends(get_current_user)
):
    if getattr(current_user, "role", "student") != "lecturer":
        raise HTTPException(status_code=403, detail={"error_code": "E_FORBIDDEN", "message": "lecturer_only"})
    resolved_code = await _resolve_module_code_value(module_code, module_id)
    summary = await fetch_topic_context_summary(week_number, module_code=resolved_code)
    topics_list = summary.get("topics_list", "")
    split_topics = [item.strip() for item in topics_list.split(",") if item.strip()]
    return {
        "module_code": summary.get("module_code") or resolved_code,
        "week_number": week_number,
        "topic_id": summary.get("topic_id"),
        "topics": split_topics,
    }
