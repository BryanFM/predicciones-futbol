"""Mensajes flash en sesión (evita msg/error en la URL)."""

from typing import Optional

from starlette.requests import Request


def flash(
    request: Request,
    *,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    pending_phone: Optional[str] = None,
) -> None:
    if msg:
        request.session["flash_msg"] = msg
    if error:
        request.session["flash_error"] = error
    if pending_phone:
        request.session["pending_phone"] = pending_phone


def consume_flash(request: Request) -> dict[str, Optional[str]]:
    return {
        "msg": request.session.pop("flash_msg", None),
        "error": request.session.pop("flash_error", None),
        "pending_phone": request.session.pop("pending_phone", None),
    }
