"""QR Yape: almacenamiento privado y entrega solo a usuarios verificados."""

from __future__ import annotations

import base64
import binascii
import os
import re
from pathlib import Path
from typing import Optional

PRIVATE_YAPE_DIR = Path(__file__).resolve().parent / "private" / "yape"
MAX_QR_BYTES = 512_000
QR_FILENAME_RE = re.compile(r"^[a-zA-Z0-9._-]+$")

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
WEBP_RIFF = b"RIFF"
WEBP_MAGIC = b"WEBP"


def _refresh_env_if_dev() -> None:
    if os.environ.get("ENVIRONMENT", "").lower() == "development":
        from app.env import refresh_env

        refresh_env()


def _media_type_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(ext, "application/octet-stream")


def _detect_media_type(data: bytes) -> Optional[str]:
    if data.startswith(PNG_MAGIC):
        return "image/png"
    if data.startswith(JPEG_MAGIC):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == WEBP_RIFF and data[8:12] == WEBP_MAGIC:
        return "image/webp"
    return None


def _validate_image(data: bytes) -> Optional[str]:
    if not data or len(data) > MAX_QR_BYTES:
        return None
    return _detect_media_type(data)


def _read_qr_file() -> Optional[tuple[bytes, str]]:
    filename = os.environ.get("YAPE_QR_FILE", "qr.png").strip() or "qr.png"
    if not QR_FILENAME_RE.match(filename):
        return None

    path = (PRIVATE_YAPE_DIR / filename).resolve()
    try:
        path.relative_to(PRIVATE_YAPE_DIR.resolve())
    except ValueError:
        return None

    if not path.is_file():
        for candidate in sorted(PRIVATE_YAPE_DIR.glob("qr.*")):
            if candidate.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                path = candidate
                break
        else:
            return None

    data = path.read_bytes()
    media_type = _validate_image(data)
    if not media_type:
        return None
    return data, media_type


def _read_qr_base64() -> Optional[tuple[bytes, str]]:
    raw = os.environ.get("YAPE_QR_BASE64", "").strip()
    if not raw:
        return None
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        return None

    media_type = _validate_image(data)
    if not media_type:
        return None

    configured = os.environ.get("YAPE_QR_MEDIA_TYPE", "").strip()
    if configured in {"image/png", "image/jpeg", "image/webp"} and configured == media_type:
        return data, configured
    return data, media_type


def yape_qr_content() -> Optional[tuple[bytes, str]]:
    """Devuelve (bytes, media_type) del QR o None si no está configurado."""
    _refresh_env_if_dev()
    from_file = _read_qr_file()
    if from_file:
        return from_file
    return _read_qr_base64()


def yape_qr_available() -> bool:
    return yape_qr_content() is not None
