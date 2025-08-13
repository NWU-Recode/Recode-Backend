from fastapi import FastAPI

from app.db.session import init_db
from app.features.slide_extraction.endpoints import (
    router as slide_extraction_router,
)
from app.features.users.endpoints import router as users_router


app = FastAPI(title="Recode Backend")

init_db()

app.include_router(users_router)
app.include_router(slide_extraction_router)
