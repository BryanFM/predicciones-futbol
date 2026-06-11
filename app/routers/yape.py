"""Compras Yape — solicitudes de usuario."""

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.auth import require_login, require_verified
from app.database import get_db
from app.flash import flash
from app.models import Category, User, YapePurchaseRequest, YapePurchaseStatus
from app.rendering import render
from app.yape_policy import (
    MAX_PENDING_REQUESTS,
    OPERATION_CODE_RE,
    YAPE_PACKAGES,
    get_package,
    yape_payments_enabled,
    yape_recipient_phone,
)
from app.yape_qr import yape_qr_available, yape_qr_content

router = APIRouter(tags=["yape"])


def _require_yape_enabled() -> None:
    if not yape_payments_enabled():
        raise HTTPException(404, "Pagos Yape no disponibles")


@router.get("/comprar-yape", response_class=HTMLResponse)
def purchase_form(
    request: Request,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified),
):
    _require_yape_enabled()
    categories = db.query(Category).filter(Category.is_active.is_(True)).order_by(Category.name).all()
    selected = category_id or (categories[0].id if categories else None)
    selected_category = next((c for c in categories if c.id == selected), None)
    pending_count = (
        db.query(YapePurchaseRequest)
        .filter(
            YapePurchaseRequest.user_id == current_user.id,
            YapePurchaseRequest.status == YapePurchaseStatus.PENDING,
        )
        .count()
    )
    recipient = yape_recipient_phone()
    qr_available = yape_qr_available()
    yape_ready = qr_available or bool(recipient)

    return render(
        "yape/purchase.html",
        {
            "categories": categories,
            "selected_category_id": selected,
            "selected_category": selected_category,
            "packages": YAPE_PACKAGES,
            "yape_ready": yape_ready,
            "yape_qr_available": qr_available,
            "pending_count": pending_count,
            "max_pending": MAX_PENDING_REQUESTS,
        },
        request=request,
        db=db,
        current_user=current_user,
    )


@router.post("/comprar-yape")
def submit_purchase(
    request: Request,
    package_id: str = Form(...),
    category_id: int = Form(...),
    operation_code: str = Form(...),
    user_note: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified),
):
    _require_yape_enabled()

    pkg = get_package(package_id)
    if not pkg:
        flash(request, error="Paquete no válido.")
        return RedirectResponse("/comprar-yape", status_code=303)

    category = db.get(Category, category_id)
    if not category or not category.is_active:
        flash(request, error="Torneo no válido.")
        return RedirectResponse(f"/comprar-yape?category_id={category_id}", status_code=303)

    code = operation_code.strip().upper()
    if not OPERATION_CODE_RE.match(code):
        flash(request, error="Código de operación inválido (6–14 caracteres alfanuméricos).")
        return RedirectResponse(f"/comprar-yape?category_id={category_id}", status_code=303)

    pending_count = (
        db.query(YapePurchaseRequest)
        .filter(
            YapePurchaseRequest.user_id == current_user.id,
            YapePurchaseRequest.status == YapePurchaseStatus.PENDING,
        )
        .count()
    )
    if pending_count >= MAX_PENDING_REQUESTS:
        flash(request, error=f"Tienes {MAX_PENDING_REQUESTS} solicitudes pendientes. Espera la revisión del admin.")
        return RedirectResponse("/mis-compras-yape", status_code=303)

    duplicate = db.query(YapePurchaseRequest).filter(YapePurchaseRequest.operation_code == code).first()
    if duplicate:
        flash(request, error="Ese código de operación ya fue registrado.")
        return RedirectResponse(f"/comprar-yape?category_id={category_id}", status_code=303)

    note = user_note.strip()[:255] or None
    db.add(
        YapePurchaseRequest(
            user_id=current_user.id,
            category_id=category.id,
            package_id=pkg["id"],
            amount_soles=pkg["soles"],
            hp_requested=pkg["hp"],
            operation_code=code,
            user_note=note,
        )
    )
    db.commit()
    flash(
        request,
        msg="Solicitud enviada. Un admin revisará tu pago Yape y te notificará aquí.",
    )
    return RedirectResponse("/mis-compras-yape", status_code=303)


@router.get("/yape/qr")
def yape_qr_image(
    download: bool = False,
    _: User = Depends(require_verified),
):
    """QR privado: solo usuarios con sesión y celular verificado."""
    _require_yape_enabled()
    content = yape_qr_content()
    if not content:
        raise HTTPException(404, "QR Yape no configurado")
    data, media_type = content
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(media_type, "png")
    disposition = (
        f'attachment; filename="yape-hamster-fijas.{ext}"'
        if download
        else "inline"
    )
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": disposition,
        },
    )


@router.get("/mis-compras-yape", response_class=HTMLResponse)
def my_purchases(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    _require_yape_enabled()
    purchases = (
        db.query(YapePurchaseRequest)
        .filter(YapePurchaseRequest.user_id == current_user.id)
        .order_by(YapePurchaseRequest.created_at.desc())
        .limit(50)
        .all()
    )
    categories = {c.id: c for c in db.query(Category).all()}
    packages = {p["id"]: p for p in YAPE_PACKAGES}

    return render(
        "yape/my_requests.html",
        {
            "purchases": purchases,
            "categories": categories,
            "packages": packages,
        },
        request=request,
        db=db,
        current_user=current_user,
    )
