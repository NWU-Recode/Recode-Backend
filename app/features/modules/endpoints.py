from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from . import schemas, service

router = APIRouter(prefix="/modules", tags=["modules"])

@router.get("/", response_model=list[schemas.ModuleOut])
def list_modules(db: Session = Depends(get_db)):
    """List all modules."""
    return service.module_service.list(db)

@router.get("/{module_id}", response_model=schemas.ModuleOut)
def get_module(module_id: str, db: Session = Depends(get_db)):
    """Get a module by ID."""
    module = service.module_service.get(db, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    return module

@router.post("/", response_model=schemas.ModuleOut, status_code=status.HTTP_201_CREATED)
def create_module(module: schemas.ModuleCreate, db: Session = Depends(get_db)):
    """Create a new module."""
    return service.module_service.create(db, module)

@router.put("/{module_id}", response_model=schemas.ModuleOut)
def update_module(module_id: str, module: schemas.ModuleUpdate, db: Session = Depends(get_db)):
    """Update an existing module."""
    updated = service.module_service.update(db, module_id, module)
    if not updated:
        raise HTTPException(status_code=404, detail="Module not found")
    return updated

@router.delete("/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_module(module_id: str, db: Session = Depends(get_db)):
    """Delete a module by ID."""
    deleted = service.module_service.delete(db, module_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Module not found")
    return
