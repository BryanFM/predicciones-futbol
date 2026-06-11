"""Operaciones admin sobre compras Yape."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Category, User, YapePurchaseRequest, YapePurchaseStatus
from app.timezone import peru_now
from app.yape_policy import OPERATION_CODE_RE, YAPE_PACKAGES, get_package


def max_hp_for_package(package_id: str, hp_requested: int) -> int:
    pkg = get_package(package_id)
    return (pkg["hp"] * 2) if pkg else hp_requested * 2


def validate_hp_grant(package_id: str, hp_requested: int, hp_granted: int) -> Optional[str]:
    if hp_granted < 1:
        return "Los HP deben ser al menos 1."
    if hp_granted > max_hp_for_package(package_id, hp_requested):
        return "HP otorgados fuera de rango permitido."
    return None


def approve_purchase(
    db: Session,
    purchase: YapePurchaseRequest,
    admin: User,
    hp_granted: int,
    admin_notes: str = "",
) -> Optional[str]:
    err = validate_hp_grant(purchase.package_id, purchase.hp_requested, hp_granted)
    if err:
        return err
    purchase.status = YapePurchaseStatus.APPROVED
    purchase.hp_granted = hp_granted
    purchase.reviewed_by_id = admin.id
    purchase.reviewed_at = peru_now()
    purchase.admin_notes = admin_notes.strip()[:255] or None
    db.commit()
    return None


def register_and_approve_purchase(
    db: Session,
    *,
    admin: User,
    user_id: int,
    category_id: int,
    package_id: str,
    operation_code: str,
    hp_granted: Optional[int] = None,
    user_note: str = "",
    admin_notes: str = "",
) -> tuple[Optional[YapePurchaseRequest], Optional[str]]:
    user = db.get(User, user_id)
    if not user:
        return None, "Usuario no encontrado."
    if not user.phone_verified:
        return None, "El usuario debe tener celular verificado."

    pkg = get_package(package_id)
    if not pkg:
        return None, "Paquete no válido."

    category = db.get(Category, category_id)
    if not category or not category.is_active:
        return None, "Torneo no válido."

    code = operation_code.strip().upper()
    if not OPERATION_CODE_RE.match(code):
        return None, "Código de operación inválido."

    if db.query(YapePurchaseRequest).filter(YapePurchaseRequest.operation_code == code).first():
        return None, "Ese código de operación ya está registrado."

    granted = hp_granted if hp_granted and hp_granted > 0 else pkg["hp"]
    err = validate_hp_grant(pkg["id"], pkg["hp"], granted)
    if err:
        return None, err

    purchase = YapePurchaseRequest(
        user_id=user.id,
        category_id=category.id,
        package_id=pkg["id"],
        amount_soles=pkg["soles"],
        hp_requested=pkg["hp"],
        operation_code=code,
        user_note=user_note.strip()[:255] or None,
        status=YapePurchaseStatus.APPROVED,
        hp_granted=granted,
        reviewed_by_id=admin.id,
        reviewed_at=peru_now(),
        admin_notes=admin_notes.strip()[:255] or "Registrado y acreditado por admin",
    )
    db.add(purchase)
    db.commit()
    db.refresh(purchase)
    return purchase, None
