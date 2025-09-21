from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Body
from app.common.deps import get_current_user, CurrentUser
from .schemas import ChallengeSubmitRequest, ChallengeSubmitResponse, GetChallengeAttemptResponse, ChallengeAttemptQuestionStatus
from .service import challenge_service
from app.features.challenges.repository import challenge_repository
from app.features.topic_detections.repository import question_repository 
from app.features.challenges.generation import generate_week_challenges
from app.features.challenges.claude_generator import generate_challenges_with_claude
from app.features.challenges.semester_orchestrator import semester_orchestrator
from app.features.slides.pathing import parse_week_topic_from_filename
import re
from typing import Dict, Any, Optional

router = APIRouter(prefix="/challenges", tags=["challenges"])

@router.post('/{challenge_id}/submit', response_model=ChallengeSubmitResponse)
async def submit_challenge(challenge_id: str, current_user: CurrentUser = Depends(get_current_user)):
    try:
        from .schemas import ChallengeSubmitRequest
        req = ChallengeSubmitRequest(challenge_id=challenge_id, items=None)
        return await challenge_service.submit(req, str(current_user.id))
    except ValueError as ve:
        msg = str(ve)
        if msg.startswith("challenge_already_submitted"):
            raise HTTPException(status_code=409, detail={"error_code":"E_CONFLICT","message":"challenge_already_submitted"})
        if msg.startswith("challenge_not_configured"):
            raise HTTPException(status_code=409, detail={"error_code":"E_INVALID_STATE","message":msg})
        if msg.startswith("missing_questions:"):
            missing = msg.split(":",1)[1].split(',') if ':' in msg else []
            raise HTTPException(status_code=400, detail={"error_code":"E_INVALID_INPUT","message":"missing_questions","missing_question_ids":missing})
        if msg.startswith("challenge_expired"):
            raise HTTPException(status_code=409, detail={"error_code":"E_CONFLICT","message":"challenge_expired"})
        raise HTTPException(status_code=400, detail={"error_code":"E_INVALID_INPUT","message":msg})
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error_code":"E_UNKNOWN","message":str(e)})

