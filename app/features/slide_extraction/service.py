"""Service layer for slide extraction operations."""

from io import BytesIO
from typing import Dict, List

from fastapi import UploadFile
from sqlalchemy.orm import Session

from . import models, repository, schemas
from fastapi.concurrency import run_in_threadpool
from .pptx_extraction import extract_pptx_text


async def extract_slides_from_upload(file: UploadFile) -> Dict[int, List[str]]:	

    if not file.filename.lower().endswith(".pptx"):
        raise ValueError("File must have a .pptx extension")

    data = await file.read()
    if not data:
        raise ValueError("Uploaded file is empty")

    return extract_pptx_text(BytesIO(data))


async def save_extraction_from_upload(
    file: UploadFile, db: Session, persist: bool = True
) -> models.SlideExtraction | dict:
    slides = await extract_slides_from_upload(file)
    if not persist:
        return {"filename": file.filename, "slides": slides}
    data = schemas.SlideExtractionCreate(filename=file.filename, slides=slides)	
    return await run_in_threadpool(repository.create_extraction, db, data)
