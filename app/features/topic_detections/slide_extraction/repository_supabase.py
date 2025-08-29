from __future__ import annotations

from typing import Optional, Dict, Any
from app.DB.supabase import get_supabase


class SlideExtractionSupabaseRepository:
    table = "slide_extractions"

    async def create_extraction(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        client = await get_supabase()
        try:
            resp = await client.table(self.table).insert(data).execute()
            return resp.data[0] if getattr(resp, "data", None) else None
        except Exception:
            return None


slide_extraction_supabase_repository = SlideExtractionSupabaseRepository()
