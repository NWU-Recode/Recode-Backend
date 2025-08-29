from __future__ import annotations

import mimetypes
from typing import Dict, Any

from .pathing import build_slide_object_key
from app.DB.supabase import get_supabase


async def upload_slide_bytes(
    file_bytes: bytes,
    original_filename: str,
    topic_name: str,
    given_at_dt,             # datetime
    semester_start_date,     # date
    signed_url_ttl_sec: int = 900,
) -> Dict[str, Any]:
    key = build_slide_object_key(original_filename, topic_name, given_at_dt, semester_start_date)
    content_type = mimetypes.guess_type(original_filename)[0] or "application/octet-stream"

    client = await get_supabase()
    bucket = client.storage.from_("slides")
    # Upload bytes
    bucket.upload(
        path=key.object_key,
        file=file_bytes,
        file_options={"content-type": content_type, "cache-control": "max-age=31536000"},
    )
    signed = bucket.create_signed_url(key.object_key, expires_in=signed_url_ttl_sec)
    # supabase-py returns dict with signedURL
    signed_url = signed.get("signedURL") if isinstance(signed, dict) else None
    return {
        "season": key.season,
        "week": key.week,
        "topic_slug": key.topic_slug,
        "object_key": key.object_key,
        "signed_url": signed_url,
    }

