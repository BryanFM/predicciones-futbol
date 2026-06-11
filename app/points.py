"""Hamster puntos — reglas y cálculo."""

from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    ChampionPrediction,
    Match,
    PointBonus,
    Prediction,
    PredictionResult,
    PredictionType,
    User,
    YapePurchaseRequest,
    YapePurchaseStatus,
)
from app.points_rules import RULE_CHAMPION_HIT, RULE_SCORE_HIT, get_hp

# Compatibilidad con plantillas que usan constantes (valores por defecto).
SCORE_HIT_POINTS = 5
CHAMPION_HIT_POINTS = 50


def user_hamster_points(
    db: Session,
    user_id: int,
    category_id: Optional[int] = None,
) -> dict:
    score_hp_unit = get_hp(db, RULE_SCORE_HIT, category_id)
    champion_hp_unit = get_hp(db, RULE_CHAMPION_HIT, category_id)

    score_query = db.query(Prediction).filter(
        Prediction.user_id == user_id,
        Prediction.type == PredictionType.SCORE,
        Prediction.result == PredictionResult.HIT,
    )
    if category_id:
        score_query = score_query.join(Match).filter(Match.category_id == category_id)
    score_hits = score_query.count()

    champ_query = db.query(ChampionPrediction).filter(
        ChampionPrediction.user_id == user_id,
        ChampionPrediction.result == PredictionResult.HIT,
    )
    if category_id:
        champ_query = champ_query.filter(ChampionPrediction.category_id == category_id)
    champion_hits = champ_query.count()

    score_pts = score_hits * score_hp_unit
    champion_pts = champion_hits * champion_hp_unit

    purchased_query = db.query(YapePurchaseRequest).filter(
        YapePurchaseRequest.user_id == user_id,
        YapePurchaseRequest.status == YapePurchaseStatus.APPROVED,
    )
    if category_id:
        purchased_query = purchased_query.filter(YapePurchaseRequest.category_id == category_id)
    purchased_pts = sum(row.hp_granted or 0 for row in purchased_query.all())

    bonus_query = db.query(PointBonus).filter(PointBonus.user_id == user_id)
    if category_id:
        bonus_query = bonus_query.filter(PointBonus.category_id == category_id)
    bonuses = bonus_query.all()
    bonus_pts = sum(b.hp for b in bonuses)
    referral_pts = sum(b.hp for b in bonuses if b.bonus_type.value.startswith("referral"))
    group_leader_pts = sum(b.hp for b in bonuses if b.bonus_type.value == "group_leader")

    return {
        "score_hits": score_hits,
        "champion_hits": champion_hits,
        "score_points": score_pts,
        "champion_points": champion_pts,
        "purchased_points": purchased_pts,
        "bonus_points": bonus_pts,
        "referral_points": referral_pts,
        "group_leader_points": group_leader_pts,
        "score_hp_unit": score_hp_unit,
        "champion_hp_unit": champion_hp_unit,
        "total": score_pts + champion_pts + purchased_pts + bonus_pts,
    }


def leaderboard(
    db: Session,
    category_id: Optional[int] = None,
    limit: int = 20,
) -> list[dict]:
    users = db.query(User).filter(User.phone_verified.is_(True)).all()
    rows = []
    for user in users:
        pts = user_hamster_points(db, user.id, category_id)
        if pts["total"] > 0:
            rows.append({"user": user, **pts})
            continue
        if not category_id:
            continue
        pending_scores = (
            db.query(Prediction)
            .join(Match)
            .filter(
                Prediction.user_id == user.id,
                Prediction.type == PredictionType.SCORE,
                Prediction.result == PredictionResult.PENDING,
                Match.category_id == category_id,
            )
            .count()
        )
        pending_champ = (
            db.query(ChampionPrediction)
            .filter(
                ChampionPrediction.user_id == user.id,
                ChampionPrediction.category_id == category_id,
            )
            .count()
        )
        if pending_scores or pending_champ:
            rows.append({"user": user, **pts})

    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows[:limit]
