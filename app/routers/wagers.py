"""Rutas de apuestas de HP e historial de puntos."""

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from sqlalchemy.orm import Session

from app.auth import require_verified
from app.database import get_db
from app.flash import flash
from app.models import Category, Match, User, WagerStatus
from app.points import points_history, user_hamster_points
from app.rendering import render
from app.timezone import peru_now
from app.wagers import (
    MAX_STAKE,
    MIN_STAKE,
    WAGER_PICKS,
    cancel_wager,
    place_wager,
    user_wagers,
    wager_balance,
)

router = APIRouter(tags=["wagers"])


def _selected_category(db: Session, category_id: Optional[int]) -> tuple[list[Category], Optional[int]]:
    categories = (
        db.query(Category).filter(Category.is_active.is_(True)).order_by(Category.name).all()
    )
    selected = category_id or (categories[0].id if categories else None)
    return categories, selected


@router.get("/apuestas", response_class=HTMLResponse)
def wagers_page(
    request: Request,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified),
):
    categories, selected = _selected_category(db, category_id)

    open_matches = (
        db.query(Match)
        .filter(
            Match.category_id == selected,
            Match.home_score.is_(None),
            Match.match_date > peru_now(),
        )
        .order_by(Match.match_date)
        .limit(40)
        .all()
        if selected
        else []
    )
    open_matches = [m for m in open_matches if m.predictions_open]

    my_wagers = user_wagers(db, current_user.id, selected)
    pending_match_ids = {w.match_id for w in my_wagers if w.status == WagerStatus.PENDING}
    balance = wager_balance(db, current_user.id, selected)

    return render(
        "wagers/index.html",
        {
            "categories": categories,
            "selected_category_id": selected,
            "open_matches": open_matches,
            "my_wagers": my_wagers,
            "pending_match_ids": pending_match_ids,
            "balance": balance,
            "picks": WAGER_PICKS,
            "min_stake": MIN_STAKE,
            "max_stake": MAX_STAKE,
            "WagerStatus": WagerStatus,
        },
        request=request,
        db=db,
        current_user=current_user,
    )


def _safe_back(return_to: str, fallback: str) -> str:
    """Solo rutas internas (evita open redirect)."""
    if return_to.startswith("/") and not return_to.startswith("//"):
        return return_to
    return fallback


@router.post("/apuestas")
def create_wager(
    request: Request,
    match_id: int = Form(...),
    pick: str = Form(...),
    stake: int = Form(...),
    category_id: Optional[int] = Form(None),
    return_to: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified),
):
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(404)

    back = _safe_back(return_to, f"/apuestas?category_id={category_id or match.category_id}")
    try:
        wager = place_wager(db, current_user, match, pick.strip().upper(), stake)
    except ValueError as exc:
        flash(request, error=str(exc))
        return RedirectResponse(back, status_code=303)

    flash(
        request,
        msg=(
            f"Apuesta registrada: {wager.stake_hp} HP a «{WAGER_PICKS[wager.pick]}» en "
            f"{match.home_team} vs {match.away_team}. Si aciertas ganas {wager.stake_hp} HP extra."
        ),
    )
    return RedirectResponse(back, status_code=303)


@router.post("/apuestas/{wager_id}/cancelar")
def remove_wager(
    request: Request,
    wager_id: int,
    category_id: Optional[int] = Form(None),
    return_to: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified),
):
    back = _safe_back(return_to, f"/apuestas{f'?category_id={category_id}' if category_id else ''}")
    try:
        cancel_wager(db, current_user, wager_id)
    except ValueError as exc:
        flash(request, error=str(exc))
        return RedirectResponse(back, status_code=303)
    flash(request, msg="Apuesta retirada: tus HP vuelven a estar disponibles.")
    return RedirectResponse(back, status_code=303)


@router.get("/mis-puntos", response_class=HTMLResponse)
def points_history_page(
    request: Request,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified),
):
    categories, selected = _selected_category(db, category_id)
    history = points_history(db, current_user.id, selected)
    points = user_hamster_points(db, current_user.id, selected)
    balance = wager_balance(db, current_user.id, selected)

    return render(
        "points/history.html",
        {
            "categories": categories,
            "selected_category_id": selected,
            "history": history,
            "points": points,
            "balance": balance,
            "user_points": points,
        },
        request=request,
        db=db,
        current_user=current_user,
    )
