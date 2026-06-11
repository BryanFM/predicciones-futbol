"""Cabeceras de seguridad y validaciones de arranque en producción."""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware


def validate_production_secrets() -> None:
    if os.environ.get("ENVIRONMENT", "").lower() != "production":
        return
    key = os.environ.get("SECRET_KEY", "").strip()
    if not key or key == "dev-secret-change-in-production" or len(key) < 32:
        raise RuntimeError(
            "SECRET_KEY inválida en producción: debe tener al menos 32 caracteres "
            "y no usar el valor por defecto de desarrollo."
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if os.environ.get("ENVIRONMENT", "").lower() == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://scripts.clarity.ms; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self' https://www.google-analytics.com https://*.clarity.ms "
            "https://www.googletagmanager.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        return response
