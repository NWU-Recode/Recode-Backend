from sqlalchemy.orm import Session
from . import repository, schemas
from .models import Module
from typing import List, Optional

class ModuleService:
    def list(self, db: Session) -> List[Module]:
        """List all modules."""
        return repository.module_repository.list(db)

    def get(self, db: Session, module_id: str) -> Optional[Module]:
        """Get a module by ID."""
        return repository.module_repository.get(db, module_id)

    def create(self, db: Session, module: schemas.ModuleCreate) -> Module:
        """Create a new module."""
        return repository.module_repository.create(db, module)

    def update(self, db: Session, module_id: str, module: schemas.ModuleUpdate) -> Optional[Module]:
        """Update an existing module."""
        return repository.module_repository.update(db, module_id, module)

    def delete(self, db: Session, module_id: str) -> bool:
        """Delete a module by ID."""
        return repository.module_repository.delete(db, module_id)

module_service = ModuleService()
