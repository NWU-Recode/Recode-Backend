from fastapi import FastAPI

app = FastAPI(title="Minimal Recode Backend")

@app.get("/")
def root():
    return {"status": "ok"}
