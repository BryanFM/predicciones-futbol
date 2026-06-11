"""Plantillas Jinja2 compartidas e inyección de contexto común."""

from pathlib import Path
from typing import Any, Optional

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.models import User
from app.flash import consume_flash
from app.points import user_hamster_points
from app.points_rules import rules_dict

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_STATIC_DIR = Path(__file__).resolve().parent / "static"
templates = Jinja2Templates(directory=_TEMPLATES_DIR)


def static_url(path: str) -> str:
    """URL de estático con versión según mtime (evita caché obsoleta del navegador)."""
    file_path = _STATIC_DIR / path
    if file_path.is_file():
        version = int(file_path.stat().st_mtime)
    else:
        version = 0
    return f"/static/{path}?v={version}"


def _category_id_for_nav(request: Request, context: dict[str, Any]) -> Optional[int]:
    selected = context.get("selected_category_id")
    if selected:
        return selected
    raw = request.query_params.get("category_id")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def render(
    name: str,
    context: dict[str, Any],
    *,
    request: Request,
    db: Session,
    current_user: Optional[User] = None,
):
    ctx = dict(context)
    ctx.setdefault("request", request)
    ctx.setdefault("current_user", current_user)
    flashed = consume_flash(request)
    ctx.setdefault("message", flashed["msg"] or "")
    ctx.setdefault("error", flashed["error"] or "")
    if flashed["pending_phone"]:
        ctx.setdefault("pending_phone", flashed["pending_phone"])
    if current_user is not None and "user_points" not in ctx:
        ctx["user_points"] = user_hamster_points(
            db, current_user.id, _category_id_for_nav(request, ctx)
        )
    cat_id = _category_id_for_nav(request, ctx)
    if "hp_rules" not in ctx:
        hp = rules_dict(db, cat_id)
        ctx["hp_rules"] = hp
        ctx.setdefault("SCORE_HIT_POINTS", hp["score_hit"])
        ctx.setdefault("CHAMPION_HIT_POINTS", hp["champion_hit"])
    return templates.TemplateResponse(name, ctx)


def _optional_user_from_session(request: Request) -> Optional[User]:
    try:
        from app.database import get_db

        user_id = request.session.get("user_id")
        if not user_id:
            return None
        db = next(get_db())
        try:
            return db.get(User, user_id)
        finally:
            db.close()
    except Exception:
        return None


def render_error_page(
    request: Request,
    *,
    status_code: int,
    title: str,
    message: str,
):
    current_user = _optional_user_from_session(request)
    ctx: dict[str, Any] = {
        "request": request,
        "status_code": status_code,
        "title": title,
        "error_detail": message,
        "current_user": current_user,
        "user_points": None,
        "message": "",
        "error": "",
    }
    return templates.TemplateResponse(
        "errors/error.html",
        ctx,
        status_code=status_code,
    )
