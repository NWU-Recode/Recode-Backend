from fastapi import APIRouter
from .schemas import User
from .service import get_all_users

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=list[User])
def read_users():
    return get_all_users()