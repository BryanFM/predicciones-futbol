"""Rutas de referidos para usuarios."""

from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from sqlalchemy.orm import Session

from app.auth import require_login
from app.database import get_db
from app.models import Category, User
from app.points_rules import get_rules_for_admin, rules_dict
from app.referrals import ensure_referral_code, referral_link, referral_stats
from app.rendering import render

router = APIRouter(tags=["referrals"])


@router.get("/referidos", response_class=HTMLResponse)
def referrals_page(
    request: Request,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    categories = db.query(Category).filter(Category.is_active.is_(True)).order_by(Category.name).all()
    selected = category_id or (categories[0].id if categories else None)
    code = ensure_referral_code(db, current_user)
    stats = referral_stats(db, current_user.id, selected)
    hp_rules = rules_dict(db, selected)

    return render(
        "referrals/index.html",
        {
            "categories": categories,
            "selected_category_id": selected,
            "referral_code": code,
            "referral_url": referral_link(request, code),
            "stats": stats,
            "hp_rules": hp_rules,
            "points_rules": get_rules_for_admin(db, selected),
        },
        request=request,
        db=db,
        current_user=current_user,
    )
