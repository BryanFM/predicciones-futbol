"""SEO: URLs canónicas, metadatos y sitemap."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import Request

SITE_NAME = "Hamster Fijas"
DEFAULT_META_DESCRIPTION = (
    "Hamster Fijas — plataforma de predicciones del Mundial 2026. "
    "Registra marcadores exactos, elige al campeón y compite por Hamster puntos con tus amigos."
)
DEFAULT_OG_IMAGE_PATH = "/static/apple-touch-icon.png"

NOINDEX_PREFIXES = (
    "/admin",
    "/auth",
    "/cuenta",
    "/verificar-telefono",
    "/comprar-yape",
    "/mis-compras-yape",
    "/yape/qr",
    "/avatars/",
    "/apuestas",
    "/mis-puntos",
)


def site_base_url(request: Request) -> str:
    configured = os.environ.get("SITE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    return str(request.base_url).rstrip("/")


def absolute_url(request: Request, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    base = site_base_url(request)
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def canonical_url(request: Request, path: Optional[str] = None) -> str:
    return absolute_url(request, path or request.url.path)


def og_image_url(request: Request) -> str:
    return absolute_url(request, DEFAULT_OG_IMAGE_PATH)


def default_robots(request: Request) -> str:
    path = request.url.path
    if any(path.startswith(prefix) for prefix in NOINDEX_PREFIXES):
        return "noindex, nofollow"
    return "index, follow"


def format_sitemap_lastmod(value: Optional[datetime] = None) -> str:
    dt = value or datetime.utcnow()
    return dt.strftime("%Y-%m-%d")
