from sqlalchemy.orm import Session
from . import models, schemas
import uuid

class ModuleRepository:
    def list(self, db: Session) -> list[models.Module]:
        return db.query(models.Module).all()

    def get(self, db: Session, module_id: str) -> models.Module | None:
        # Ensure module_id is UUID if needed
        try:
            module_id = uuid.UUID(module_id)
        except ValueError:
            return None
        return db.query(models.Module).filter(models.Module.module_id == module_id).first()

    def create(self, db: Session, module: schemas.ModuleCreate) -> models.Module:
        db_module = models.Module(**module.dict())
        db.add(db_module)
        db.commit()
        db.refresh(db_module)
        return db_module

    def update(self, db: Session, module_id: str, module: schemas.ModuleUpdate) -> models.Module | None:
        db_module = self.get(db, module_id)
        if not db_module:
            return None
        for key, value in module.dict(exclude_unset=True).items():
            setattr(db_module, key, value)
        db.commit()
        db.refresh(db_module)
        return db_module

    def delete(self, db: Session, module_id: str) -> bool:
        db_module = self.get(db, module_id)
        if db_module:
            db.delete(db_module)
            db.commit()
            return True
        return False

module_repository = ModuleRepository()
