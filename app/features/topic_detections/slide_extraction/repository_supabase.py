from __future__ import annotations

from typing import Optional, Dict, Any
from app.DB.supabase import get_supabase


class SlideExtractionSupabaseRepository:
    table = "slide_extractions"

    async def create_extraction(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        resp = await client.table(self.table).insert(data).execute()
        if not getattr(resp, "data", None):
            # Bubble up a clear error when insert failed so callers can react
            raise RuntimeError("Failed to create slide_extraction row: no data returned")
        return resp.data[0]


slide_extraction_supabase_repository = SlideExtractionSupabaseRepository()
