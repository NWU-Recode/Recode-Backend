import os
from typing import List, Optional
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from supabase import create_client, Client

# --------------------------
# Supabase client helper (lazy init)
# --------------------------
def get_supabase_client() -> Client:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

SIGNED_URL_EXPIRES_SECONDS = int(os.getenv("SIGNED_URL_EXPIRES_SECONDS", "3600"))
SLIDES_BUCKET = os.getenv("SLIDES_BUCKET_NAME", "slides")

router = APIRouter(prefix="/slides", tags=["Slides"])

# --------------------------
# Response models
# --------------------------
class SlideMeta(BaseModel):
    name: str
    path: str
    size: Optional[int] = None
    created_at: Optional[str] = None
    last_accessed_at: Optional[str] = None

class SlidesListResponse(BaseModel):
    slides: List[SlideMeta]
    total: int

# --------------------------
# Helpers
# --------------------------
def get_profile(user_id: int):
    supabase = get_supabase_client()
    res = supabase.table("profiles").select("id, email, full_name, role").eq("id", user_id).limit(1).execute()
    if res.error:
        raise RuntimeError(f"Supabase error fetching profile: {res.error}")
    rows = res.data or []
    return rows[0] if rows else None

def user_is_enrolled_in_module(user_id: int, module_code: str) -> bool:
    supabase = get_supabase_client()
    mod = supabase.table("modules").select("id").eq("code", module_code).limit(1).execute()
    if mod.error or not mod.data:
        return False
    module_id = mod.data[0]["id"]
    enrol = supabase.table("enrolments").select("id").eq("module_id", module_id).eq("student_id", user_id).limit(1).execute()
    if enrol.error:
        return False
    return bool(enrol.data)

def user_is_lecturer_for_module(user_id: int, module_code: str) -> bool:
    supabase = get_supabase_client()
    mod = supabase.table("modules").select("id, lecturer_id").eq("code", module_code).limit(1).execute()
    if mod.error or not mod.data:
        return False
    lecturer_id = mod.data[0].get("lecturer_id")
    return lecturer_id == user_id

def list_objects_in_bucket(prefix: Optional[str] = None) -> List[dict]:
    supabase = get_supabase_client()
    try:
        res = supabase.storage.from_(SLIDES_BUCKET).list(path=prefix or "", limit=1000, offset=0)
    except Exception as e:
        raise RuntimeError(f"Storage listing error: {e}")
    if hasattr(res, "error") and res.error:
        raise RuntimeError(f"Storage listing error: {res.error}")
    return res.data or []

def create_signed_url_for_object(object_path: str, expires_in: int = SIGNED_URL_EXPIRES_SECONDS) -> str:
    supabase = get_supabase_client()
    try:
        signed = supabase.storage.from_(SLIDES_BUCKET).create_signed_url(object_path, expires_in)
    except Exception as e:
        raise RuntimeError(f"Storage create_signed_url error: {e}")
    if hasattr(signed, "error") and signed.error:
        raise RuntimeError(f"Storage signed url error: {signed.error}")
    return signed.get("signedURL") or signed.get("signed_url") or ""

# --------------------------
# Routes
# --------------------------
@router.get("/", response_model=SlidesListResponse)
def list_slides(
    user_id: int = Query(..., description="Integer user id (profiles.id)"),
    module_code: Optional[str] = Query(None, description="Module code (e.g. CMPG000) to filter slides"),
    limit: int = Query(50, ge=1, le=1000, description="Max number of items"),
    prefix_mode: bool = Query(True, description="If true we treat module_code as a folder prefix in storage")
):
    profile = get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")

    role = (profile.get("role") or "").lower()

    module_codes_to_check = []
    if module_code:
        if role == "student" and not user_is_enrolled_in_module(user_id, module_code):
            raise HTTPException(status_code=403, detail="Student is not enrolled in this module")
        elif role == "lecturer" and not user_is_lecturer_for_module(user_id, module_code):
            raise HTTPException(status_code=403, detail="Lecturer is not assigned to this module")
        module_codes_to_check = [module_code]

    results = []
    if module_codes_to_check:
        for mcode in module_codes_to_check:
            objects = list_objects_in_bucket(prefix=mcode if prefix_mode else None)
            for obj in objects:
                path = obj.get("name") or obj.get("path") or ""
                full_path = f"{mcode}/{path}" if prefix_mode and not path.startswith(f"{mcode}/") else path
                results.append({
                    "name": os.path.basename(path),
                    "path": full_path,
                    "size": obj.get("size"),
                    "created_at": obj.get("created_at"),
                    "last_accessed_at": obj.get("last_accessed_at")
                })
    else:
        objects = list_objects_in_bucket(prefix=None)
        for obj in objects:
            path = obj.get("name") or obj.get("path") or ""
            results.append({
                "name": os.path.basename(path),
                "path": path,
                "size": obj.get("size"),
                "created_at": obj.get("created_at"),
                "last_accessed_at": obj.get("last_accessed_at")
            })

    # Sort & limit
    results_sorted = sorted(results, key=lambda r: r.get("created_at") or "", reverse=True)
    results_limited = results_sorted[:limit]

    slides_meta = [SlideMeta(**r) for r in results_limited]
    return SlidesListResponse(slides=slides_meta, total=len(results_limited))


@router.get("/download")
def get_slide_signed_url(
    user_id: int = Query(..., description="Integer user id (profiles.id)"),
    object_path: str = Query(..., description="Object path in bucket (e.g. MODULE_CODE/filename.pdf)"),
    expires_in: Optional[int] = Query(None, description="Signed URL expiry in seconds (defaults to env)")
):
    profile = get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")

    role = (profile.get("role") or "").lower()
    parts = object_path.split("/", 1)
    module_code = parts[0] if len(parts) > 1 else None

    if module_code:
        if role == "student" and not user_is_enrolled_in_module(user_id, module_code):
            raise HTTPException(status_code=403, detail="Student is not enrolled in this module")
        elif role == "lecturer" and not user_is_lecturer_for_module(user_id, module_code):
            raise HTTPException(status_code=403, detail="Lecturer is not assigned to this module")

    exp = expires_in if expires_in and expires_in > 0 else SIGNED_URL_EXPIRES_SECONDS
    signed = create_signed_url_for_object(object_path, exp)
    if not signed:
        raise HTTPException(status_code=404, detail="File not found or unable to create signed URL")
    return {"url": signed, "expires_in": exp}
