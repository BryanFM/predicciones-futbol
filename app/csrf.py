"""Protección CSRF basada en sesión (formularios + cabecera X-CSRF-Token)."""

from __future__ import annotations

import hmac
import secrets
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.hf_response import wants_ajax

CSRF_HEADER = "x-csrf-token"
CSRF_FORM_FIELD = "csrf_token"

EXEMPT_PATHS = frozenset(
    {
        "/health",
        "/auth/callback",
    }
)


def ensure_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def csrf_token(request: Request) -> str:
    """Helper para plantillas Jinja."""
    try:
        return ensure_csrf_token(request)
    except Exception:
        return ""


def is_csrf_exempt(path: str) -> bool:
    return path in EXEMPT_PATHS


def _safe_equal(a: Optional[str], b: Optional[str]) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a, b)


async def _submitted_token(request: Request) -> Optional[str]:
    header = request.headers.get(CSRF_HEADER)
    if header:
        return header.strip()
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        val = form.get(CSRF_FORM_FIELD)
        if val is not None:
            return str(val)
    return None


def csrf_failed_response(request: Request) -> Response:
    if wants_ajax(request):
        return JSONResponse(
            {"ok": False, "error": "Sesión inválida. Recarga la página e inténtalo de nuevo."},
            status_code=403,
        )
    from app.flash import flash

    flash(request, error="Sesión inválida. Recarga la página e inténtalo de nuevo.")
    return RedirectResponse("/", status_code=303)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            ensure_csrf_token(request)
            return await call_next(request)

        if request.method == "POST" and not is_csrf_exempt(request.url.path):
            expected = request.session.get("csrf_token")
            submitted = await _submitted_token(request)
            if not _safe_equal(submitted, expected):
                return csrf_failed_response(request)

        return await call_next(request)
