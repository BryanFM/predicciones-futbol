"""Sistema de referidos."""

from __future__ import annotations

import secrets
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Category, PointBonus, PointBonusType, User
from app.points_rules import RULE_REFERRAL_REFERRED, RULE_REFERRAL_REFERRER, get_hp


def generate_referral_code(db: Session) -> str:
    for _ in range(20):
        code = secrets.token_hex(4).upper()[:8]
        if not db.query(User).filter(User.referral_code == code).first():
            return code
    raise RuntimeError("No se pudo generar código de referido")


def ensure_referral_code(db: Session, user: User) -> str:
    if user.referral_code:
        return user.referral_code
    user.referral_code = generate_referral_code(db)
    db.commit()
    db.refresh(user)
    return user.referral_code


def resolve_referrer_id(db: Session, code: Optional[str]) -> Optional[int]:
    if not code:
        return None
    normalized = code.strip().upper()
    if len(normalized) < 4:
        return None
    referrer = db.query(User).filter(User.referral_code == normalized).first()
    return referrer.id if referrer else None


def capture_referral_code(request, code: Optional[str]) -> None:
    ref = (code or "").strip().upper()
    if len(ref) >= 4:
        request.session["referral_code"] = ref


def apply_referred_by(db: Session, user: User, referred_by_id: Optional[int]) -> bool:
    """Asigna referidor si el usuario aún no tiene uno. Devuelve True si se aplicó."""
    if not referred_by_id or user.referred_by_id or referred_by_id == user.id:
        return False
    referrer = db.get(User, referred_by_id)
    if not referrer or referrer.email.lower() == user.email.lower():
        return False
    user.referred_by_id = referred_by_id
    return True


def pop_pending_referral_code(request) -> Optional[str]:
    return request.session.pop("referral_code", None) or None


def referral_link(request, code: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/?ref={code}"


def _bonus_exists(
    db: Session,
    user_id: int,
    category_id: int,
    bonus_type: PointBonusType,
    reference_key: str,
) -> bool:
    return (
        db.query(PointBonus)
        .filter(
            PointBonus.user_id == user_id,
            PointBonus.category_id == category_id,
            PointBonus.bonus_type == bonus_type,
            PointBonus.reference_key == reference_key,
        )
        .first()
        is not None
    )


def credit_referral_on_verify(db: Session, user: User) -> int:
    """Acredita HP de referido al verificar celular. Devuelve bonos creados."""
    if not user.referred_by_id or user.referred_by_id == user.id:
        return 0
    referrer = db.get(User, user.referred_by_id)
    if not referrer:
        return 0

    ref_key = f"user:{user.id}"
    created = 0
    categories = db.query(Category).filter(Category.is_active.is_(True)).all()
    for cat in categories:
        hp_referrer = get_hp(db, RULE_REFERRAL_REFERRER, cat.id)
        if hp_referrer > 0 and not _bonus_exists(
            db, referrer.id, cat.id, PointBonusType.REFERRAL_REFERRER, ref_key
        ):
            db.add(
                PointBonus(
                    user_id=referrer.id,
                    category_id=cat.id,
                    bonus_type=PointBonusType.REFERRAL_REFERRER,
                    hp=hp_referrer,
                    reference_key=ref_key,
                    notes=f"Referido: {user.name}",
                )
            )
            created += 1

        hp_referred = get_hp(db, RULE_REFERRAL_REFERRED, cat.id)
        if hp_referred > 0 and not _bonus_exists(
            db, user.id, cat.id, PointBonusType.REFERRAL_REFERRED, ref_key
        ):
            db.add(
                PointBonus(
                    user_id=user.id,
                    category_id=cat.id,
                    bonus_type=PointBonusType.REFERRAL_REFERRED,
                    hp=hp_referred,
                    reference_key=ref_key,
                    notes=f"Invitado por {referrer.name}",
                )
            )
            created += 1

    if created:
        db.commit()
    return created


def referral_stats(db: Session, user_id: int, category_id: Optional[int] = None) -> dict:
    referred_users = db.query(User).filter(User.referred_by_id == user_id).all()
    verified = [u for u in referred_users if u.phone_verified]

    bonus_query = db.query(PointBonus).filter(
        PointBonus.user_id == user_id,
        PointBonus.bonus_type == PointBonusType.REFERRAL_REFERRER,
    )
    if category_id:
        bonus_query = bonus_query.filter(PointBonus.category_id == category_id)
    referral_hp = sum(b.hp for b in bonus_query.all())

    return {
        "total_invited": len(referred_users),
        "verified_invited": len(verified),
        "referral_hp": referral_hp,
        "referred_users": verified,
    }


def admin_users_referral_maps(db: Session, users: list[User]) -> dict:
    """Datos de referidos para la tabla admin de usuarios."""
    from sqlalchemy import func

    user_ids = [u.id for u in users]
    referrer_ids = {u.referred_by_id for u in users if u.referred_by_id}

    referrers: dict[int, User] = {}
    if referrer_ids:
        referrers = {
            u.id: u
            for u in db.query(User).filter(User.id.in_(referrer_ids)).all()
        }

    invited_total: dict[int, int] = {}
    invited_verified: dict[int, int] = {}
    if user_ids:
        invited_total = dict(
            db.query(User.referred_by_id, func.count(User.id))
            .filter(User.referred_by_id.in_(user_ids))
            .group_by(User.referred_by_id)
            .all()
        )
        invited_verified = dict(
            db.query(User.referred_by_id, func.count(User.id))
            .filter(
                User.referred_by_id.in_(user_ids),
                User.phone_verified.is_(True),
            )
            .group_by(User.referred_by_id)
            .all()
        )

    return {
        "referrers": referrers,
        "invited_total": invited_total,
        "invited_verified": invited_verified,
    }
