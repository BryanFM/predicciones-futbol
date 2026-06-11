"""Operaciones de cuenta de usuario."""

import hashlib

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    AccountDeletion,
    ChampionPrediction,
    PhoneVerification,
    PointBonus,
    Prediction,
    User,
    YapePurchaseRequest,
)
from app.timezone import peru_now, utc_naive_to_pet


def email_fingerprint(email: str) -> str:
    normalized = email.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def record_account_deletion(
    db: Session,
    user: User,
    *,
    deleted_by: str = "self",
) -> AccountDeletion:
    prediction_count = (
        db.query(func.count(Prediction.id)).filter(Prediction.user_id == user.id).scalar() or 0
    )
    champion_count = (
        db.query(func.count(ChampionPrediction.id))
        .filter(ChampionPrediction.user_id == user.id)
        .scalar()
        or 0
    )
    entry = AccountDeletion(
        former_user_id=user.id,
        email_hash=email_fingerprint(user.email),
        registered_at=utc_naive_to_pet(user.created_at),
        deleted_at=peru_now(),
        phone_verified=user.phone_verified,
        was_admin=user.is_admin,
        prediction_count=prediction_count,
        champion_count=champion_count,
        deleted_by=deleted_by,
    )
    db.add(entry)
    return entry


def delete_user_account(db: Session, user: User, *, deleted_by: str = "self") -> AccountDeletion:
    entry = record_account_deletion(db, user, deleted_by=deleted_by)
    user_id = user.id

    db.query(User).filter(User.referred_by_id == user_id).update(
        {User.referred_by_id: None}, synchronize_session=False
    )
    db.query(YapePurchaseRequest).filter(YapePurchaseRequest.reviewed_by_id == user_id).update(
        {YapePurchaseRequest.reviewed_by_id: None}, synchronize_session=False
    )
    from app.models import PointWager

    db.query(PointWager).filter(PointWager.user_id == user_id).delete()
    db.query(PointBonus).filter(PointBonus.user_id == user_id).delete()
    db.query(YapePurchaseRequest).filter(YapePurchaseRequest.user_id == user_id).delete()
    db.query(PhoneVerification).filter(PhoneVerification.user_id == user_id).delete()
    db.query(Prediction).filter(Prediction.user_id == user_id).delete()
    db.query(ChampionPrediction).filter(ChampionPrediction.user_id == user_id).delete()
    db.delete(user)
    db.commit()
    return entry
