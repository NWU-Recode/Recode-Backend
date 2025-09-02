import os, subprocess

if __name__ == "__main__":
    dev = os.environ.get("ENV", "dev") == "dev"
    port = int(os.environ.get("PORT", 8000))
    if dev:
        import uvicorn
        uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
    else:
        subprocess.run([
            "gunicorn","-k","uvicorn.workers.UvicornWorker",
            "app.main:app","--workers","4",f"--bind=0.0.0.0:{port}"
        ])