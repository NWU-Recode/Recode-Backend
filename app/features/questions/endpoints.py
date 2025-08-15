from fastapi import APIRouter, HTTPException, Depends
from app.common.deps import get_current_user, CurrentUser
from .schemas import (
    ExecuteRequest, ExecuteResponse,
    QuestionSubmitRequest, QuestionSubmitResponse,
    BatchExecuteRequest, BatchExecuteResponse,
    BatchSubmitRequest, BatchSubmitResponse
)
from .service import question_service

router = APIRouter(prefix="/questions", tags=["questions"])

@router.post('/execute', response_model=ExecuteResponse)
async def execute_question(req: ExecuteRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await question_service.execute(req, str(current_user.id))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post('/submit', response_model=QuestionSubmitResponse)
async def submit_question(req: QuestionSubmitRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await question_service.submit(req, str(current_user.id))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post('/batch/execute', response_model=BatchExecuteResponse)
async def batch_execute(req: BatchExecuteRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await question_service.batch_execute(req, str(current_user.id))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post('/batch/submit', response_model=BatchSubmitResponse)
async def batch_submit(req: BatchSubmitRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await question_service.batch_submit(req, str(current_user.id))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
