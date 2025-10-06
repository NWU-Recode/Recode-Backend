from fastapi import APIRouter
import httpx, os, socket

router = APIRouter()


@router.get("/j0")
async def debug_j0():
    j0 = os.getenv("JUDGE0_URL", "")
    try:
        # 1) DNS resolution
        host = j0.split("://", 1)[-1].split("/", 1)[0]
        resolved = socket.getaddrinfo(host, None)

        # 2) basic TCP/HTTP GET (no auth)
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(j0, follow_redirects=True)
        return {
            "ok": True,
            "judge0_url": j0,
            "dns": [f"{x[4][0]}" for x in resolved],
            "status_code": r.status_code,
            "text_sample": (r.text or "")[:120],
        }
    except Exception as e:
        return {"ok": False, "judge0_url": j0, "error": repr(e)}
