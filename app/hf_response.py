"""Respuestas HTML vs JSON para peticiones AJAX del frontend."""

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.responses import Response


def wants_ajax(request: Request) -> bool:
    return request.headers.get("x-hf-ajax") == "1"


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
