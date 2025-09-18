from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class ModuleBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    semester_id: UUID
    lecturer_id: int
    code_language: Optional[str]
    credits: Optional[int]

class ModuleCreate(ModuleBase):
    pass

class ModuleResponse(ModuleBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
