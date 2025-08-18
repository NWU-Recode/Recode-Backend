"""Service layer for slide extraction operations."""

from io import BytesIO
from typing import Dict, List

from fastapi import UploadFile

from .pptx_extraction import extract_pptx_text


async def extract_slides_from_upload(file: UploadFile) -> Dict[int, List[str]]:	

    if not file.filename.lower().endswith(".pptx"):
        raise ValueError("File must have a .pptx extension")

    data = await file.read()
    if not data:
        raise ValueError("Uploaded file is empty")

    return extract_pptx_text(BytesIO(data))

