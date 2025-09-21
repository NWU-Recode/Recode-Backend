import time
import httpx
from jose import jwt
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
            # Clamp timeouts and pool to avoid 30s stalls
            timeout = httpx.Timeout(connect=3, read=5, write=5, pool=5)
            limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
            async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
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
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "")
        # HS256 legacy path
        if alg.startswith("HS"):
            secret = _settings.supabase_jwt_secret
            if not secret:
                raise ValueError("HS token but SUPABASE_JWT_SECRET not configured")
            return jwt.decode(
                token,
                secret,
                algorithms=[alg],
                audience=audience,
                options={"verify_aud": audience is not None},
            )

        # RS256 path (kid required)
        jwks = await self.get()
        kid = header.get("kid")
        key = None
        if kid:
            key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
            if not key:
                # Force refresh and retry once
                self._jwks = None
                jwks = await self.get()
                key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if not key:
            available = [k.get("kid") for k in jwks.get("keys", [])]
            raise ValueError(f"Signing key not found (alg={alg}, kid={kid}, available={available})")
        return jwt.decode(
            token,
            key,
            algorithms=[key.get("alg", alg)],
            audience=audience,
            options={"verify_aud": audience is not None},
        )
