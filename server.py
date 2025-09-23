import os
import uvicorn

if __name__ == "__main__":
    dev = os.environ.get("ENV", "dev") == "dev"
    port = int(os.environ.get("PORT", 8000))  # Render injects PORT

    if dev:
        # Local dev with reload
        uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=True)
    else:
        # Production on Render – no reload, bind to all interfaces
        uvicorn.run("app.main:app", host="0.0.0.0", port=port)
