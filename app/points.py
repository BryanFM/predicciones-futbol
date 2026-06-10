"""Hamster puntos — reglas y cálculo."""

from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    ChampionPrediction,
    Match,
    Prediction,
    PredictionResult,
    PredictionType,
    User,
    YapePurchaseRequest,
    YapePurchaseStatus,
)

SCORE_HIT_POINTS = 5
CHAMPION_HIT_POINTS = 50


def user_hamster_points(
    db: Session,
    user_id: int,
    category_id: Optional[int] = None,
) -> dict:
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

    score_pts = score_hits * SCORE_HIT_POINTS
    champion_pts = champion_hits * CHAMPION_HIT_POINTS

    purchased_query = db.query(YapePurchaseRequest).filter(
        YapePurchaseRequest.user_id == user_id,
        YapePurchaseRequest.status == YapePurchaseStatus.APPROVED,
    )
    if category_id:
        purchased_query = purchased_query.filter(YapePurchaseRequest.category_id == category_id)
    purchased_pts = sum(row.hp_granted or 0 for row in purchased_query.all())

    return {
        "score_hits": score_hits,
        "champion_hits": champion_hits,
        "score_points": score_pts,
        "champion_points": champion_pts,
        "purchased_points": purchased_pts,
        "total": score_pts + champion_pts + purchased_pts,
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
