"""Proxy y caché de avatares externos (p. ej. Google) para evitar 429."""

from __future__ import annotations

import re
import time
from typing import Optional

import httpx

from app.models import User

_CACHE: dict[str, tuple[float, bytes, str]] = {}
_CACHE_TTL_SECONDS = 86_400
_STALE_GRACE_SECONDS = 604_800
_USER_AGENT = "HamsterFijas/1.0"


def avatar_url(user: Optional[User], size: str = "sm") -> str:
    if not user or not user.picture:
        return ""
    return f"/avatars/{user.id}?v={size}"


def normalize_google_avatar_url(url: str, *, px: int = 128) -> str:
    if "googleusercontent.com" not in url:
        return url
    base = re.sub(r"=s\d+(-c)?$", "", url.split("?", 1)[0])
    return f"{base}=s{px}-c"


def _cache_get(url: str, *, allow_stale: bool = False) -> Optional[tuple[bytes, str]]:
    entry = _CACHE.get(url)
    if not entry:
        return None
    expires_at, body, content_type = entry
    now = time.time()
    if expires_at >= now:
        return body, content_type
    if allow_stale and now - expires_at <= _STALE_GRACE_SECONDS:
        return body, content_type
    return None


def _cache_set(url: str, body: bytes, content_type: str) -> None:
    _CACHE[url] = (time.time() + _CACHE_TTL_SECONDS, body, content_type)


async def fetch_avatar(url: str) -> tuple[bytes, str]:
    normalized = normalize_google_avatar_url(url)
    cached = _cache_get(normalized)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(
                normalized,
                headers={"User-Agent": _USER_AGENT, "Accept": "image/*"},
            )
            if response.status_code == 429:
                stale = _cache_get(normalized, allow_stale=True)
                if stale:
                    return stale
                response.raise_for_status()
            response.raise_for_status()
            content_type = response.headers.get("content-type", "image/jpeg").split(";")[0]
            body = response.content
    except httpx.HTTPError:
        stale = _cache_get(normalized, allow_stale=True)
        if stale:
            return stale
        raise

    _cache_set(normalized, body, content_type)
    return body, content_type
