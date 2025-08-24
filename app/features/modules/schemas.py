from pydantic import BaseModel, Field
import uuid
from typing import Optional

class ModuleBase(BaseModel):
    module_code: str = Field(..., description="Unique code for the module")
    module_name: str = Field(..., description="Name of the module")
    lecturer_id: uuid.UUID = Field(..., description="Lecturer's UUID")
    semester_id: uuid.UUID = Field(..., description="Semester's UUID")

class ModuleCreate(ModuleBase):
    pass

class ModuleUpdate(BaseModel):
    module_code: Optional[str] = None
    module_name: Optional[str] = None
    lecturer_id: Optional[uuid.UUID] = None
    semester_id: Optional[uuid.UUID] = None

class ModuleOut(ModuleBase):
    module_id: uuid.UUID

    class Config:
        from_attributes = True
