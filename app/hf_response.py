"""Respuestas HTML vs JSON para peticiones AJAX del frontend."""

from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.responses import Response


def wants_ajax(request: Request) -> bool:
    return request.headers.get("x-hf-ajax") == "1"


def safe_back(return_to: str, fallback: str) -> str:
    """Solo rutas internas (evita open redirect)."""
    if return_to.startswith("/") and not return_to.startswith("//"):
        return return_to
    return fallback


def home_url(
    category_id: Optional[int] = None,
    match_date: Optional[str] = None,
    group: Optional[str] = None,
) -> str:
    params = []
    if category_id:
        params.append(f"category_id={category_id}")
    if match_date:
        params.append(f"match_date={match_date}")
    if group:
        params.append(f"group={group}")
    return "/?" + "&".join(params) if params else "/"


def ajax_or_redirect(
    request: Request,
    redirect_url: str,
    data: dict[str, Any],
    *,
    status_code: int = 200,
) -> Response:
    if wants_ajax(request):
        return JSONResponse({"ok": True, **data}, status_code=status_code)
    return RedirectResponse(redirect_url, status_code=303)


def ajax_error(
    request: Request,
    redirect_url: str,
    message: str,
    *,
    status_code: int = 400,
) -> Response:
    if wants_ajax(request):
        return JSONResponse({"ok": False, "error": message}, status_code=status_code)
    from app.flash import flash

    flash(request, error=message)
    return RedirectResponse(redirect_url, status_code=303)
