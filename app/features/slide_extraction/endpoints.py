from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.common.deps import get_current_user, CurrentUser



router = APIRouter(prefix="/slides", tags=["slide-extraction"])


#Extract slide text without hitting the database (quick test endpoint).
@router.post("/extract/raw", response_model=dict, summary="Extract slide text (auth required)")
async def extract_slides_raw(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user)
) -> dict:
    try:
        from .service import extract_slides_from_upload
        slides = await extract_slides_from_upload(file)
        return {"filename": file.filename, "slides": slides, "user_id": str(current_user.id)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
