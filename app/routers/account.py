from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.account import delete_user_account
from app.auth import require_login
from app.database import get_db
from app.flash import flash
from app.models import ChampionPrediction, Prediction, User
from app.rendering import render

router = APIRouter(tags=["account"])

DELETE_CONFIRM = "ELIMINAR"


@router.get("/cuenta", response_class=HTMLResponse)
def account_settings(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    prediction_count = (
        db.query(func.count(Prediction.id))
        .filter(Prediction.user_id == current_user.id)
        .scalar()
        or 0
    )
    champion_count = (
        db.query(func.count(ChampionPrediction.id))
        .filter(ChampionPrediction.user_id == current_user.id)
        .scalar()
        or 0
    )
    return render(
        "account/settings.html",
        {
            "prediction_count": prediction_count,
            "champion_count": champion_count,
        },
        request=request,
        db=db,
        current_user=current_user,
    )


@router.post("/cuenta/eliminar")
def delete_account(
    request: Request,
    confirm: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    if confirm.strip().upper() != DELETE_CONFIRM:
        flash(request, error="Debes escribir ELIMINAR exactamente para confirmar.")
        return RedirectResponse("/cuenta", status_code=303)

    delete_user_account(db, current_user)
    request.session.clear()
    flash(request, msg="Tu cuenta y datos asociados fueron eliminados.")
    return RedirectResponse("/", status_code=303)
