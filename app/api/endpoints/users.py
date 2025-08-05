from fastapi import APIRouter, HTTPException
from app.db.client import supabase

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
async def list_users():
    result = supabase.table("users").select("*").execute()
    if result.error:
        raise HTTPException(status_code=500, detail=result.error.message)
    return result.data