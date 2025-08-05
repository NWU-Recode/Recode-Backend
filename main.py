from fastapi import FastAPI
from app.api.endpoints.users import router as users_router

app = FastAPI(title="Recode Backend")
app.include_router(users_router)

@app.get("/")
def health_check():
    return {"status": "ok"}