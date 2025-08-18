import time
import httpx
from jose import jwt
from jose.utils import base64url_decode
from app.Core.config import get_settings

_settings = get_settings()

class JWKSCache:
    def __init__(self, jwks_url: str, ttl_seconds: int = 3600):
        self.jwks_url = jwks_url
        self.ttl = ttl_seconds
        self._jwks = None
        self._fetched_at = 0

    async def get(self) -> dict:
        now = time.time()
        if self._jwks is None or (now - self._fetched_at) > self.ttl:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {}
                if _settings.supabase_anon_key:
                    headers = {
                        "apikey": _settings.supabase_anon_key,
                        "Authorization": f"Bearer {_settings.supabase_anon_key}",
                    }

                # Try primary then fallbacks if 404 (Supabase deployments differ)
                attempted = []
                urls = [self.jwks_url]
                if self.jwks_url.endswith('/certs'):
                    base = self.jwks_url[:-len('certs')]
                    urls.extend([
                        base + 'jwks',
                        base + '.well-known/jwks.json',
                    ])
                last_exc = None
                for url in urls:
                    attempted.append(url)
                    try:
                        resp = await client.get(url, headers=headers)
                        if resp.status_code == 404:
                            continue
                        resp.raise_for_status()
                        self._jwks = resp.json()
                        self._fetched_at = now
                        # If fallback worked, update canonical URL
                        self.jwks_url = url
                        break
                    except Exception as e:  # noqa: BLE001
                        last_exc = e
                        continue
                else:
                    # All attempts failed
                    if last_exc:
                        raise last_exc
                    raise RuntimeError(f"Failed to fetch JWKS. Tried: {attempted}")
        return self._jwks

    async def verify(self, token: str, audience: str | None = None) -> dict:
        jwks = await self.get()
        headers = jwt.get_unverified_header(token)
        kid = headers.get("kid")
        key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
        if not key:
            # Force refresh once if kid not found
            self._jwks = None
            jwks = await self.get()
            key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
        if not key:
            raise ValueError("Signing key not found for token")

        return jwt.decode(
            token,
            key,
            algorithms=[key["alg"]],
            audience=audience,
            options={"verify_aud": audience is not None},
        )
