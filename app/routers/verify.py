from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import require_login
from app.database import get_db
from app.flash import flash
from app.models import User
from app.phone_policy import enforce_unique_phone
from app.rendering import render
from app.sms import is_development_sms, normalize_phone, send_verification_code, twilio_is_configured, verify_code

router = APIRouter(tags=["verify"])


@router.get("/verificar-telefono", response_class=HTMLResponse)
def verify_phone_page(
    request: Request,
    current_user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    db.refresh(current_user)
    if current_user.phone_verified:
        return RedirectResponse("/", status_code=303)
    return render(
        "verify_phone.html",
        {
            "twilio_available": twilio_is_configured(),
            "sms_dev_mode": is_development_sms(),
        },
        request=request,
        db=db,
        current_user=current_user,
    )


@router.post("/verificar-telefono/enviar")
def send_code(
    request: Request,
    phone: str = Form(...),
    current_user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    normalized = normalize_phone(phone)
    if enforce_unique_phone():
        taken = db.query(User).filter(
            User.phone_verified.is_(True),
            User.phone_number == normalized,
            User.id != current_user.id,
        ).first()
        if taken:
            flash(request, error="Ese número ya está registrado", pending_phone=normalized)
            return RedirectResponse("/verificar-telefono", status_code=303)

    ok, msg = send_verification_code(db, current_user.id, normalized)
    if not ok:
        flash(request, error=msg, pending_phone=normalized)
    else:
        flash(request, msg=msg, pending_phone=normalized)
    return RedirectResponse("/verificar-telefono", status_code=303)


@router.post("/verificar-telefono/confirmar")
def confirm_code(
    request: Request,
    phone: str = Form(...),
    code: str = Form(...),
    current_user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    normalized = normalize_phone(phone)
    ok, msg = verify_code(db, current_user.id, normalized, code)
    if not ok:
        flash(request, error=msg, pending_phone=normalized)
        return RedirectResponse("/verificar-telefono", status_code=303)

    current_user.phone_number = normalized
    current_user.phone_verified = True
    from datetime import datetime
    current_user.phone_verified_at = datetime.utcnow()
    db.commit()
    request.session.pop("pending_phone", None)
    flash(request, msg="Teléfono verificado correctamente")
    return RedirectResponse("/", status_code=303)
