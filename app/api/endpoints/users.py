from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from app.db.client import supabase

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
async def list_users():
    """Return a list of users from the Supabase table."""

    def fetch_users():
        return supabase.table("users").select("*").execute()

    result = await run_in_threadpool(fetch_users)
    if result.error:
        message = getattr(result.error, "message", str(result.error))
        raise HTTPException(status_code=500, detail=message)
    return result.data