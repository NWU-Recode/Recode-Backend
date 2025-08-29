#Question feature - Question management, Fetching and filtering questions
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.common.deps import get_current_user, CurrentUser
from .schemas import (
    ExecuteRequest, ExecuteResponse,
    QuestionSubmitRequest, QuestionSubmitResponse,
    BatchExecuteRequest, BatchExecuteResponse,
    BatchSubmitRequest, BatchSubmitResponse,
    ChallengeTilesResponse, 
    FetchedRequest, FetchedResponse,
    QuestionCreateRequest, QuestionCreateResponse,
    QuestionUpdateRequest, QuestionUpdateResponse,
    QuestionSummaryResponse,
    QuestionStatsResponse,
    QuestionHintRequest,QuestionHintResponse,
    QuestionHintCreateRequest,QuestionHintCreateResponse,
    QuestionHintUpdateRequest,QuestionHintUpdateResponse
    



)
from .service import question_service

#setup of router
router = APIRouter(prefix="/questions", tags=["questions"])

#function to make erros consistent
def _err(status: int, code: str, message: str):
    return HTTPException(status_code=status, detail={"error_code": code, "message": message})

#Submission?
@router.post('/execute', response_model=ExecuteResponse)
async def execute_question(req: ExecuteRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await question_service.execute(req, str(current_user.id))
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))

#Submission?
@router.post('/submit', response_model=QuestionSubmitResponse)
async def submit_question(req: QuestionSubmitRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        resp = await question_service.submit(req, str(current_user.id))
        if isinstance(resp, dict) and resp.get("__pending__"):
            from fastapi.responses import JSONResponse
            body = {k: v for k, v in resp.items() if k != "__pending__"}
            body.update({"status": "pending"})
            return JSONResponse(status_code=202, content=body)
        return resp
    except Exception as e:
        msg = str(e)
        code = "E_INVALID_INPUT"
        if "payload_too_large" in msg:
            code = "E_PAYLOAD_TOO_LARGE"
            raise _err(413, code, msg)
        elif msg == "duplicate_idempotency_key":
            raise _err(409, "E_CONFLICT", msg)
        raise _err(400, code, msg)

#Submission?
@router.post('/batch/execute', response_model=BatchExecuteResponse)
async def batch_execute(req: BatchExecuteRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await question_service.batch_execute(req, str(current_user.id))
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))
#Submission?
@router.post('/batch/submit', response_model=BatchSubmitResponse)
async def batch_submit(req: BatchSubmitRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await question_service.batch_submit(req, str(current_user.id))
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))

#Challenges?
@router.get('/tiles/{challenge_id}', response_model=ChallengeTilesResponse)
async def get_tiles(challenge_id: str, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await question_service.get_tiles(challenge_id, str(current_user.id))
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))

#CAITLIN - ADDED ENDPOINTS
#QUERYING QUESTIONS
#fetches relevant questions from question bank based on tags derived from slides , will later be selected for challenge
@router.post("/fetch-question", response_model=FetchedResponse)
async def fetch_questions(req: FetchedRequest):
    try:
        return await question_service.fetch(req)
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))


#CRUD operations for question manangement
#Create new question
@router.post('/create', response_model=QuestionCreateResponse)
async def create_question(req: QuestionCreateRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await question_service.create_question(req, str(current_user.id))
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))

#Update existing question
@router.put('/{question_id}', response_model=QuestionUpdateResponse)
async def update_question(question_id: str, req: QuestionUpdateRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await question_service.update_question(question_id, req, str(current_user.id))
    except Exception as e:
        raise _err(400, "E_NOT__FOUND", str(e))

#Delete existing question
@router.delete('/{question_id}')
async def delete_question(question_id: str, current_user: CurrentUser = Depends(get_current_user)):
    try:
        await question_service.delete_question(question_id, str(current_user.id))
        return {"status": "success", "message":"Question Deleted"}
    except Exception as e:
        raise _err(400, "E_NOT__FOUND", str(e))

# Return all questions for lecturer with filters (difficulty and topic (from slide extraction feature)) for selection UI
@router.get('/list', response_model=List[QuestionSummaryResponse])
async def list_questions( topic: str = None, difficulty: str = None, lecture_id: str = None,exclude_already_assigned: bool = True,current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await question_service.filter_questions(
            topic=topic,
            difficulty=difficulty,
        )
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))

# Return stats on questions: counts per topic, difficulty, usage history
@router.get('/stats', response_model=QuestionStatsResponse)
async def get_question_stats(current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await question_service.get_question_stats()
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))
#HINTS FOR THE QUESTIONS
#CRUD operations for hint management
#Add
@router.post("/{question_id}/hints", response_model=QuestionHintCreateResponse)
async def create_hint(question_id: str, req: QuestionHintCreateRequest, current_user: CurrentUser = Depends(get_current_user)):
    return await question_service.create_hint(question_id, req, str(current_user.id))
#Update
@router.put("/hints/{hint_id}", response_model=QuestionHintUpdateResponse)
async def update_hint(hint_id: str, req: QuestionHintUpdateRequest, current_user: CurrentUser = Depends(get_current_user)):
    return await question_service.update_hint(hint_id, req, str(current_user.id))
#Delete
@router.delete("/hints/{hint_id}")
async def delete_hint(hint_id: str, current_user: CurrentUser = Depends(get_current_user)):
    await question_service.delete_hint(hint_id, str(current_user.id))
    return {"status": "success", "message": "Hint deleted"}

#Returns hints for a question, hints will be tiered and unlocked after certain attemps
@router.get("/{question_id}/hints/student", response_model=List[QuestionHintResponse])
async def get_hints_for_student(
    question_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    try:
        return await question_service.get_student_hints(question_id, str(current_user.id))
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))

