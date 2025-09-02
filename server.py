import os
import sys

if __name__ == "__main__":
    dev = os.environ.get("ENV", "dev") == "dev"

    if dev:
        import uvicorn
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
    else:
        # Derive bind host/port and worker count from environment (Render/Heroku style)
        host = os.environ.get("HOST", "0.0.0.0")
        port = os.environ.get("PORT", "8000")
        workers = os.environ.get("WEB_CONCURRENCY") or os.environ.get("WORKERS") or "4"

        cmd = [
            "gunicorn",
            "-k", "uvicorn.workers.UvicornWorker",
            "app.main:app",
            "--workers", str(int(workers)),
            "--bind", f"{host}:{port}",
            "--access-logfile", "-",
        ]

        # Replace the current process with gunicorn so signals/healthchecks work
        os.execvp(cmd[0], cmd)