@router.get('/{challenge_id}/attempt', response_model=GetChallengeAttemptResponse)
async def get_challenge_attempt(challenge_id: str, current_user: CurrentUser = Depends(get_current_user)):
    try:
        user_id = str(current_user.id)
        attempt = await challenge_repository.create_or_get_open_attempt(challenge_id, user_id)
        snapshot = attempt.get("snapshot_questions") or []
        latest_attempts = await question_repository.list_latest_attempts_for_challenge(challenge_id, user_id)
        index = {a.get("question_id"): a for a in latest_attempts}
        questions: list[ChallengeAttemptQuestionStatus] = []
        for snap in snapshot:
            qid = snap["question_id"]
            att = index.get(qid)
            if not att:
                questions.append(ChallengeAttemptQuestionStatus(question_id=qid, status="unattempted"))
            else:
                status = "passed" if att.get("is_correct") else "failed"
                questions.append(ChallengeAttemptQuestionStatus(
                    question_id=qid,
                    status=status,
                    last_submitted_at=att.get("updated_at") or att.get("created_at"),
                    token=att.get("judge0_token")
                ))
        return GetChallengeAttemptResponse(
            challenge_attempt_id=attempt["id"],
            challenge_id=attempt["challenge_id"],
            status=attempt.get("status"),
            started_at=attempt.get("started_at"),
            deadline_at=attempt.get("deadline_at"),
            submitted_at=attempt.get("submitted_at"),
            snapshot_question_ids=[s["question_id"] for s in snapshot],
            questions=questions
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error_code":"E_INVALID_INPUT","message":str(e)})


# -----------------------------
# GENERATION (moved from weeks)
# -----------------------------
class _GenerateReq:
    def __init__(self, slides_url: str, force: bool = False):
        self.slides_url = slides_url
        self.force = force


@router.post("/create")
async def create_from_slides(req: dict = Body(...), current_user: CurrentUser = Depends(get_current_user)):
    try:
        if getattr(current_user, "role", "student") != "lecturer":
            raise HTTPException(status_code=403, detail={"error_code":"E_FORBIDDEN","message":"lecturer_only"})
        gr = _GenerateReq(slides_url=req.get("slides_url"), force=bool(req.get("force", False)))
        if not isinstance(gr.slides_url, str) or not gr.slides_url:
            raise HTTPException(status_code=400, detail={"error_code":"E_INVALID_INPUT","message":"slides_url required"})

        # Extract slide_stack_id from slides_url if it's a Supabase URL
        slide_stack_id = None
        if gr.slides_url.startswith("supabase://"):
            try:
                # Extract ID from URL pattern
                parts = gr.slides_url.split("/")
                for part in parts:
                    if part.isdigit():
                        slide_stack_id = int(part)
                        break
            except:
                pass

        week_number = req.get("week_number")
        if not week_number:
            # Try to extract from filename or URL
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
                "message": "week_number required or could not be derived from slides_url"
            })

        # Use Claude-based generation
        return await generate_challenges_with_claude(week_number, slide_stack_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error_code":"E_UNKNOWN","message":str(e)})


@router.post("/{week_number}/create")
async def create_for_week(week_number: int, req: dict = Body(...), current_user: CurrentUser = Depends(get_current_user)):
    if getattr(current_user, "role", "student") != "lecturer":
        raise HTTPException(status_code=403, detail={"error_code":"E_FORBIDDEN","message":"lecturer_only"})
    if week_number <= 0:
        raise HTTPException(status_code=400, detail={"error_code": "E_INVALID_WEEK", "message": "week must be > 0"})

    # Extract slide_stack_id from request if provided
    slide_stack_id = req.get("slide_stack_id")
    if slide_stack_id and not isinstance(slide_stack_id, int):
        try:
            slide_stack_id = int(slide_stack_id)
        except:
            slide_stack_id = None

    # Use Claude-based generation
    return await generate_challenges_with_claude(week_number, slide_stack_id)


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
# -----------------------------
from app.features.topic_detections.slide_extraction.topic_service import slide_extraction_topic_service
from app.features.challenges.ai.bedrock_client import invoke_claude
import os
from pathlib import Path

DEFAULT_BASIC_TOPICS = [
    "variables",
    "operators",
    "conditionals",
    "loops",
    "functions",
]

async def _fetch_topics_from_supabase(module_code: str, week_number: int) -> str:
    """Fetch topics for prompt filling, preferring `topics` table subtopics, then slide_extractions, then defaults."""
    # 1) Prefer topics table subtopics
    topics = await slide_extraction_topic_service.get_subtopics_for_week(week_number, module_code)
    # 2) Fallback to slide_extractions aggregation
    if not topics:
        topics = await slide_extraction_topic_service.get_all_topics_for_week(week_number, module_code)
    if not topics:
        topics = DEFAULT_BASIC_TOPICS
    return ", ".join(topics)


async def _load_prompt_template(tier: str) -> str:
    """Load the appropriate prompt template for the tier."""
    base_dir = Path(__file__).parent / "prompts"
    template_files = {
        "base": "base.txt",
        "ruby": "ruby.txt",
        "emerald": "emerald.txt",
        "diamond": "diamond.txt"
    }

    template_path = base_dir / template_files.get(tier, "base.txt")
    try:
        return template_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error_code": "E_TEMPLATE_LOAD", "message": f"Failed to load {tier} template: {str(e)}"})


async def _generate_tier_challenge(module_code: str, week_number: int, tier: str) -> Dict[str, Any]:
    """Generate challenge for specific tier using the complete workflow."""

    # 1. Fetch topics from Supabase
    topics_list = await _fetch_topics_from_supabase(module_code, week_number)

    # 2. Load appropriate template
    template = await _load_prompt_template(tier)

    # 3. Fill template with topics
    final_prompt = template.replace("{{topics_list}}", topics_list)

    # 4. Call Bedrock Claude API
    try:
        response = invoke_claude(final_prompt)
        # Note: invoke_claude is synchronous, but if it becomes async, add await
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error_code": "E_CLAUDE_API", "message": f"Claude API error: {str(e)}"})

    # 5. Validate JSON response
    if not isinstance(response, dict):
        raise HTTPException(status_code=500, detail={"error_code": "E_INVALID_RESPONSE", "message": "Invalid response format from Claude"})

    required_fields = ['challenge_set_title', 'questions']
    for field in required_fields:
        if field not in response:
            raise HTTPException(status_code=500, detail={"error_code": "E_MISSING_FIELD", "message": f"Missing required field: {field}"})

    if not isinstance(response['questions'], list) or len(response['questions']) == 0:
        raise HTTPException(status_code=500, detail={"error_code": "E_INVALID_QUESTIONS", "message": "Questions must be a non-empty array"})

    # Validate each question structure
    for i, question in enumerate(response['questions']):
        required_q_fields = ['title', 'question_text', 'difficulty_level', 'starter_code', 'reference_solution', 'test_cases']
        for field in required_q_fields:
            if field not in question:
                raise HTTPException(status_code=500, detail={"error_code": "E_INVALID_QUESTION", "message": f"Question {i} missing field: {field}"})

        if not isinstance(question['test_cases'], list):
            raise HTTPException(status_code=500, detail={"error_code": "E_INVALID_TEST_CASES", "message": f"Question {i} test_cases must be an array"})

        # Validate difficulty levels based on tier
        valid_difficulties = {
            "base": ["Bronze", "Silver", "Gold"],
            "ruby": ["Ruby"],
            "emerald": ["Emerald"],
            "diamond": ["Diamond"]
        }

        if question['difficulty_level'] not in valid_difficulties.get(tier, []):
            raise HTTPException(status_code=500, detail={"error_code": "E_INVALID_DIFFICULTY", "message": f"Invalid difficulty level for {tier} tier"})

    # 6. Insert into database (simplified - you may want to expand this)
    # For now, just return the validated response
    # In production, you'd want to store this in your challenges table

    return {
        "module_code": module_code,
        "week_number": week_number,
        "tier": tier,
        "topics_used": topics_list,
        "challenge_data": response,
        "status": "generated"
    }


@router.post("/generate/base")
async def generate_base_challenge(
    module_code: Optional[str] = Body(None, embed=True),
    module_id: Optional[int] = Body(None, embed=True),
    week_number: int = Body(..., embed=True),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Generate base tier challenges (Bronze/Silver/Gold)."""
    if getattr(current_user, "role", "student") != "lecturer":
        raise HTTPException(status_code=403, detail={"error_code": "E_FORBIDDEN", "message": "lecturer_only"})

    # Backward compatibility: resolve module_code from module_id if needed
    if not module_code and module_id is not None:
        resolved = await slide_extraction_topic_service.resolve_module_code(module_id)
        module_code = resolved or str(module_id)
    if not module_code:
        raise HTTPException(status_code=400, detail={"error_code":"E_INVALID_INPUT","message":"module_code or module_id required"})

    return await _generate_tier_challenge(module_code, week_number, "base")


@router.post("/generate/ruby")
async def generate_ruby_challenge(
    module_code: Optional[str] = Body(None, embed=True),
    module_id: Optional[int] = Body(None, embed=True),
    week_number: int = Body(..., embed=True),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Generate ruby tier challenge."""
    if getattr(current_user, "role", "student") != "lecturer":
        raise HTTPException(status_code=403, detail={"error_code": "E_FORBIDDEN", "message": "lecturer_only"})

    if not module_code and module_id is not None:
        resolved = await slide_extraction_topic_service.resolve_module_code(module_id)
        module_code = resolved or str(module_id)
    if not module_code:
        raise HTTPException(status_code=400, detail={"error_code":"E_INVALID_INPUT","message":"module_code or module_id required"})

    return await _generate_tier_challenge(module_code, week_number, "ruby")


@router.post("/generate/emerald")
async def generate_emerald_challenge(
    module_code: Optional[str] = Body(None, embed=True),
    module_id: Optional[int] = Body(None, embed=True),
    week_number: int = Body(..., embed=True),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Generate emerald tier challenge."""
    if getattr(current_user, "role", "student") != "lecturer":
        raise HTTPException(status_code=403, detail={"error_code": "E_FORBIDDEN", "message": "lecturer_only"})

    if not module_code and module_id is not None:
        resolved = await slide_extraction_topic_service.resolve_module_code(module_id)
        module_code = resolved or str(module_id)
    if not module_code:
        raise HTTPException(status_code=400, detail={"error_code":"E_INVALID_INPUT","message":"module_code or module_id required"})

    return await _generate_tier_challenge(module_code, week_number, "emerald")


@router.post("/generate/diamond")
async def generate_diamond_challenge(
    module_code: Optional[str] = Body(None, embed=True),
    module_id: Optional[int] = Body(None, embed=True),
    week_number: int = Body(..., embed=True),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Generate diamond tier challenge."""
    if getattr(current_user, "role", "student") != "lecturer":
        raise HTTPException(status_code=403, detail={"error_code": "E_FORBIDDEN", "message": "lecturer_only"})

    if not module_code and module_id is not None:
        resolved = await slide_extraction_topic_service.resolve_module_code(module_id)
        module_code = resolved or str(module_id)
    if not module_code:
        raise HTTPException(status_code=400, detail={"error_code":"E_INVALID_INPUT","message":"module_code or module_id required"})

    return await _generate_tier_challenge(module_code, week_number, "diamond")

@router.get("/generate/preview-topics")
async def preview_topics(
    module_code: Optional[str] = None,
    module_id: Optional[int] = None,
    week_number: int = 1,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Preview the topics list that will feed generation. Accepts module_code or module_id."""
    if getattr(current_user, "role", "student") != "lecturer":
        raise HTTPException(status_code=403, detail={"error_code":"E_FORBIDDEN","message":"lecturer_only"})
    if not module_code and module_id is not None:
        resolved = await slide_extraction_topic_service.resolve_module_code(module_id)
        module_code = resolved or str(module_id)
    if not module_code:
        raise HTTPException(status_code=400, detail={"error_code":"E_INVALID_INPUT","message":"module_code or module_id required"})

    topics_from_topics = await slide_extraction_topic_service.get_subtopics_for_week(week_number, module_code)
    topics_from_extractions = await slide_extraction_topic_service.get_all_topics_for_week(week_number, module_code)
    final = topics_from_topics or topics_from_extractions or DEFAULT_BASIC_TOPICS
    return {
        "module_code": module_code,
        "week_number": week_number,
        "topics_table": topics_from_topics,
        "slide_extractions": topics_from_extractions,
        "final_topics": final
    }
