"""Rutas de apuestas de HP e historial de puntos."""

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from sqlalchemy.orm import Session

from app.auth import require_verified
from app.database import get_db
from app.hf_response import ajax_error, ajax_or_redirect, safe_back
from app.models import Category, Match, PointWager, User, WagerStatus
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


@router.post("/apuestas")
def create_wager(
    request: Request,
    match_id: int = Form(...),
    pick: str = Form(...),
    stake: int = Form(...),
    category_id: Optional[int] = Form(None),
    return_to: str = Form(""),
    return_category_id: Optional[int] = Form(None),
    return_match_date: str = Form(""),
    return_group: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified),
):
    from app.hf_response import home_url

    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(404)

    cat_id = category_id or return_category_id or match.category_id
    back = safe_back(
        return_to,
        home_url(cat_id, return_match_date.strip() or None, return_group.strip() or None),
    )
    try:
        wager = place_wager(db, current_user, match, pick.strip().upper(), stake)
    except ValueError as exc:
        return ajax_error(request, back, str(exc))

    from app.points import user_hamster_points

    return ajax_or_redirect(
        request,
        back,
        {
            "match_id": match_id,
            "wager_id": wager.id,
            "pick": wager.pick,
            "pick_label": WAGER_PICKS[wager.pick],
            "stake_hp": wager.stake_hp,
            "status": wager.status.value,
            "user_points": user_hamster_points(db, current_user.id, cat_id),
            "wager_balance": wager_balance(db, current_user.id, cat_id),
        },
    )


@router.post("/apuestas/{wager_id}/cancelar")
def remove_wager(
    request: Request,
    wager_id: int,
    category_id: Optional[int] = Form(None),
    return_to: str = Form(""),
    return_category_id: Optional[int] = Form(None),
    return_match_date: str = Form(""),
    return_group: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified),
):
    from app.hf_response import home_url

    cat_id = category_id or return_category_id
    back = safe_back(
        return_to,
        home_url(cat_id, return_match_date.strip() or None, return_group.strip() or None)
        if cat_id
        else "/apuestas",
    )
    try:
        wager = db.get(PointWager, wager_id)
        if not wager or wager.user_id != current_user.id:
            raise ValueError("Apuesta no encontrada.")
        match_id = wager.match_id
        cancel_wager(db, current_user, wager_id)
    except ValueError as exc:
        return ajax_error(request, back, str(exc))

    from app.points import user_hamster_points

    return ajax_or_redirect(
        request,
        back,
        {
            "match_id": match_id,
            "wager_cancelled": True,
            "user_points": user_hamster_points(db, current_user.id, cat_id),
            "wager_balance": wager_balance(db, current_user.id, cat_id),
        },
    )


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
