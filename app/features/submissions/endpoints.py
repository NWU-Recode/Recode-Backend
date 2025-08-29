from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from app.common.deps import get_current_user, CurrentUser
from app.features.questions.schemas import (
    ExecuteRequest, ExecuteResponse,
    QuestionSubmitRequest, QuestionSubmitResponse,
)
from app.features.questions.service import question_service


router = APIRouter(prefix="/submissions", tags=["submissions"])


def _err(status: int, code: str, message: str):
    return HTTPException(status_code=status, detail={"error_code": code, "message": message})


@router.post('/execute', response_model=ExecuteResponse)
async def execute(req: ExecuteRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await question_service.execute(req, str(current_user.id))
    except Exception as e:
        raise _err(400, "E_INVALID_INPUT", str(e))


@router.post('/submit', response_model=QuestionSubmitResponse)
async def submit(req: QuestionSubmitRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        resp = await question_service.submit(req, str(current_user.id))
        from fastapi.responses import JSONResponse
        if isinstance(resp, dict) and resp.get("__pending__"):
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

