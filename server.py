import subprocess
import os

if __name__ == "__main__":
    dev = os.environ.get("ENV", "dev") == "dev"

    if dev:
        import uvicorn
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
    else:
        subprocess.run([
            "gunicorn",
            "-k", "uvicorn.workers.UvicornWorker",
            "app.main:app",
            "--workers", "4",
            "--bind", "127.0.0.1:8000"
        ])
