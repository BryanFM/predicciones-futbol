"""Configuración de pagos Yape (beta)."""

from __future__ import annotations

import os
import re
from typing import Optional

YAPE_PACKAGES: list[dict] = [
    {
        "id": "starter",
        "label": "Pack Inicial",
        "soles": 10,
        "hp": 10,
        "desc": "10 Hamster puntos extra para el torneo",
    },
    {
        "id": "pro",
        "label": "Pack Pro",
        "soles": 20,
        "hp": 25,
        "desc": "25 Hamster puntos extra para el torneo",
    },
    {
        "id": "elite",
        "label": "Pack Elite",
        "soles": 50,
        "hp": 70,
        "desc": "70 Hamster puntos extra para el torneo",
    },
]

MAX_PENDING_REQUESTS = 2
OPERATION_CODE_RE = re.compile(r"^[A-Za-z0-9]{6,14}$")


def yape_payments_enabled() -> bool:
    raw = os.environ.get("YAPE_PAYMENTS_BETA", "").strip().lower()
    if raw in ("1", "true", "yes"):
        return True
    if raw in ("0", "false", "no"):
        return False
    return os.environ.get("ENVIRONMENT", "").lower() == "development"


def yape_recipient_phone() -> str:
    """Número peruano de 9 dígitos (sin +51)."""
    raw = os.environ.get("YAPE_RECIPIENT_PHONE", "").strip()
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("51") and len(digits) == 11:
        digits = digits[2:]
    return digits[-9:] if len(digits) >= 9 else digits


def format_yape_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 9:
        return f"{digits[0:3]} {digits[3:6]} {digits[6:9]}"
    return phone or "—"


def get_package(package_id: str) -> Optional[dict]:
    package_id = (package_id or "").strip().lower()
    for pkg in YAPE_PACKAGES:
        if pkg["id"] == package_id:
            return pkg
    return None
