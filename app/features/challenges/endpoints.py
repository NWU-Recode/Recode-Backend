from fastapi import APIRouter, HTTPException, Depends
from app.common.deps import get_current_user, CurrentUser
from .schemas import ChallengeSubmitRequest, ChallengeSubmitResponse
from .service import challenge_service

router = APIRouter(prefix="/challenges", tags=["challenges"])

@router.post('/submit', response_model=ChallengeSubmitResponse)
async def submit_challenge(req: ChallengeSubmitRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        return await challenge_service.finalize(req, str(current_user.id))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
