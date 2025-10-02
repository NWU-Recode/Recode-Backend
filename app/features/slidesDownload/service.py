# app/features/slidesDownload/service.py

from sqlalchemy.ext.asyncio import AsyncSession
from . import repository
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd0b2VodmxvZHJtbXF6eXhvYWlsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NDQxMjc0OSwiZXhwIjoyMDY5OTg4NzQ5fQ.-8QuL9HfjPgORJdRAVsGYF29mxJJYcQGBm6np8O-9gQ"
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


