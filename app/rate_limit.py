"""Rate limiting en memoria por instancia (IP o usuario en sesión)."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from threading import Lock
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.hf_response import wants_ajax

_BUCKETS: dict[str, list[float]] = defaultdict(list)
_LOCK = Lock()

GLOBAL_POST_LIMIT = (300, 60)

# prefix, max_calls, window_seconds, scope
RATE_LIMIT_RULES: tuple[tuple[str, int, int, str], ...] = (
    ("/verificar-telefono/enviar", 5, 3600, "otp_send"),
    ("/verificar-telefono/confirmar", 15, 3600, "otp_confirm"),
    ("/predictions", 120, 60, "predictions"),
    ("/apuestas", 60, 60, "wagers"),
    ("/champion-predictions", 30, 60, "champion"),
    ("/comprar-yape", 10, 3600, "yape"),
    ("/cuenta/eliminar", 3, 3600, "account_delete"),
    ("/admin/", 200, 60, "admin"),
    ("/matches/", 100, 60, "matches_admin"),
    ("/categories", 30, 60, "categories_admin"),
)


def client_ip(request: Request) -> str:
    if os.environ.get("ENVIRONMENT", "").lower() == "production":
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def rate_limit_key(request: Request, scope: str) -> str:
    uid = request.session.get("user_id")
    if uid:
        return f"{scope}:user:{uid}"
    return f"{scope}:ip:{client_ip(request)}"


def _prune(key: str, window: float, now: float) -> None:
    times = _BUCKETS[key]
    cutoff = now - window
    while times and times[0] <= cutoff:
        times.pop(0)


def check_rate_limit(key: str, max_calls: int, window_seconds: float) -> bool:
    now = time.monotonic()
    with _LOCK:
        _prune(key, window_seconds, now)
        times = _BUCKETS[key]
        if len(times) >= max_calls:
            return False
        times.append(now)
        return True


def match_rate_rule(path: str) -> Optional[tuple[int, int, str]]:
    for prefix, max_calls, window, scope in RATE_LIMIT_RULES:
        if prefix.endswith("/"):
            if path.startswith(prefix):
                return max_calls, window, scope
        elif path == prefix or path.startswith(prefix + "/"):
            return max_calls, window, scope
    return None


def rate_limit_exceeded_response(request: Request) -> JSONResponse | RedirectResponse:
    if wants_ajax(request):
        return JSONResponse(
            {"ok": False, "error": "Demasiadas peticiones. Espera un momento e inténtalo de nuevo."},
            status_code=429,
        )
    from app.flash import flash

    flash(request, error="Demasiadas peticiones. Espera un momento e inténtalo de nuevo.")
    referer = request.headers.get("referer", "")
    if referer.startswith("/") and not referer.startswith("//"):
        target = referer
    else:
        target = "/"
    return RedirectResponse(target, status_code=303)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method == "POST":
            path = request.url.path
            rule = match_rate_rule(path)
            if rule:
                max_calls, window, scope = rule
                key = rate_limit_key(request, scope)
            else:
                max_calls, window = GLOBAL_POST_LIMIT
                key = f"global:ip:{client_ip(request)}"
            if not check_rate_limit(key, max_calls, float(window)):
                return rate_limit_exceeded_response(request)
        return await call_next(request)
