# app/features/semester/schemas.py
from pydantic import BaseModel
from datetime import date
from uuid import UUID

class SemesterCreate(BaseModel):
    year: int
    term_name: str
    start_date: date
    end_date: date

class SemesterResponse(BaseModel):
    id: UUID
    year: int
    term_name: str
    start_date: date
    end_date: date
    is_current: bool

    model_config = {
        "from_attributes": True  # <-- this replaces orm_mode
    }
class ModuleResponse(BaseModel):
    id: UUID
    name: str
    code: str
    description: str 

    model_config = {
        "from_attributes": True  # allows from_orm/model_validate
    }