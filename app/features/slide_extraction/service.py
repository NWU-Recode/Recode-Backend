"""Service layer for slide extraction operations."""

from io import BytesIO
from typing import Dict, List

from fastapi import UploadFile
from sqlalchemy.orm import Session

from . import models, repository, schemas
from .pptx_extraction import extract_pptx_text


async def extract_slides_from_upload(file: UploadFile) -> Dict[int, List[str]]:
    """Read ``file`` and return extracted slide text.

    Raises
    ------
    ValueError
        If the uploaded file is not a valid ``.pptx`` file or is empty.
    """

    if not file.filename.lower().endswith(".pptx"):
        raise ValueError("File must have a .pptx extension")

    data = await file.read()
    if not data:
        raise ValueError("Uploaded file is empty")

    return extract_pptx_text(BytesIO(data))


async def save_extraction_from_upload(
    file: UploadFile, db: Session
) -> models.SlideExtraction:
    """Extract slides from ``file`` and persist the result."""
    slides = await extract_slides_from_upload(file)
    data = schemas.SlideExtractionCreate(filename=file.filename, slides=slides)
    return repository.create_extraction(db, data)
