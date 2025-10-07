# app/features/slidesDownload/service.py

from sqlalchemy.ext.asyncio import AsyncSession
from . import repository
import os
from supabase import create_client
from dotenv import load_dotenv
from sqlalchemy import text
from app.features.slidesDownload.repository import get_slides_by_challenge_id

load_dotenv()
# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

async def fetch_slide_by_id(db: AsyncSession, slide_id: int):
    return await repository.get_slide_by_id(db, slide_id)

async def list_slides(db: AsyncSession, weeks=None, module_codes=None, search=None):
    return await repository.list_slides(db, weeks, module_codes, search)

async def generate_signed_url(slides_key: str, ttl: int = 300) -> str:
    if not slides_key:
        raise ValueError("slides_key is None or empty")

    bucket_name = "slides"  # correct bucket name

    # Generate signed URL directly
    signed_url = supabase.storage.from_(bucket_name).create_signed_url(slides_key, ttl)

    # Check if the signed URL was returned
    if 'signedURL' not in signed_url:
        raise FileNotFoundError(f"File '{slides_key}' not found in bucket '{bucket_name}'")

    return signed_url['signedURL']
async def fetch_slides_by_challenge_id(db: AsyncSession, challenge_id: str):
    query = text("""
        SELECT 
            c.title AS challenge_title,
            t.title AS topic_title,
            se.id AS slide_id,
            se.filename,
            se.slides AS slides_key,
            t.id AS topic_id,
            t.module_code_slidesdeck AS module_code,
            c.week_number AS week_number
        FROM 
            challenges c
        JOIN 
            topic t 
            ON t.week = c.week_number 
            AND t.module_code_slidesdeck = c.module_code
        JOIN 
            slide_extractions se 
            ON se.id = t.slide_extraction_id
        WHERE 
            c.id = :challenge_id
    """)
    result = db.execute(query, {"challenge_id": challenge_id})

    rows = result.mappings().all()  # This is okay
    return rows



