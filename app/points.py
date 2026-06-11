"""Hamster puntos — reglas y cálculo."""

from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    ChampionPrediction,
    Match,
    PointBonus,
    PointWager,
    Prediction,
    PredictionResult,
    PredictionType,
    User,
    WagerStatus,
    YapePurchaseRequest,
    YapePurchaseStatus,
)
from app.points_rules import RULE_CHAMPION_HIT, RULE_OUTCOME_HIT, RULE_SCORE_HIT, get_hp

# Compatibilidad con plantillas que usan constantes (valores por defecto).
SCORE_HIT_POINTS = 5
CHAMPION_HIT_POINTS = 50


def user_hamster_points(
    db: Session,
    user_id: int,
    category_id: Optional[int] = None,
) -> dict:
    score_hp_unit = get_hp(db, RULE_SCORE_HIT, category_id)
    outcome_hp_unit = get_hp(db, RULE_OUTCOME_HIT, category_id)
    champion_hp_unit = get_hp(db, RULE_CHAMPION_HIT, category_id)

    score_query = db.query(Prediction).filter(
        Prediction.user_id == user_id,
        Prediction.type == PredictionType.SCORE,
        Prediction.result == PredictionResult.HIT,
    )
    if category_id:
        score_query = score_query.join(Match).filter(Match.category_id == category_id)
    score_hits = score_query.count()

    outcome_query = db.query(Prediction).filter(
        Prediction.user_id == user_id,
        Prediction.type == PredictionType.OUTCOME,
        Prediction.result == PredictionResult.HIT,
    )
    if category_id:
        outcome_query = outcome_query.join(Match).filter(Match.category_id == category_id)
    outcome_hits = outcome_query.count()

    champ_query = db.query(ChampionPrediction).filter(
        ChampionPrediction.user_id == user_id,
        ChampionPrediction.result == PredictionResult.HIT,
    )
    if category_id:
        champ_query = champ_query.filter(ChampionPrediction.category_id == category_id)
    champion_hits = champ_query.count()

    score_pts = score_hits * score_hp_unit
    outcome_pts = outcome_hits * outcome_hp_unit
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

    wager_query = db.query(PointWager).filter(PointWager.user_id == user_id)
    if category_id:
        wager_query = wager_query.filter(PointWager.category_id == category_id)
    wagers = wager_query.all()
    wager_won = sum(w.stake_hp for w in wagers if w.status == WagerStatus.WON)
    wager_lost = sum(w.stake_hp for w in wagers if w.status == WagerStatus.LOST)
    wager_pending = sum(w.stake_hp for w in wagers if w.status == WagerStatus.PENDING)
    wager_net = wager_won - wager_lost

    total = score_pts + outcome_pts + champion_pts + purchased_pts + bonus_pts + wager_net

    return {
        "score_hits": score_hits,
        "outcome_hits": outcome_hits,
        "champion_hits": champion_hits,
        "score_points": score_pts,
        "outcome_points": outcome_pts,
        "champion_points": champion_pts,
        "purchased_points": purchased_pts,
        "bonus_points": bonus_pts,
        "referral_points": referral_pts,
        "group_leader_points": group_leader_pts,
        "wager_won_points": wager_won,
        "wager_lost_points": wager_lost,
        "wager_pending_stake": wager_pending,
        "wager_net": wager_net,
        "score_hp_unit": score_hp_unit,
        "outcome_hp_unit": outcome_hp_unit,
        "champion_hp_unit": champion_hp_unit,
        "total": total,
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


def points_history(
    db: Session,
    user_id: int,
    category_id: Optional[int] = None,
) -> list[dict]:
    """Movimientos de HP del usuario (positivos y negativos), ordenados del más reciente al más antiguo."""
    from datetime import datetime

    entries: list[dict] = []

    score_query = (
        db.query(Prediction)
        .join(Match)
        .filter(
            Prediction.user_id == user_id,
            Prediction.type == PredictionType.SCORE,
            Prediction.result == PredictionResult.HIT,
        )
    )
    if category_id:
        score_query = score_query.filter(Match.category_id == category_id)
    for pred in score_query.all():
        match = pred.match
        hp = get_hp(db, RULE_SCORE_HIT, match.category_id)
        entries.append(
            {
                "date": match.match_date,
                "kind": "score_hit",
                "icon": "🎯",
                "label": "Marcador exacto",
                "detail": f"{match.home_team} {match.home_score} - {match.away_score} {match.away_team}",
                "hp": hp,
            }
        )

    outcome_query = (
        db.query(Prediction)
        .join(Match)
        .filter(
            Prediction.user_id == user_id,
            Prediction.type == PredictionType.OUTCOME,
            Prediction.result == PredictionResult.HIT,
        )
    )
    if category_id:
        outcome_query = outcome_query.filter(Match.category_id == category_id)
    outcome_labels = {"1": "gana local", "X": "empate", "2": "gana visitante"}
    for pred in outcome_query.all():
        match = pred.match
        hp = get_hp(db, RULE_OUTCOME_HIT, match.category_id)
        entries.append(
            {
                "date": match.match_date,
                "kind": "outcome_hit",
                "icon": "⚽",
                "label": "Resultado acertado (1X2)",
                "detail": f"{match.home_team} vs {match.away_team} · {outcome_labels.get(pred.outcome_pick, pred.outcome_pick)}",
                "hp": hp,
            }
        )

    champ_query = db.query(ChampionPrediction).filter(
        ChampionPrediction.user_id == user_id,
        ChampionPrediction.result == PredictionResult.HIT,
    )
    if category_id:
        champ_query = champ_query.filter(ChampionPrediction.category_id == category_id)
    for cp in champ_query.all():
        hp = get_hp(db, RULE_CHAMPION_HIT, cp.category_id)
        entries.append(
            {
                "date": cp.created_at,
                "kind": "champion_hit",
                "icon": "🏆",
                "label": "Campeón acertado",
                "detail": cp.champion_team,
                "hp": hp,
            }
        )

    purchase_query = db.query(YapePurchaseRequest).filter(
        YapePurchaseRequest.user_id == user_id,
        YapePurchaseRequest.status == YapePurchaseStatus.APPROVED,
    )
    if category_id:
        purchase_query = purchase_query.filter(YapePurchaseRequest.category_id == category_id)
    for purchase in purchase_query.all():
        entries.append(
            {
                "date": purchase.reviewed_at or purchase.created_at,
                "kind": "purchase",
                "icon": "💜",
                "label": "Compra con Yape",
                "detail": f"S/ {purchase.amount_soles} · operación {purchase.operation_code}",
                "hp": purchase.hp_granted or 0,
            }
        )

    bonus_query = db.query(PointBonus).filter(PointBonus.user_id == user_id)
    if category_id:
        bonus_query = bonus_query.filter(PointBonus.category_id == category_id)
    bonus_labels = {
        "referral_referrer": ("👥", "Referido verificado"),
        "referral_referred": ("🎁", "Bonus de invitación"),
        "group_leader": ("⭐", "Líder de grupo"),
    }
    for bonus in bonus_query.all():
        icon, label = bonus_labels.get(bonus.bonus_type.value, ("✨", "Bono"))
        entries.append(
            {
                "date": bonus.created_at,
                "kind": bonus.bonus_type.value,
                "icon": icon,
                "label": label,
                "detail": bonus.notes or "",
                "hp": bonus.hp,
            }
        )

    from app.models import PointWager as _PW  # evitar sombra local

    wager_query = db.query(_PW).filter(_PW.user_id == user_id)
    if category_id:
        wager_query = wager_query.filter(_PW.category_id == category_id)
    for wager in wager_query.all():
        match = wager.match
        versus = f"{match.home_team} vs {match.away_team}" if match else ""
        pick_labels = {"1": "gana local", "X": "empate", "2": "gana visitante"}
        pick_label = pick_labels.get(wager.pick, wager.pick)
        if wager.status == WagerStatus.WON:
            entries.append(
                {
                    "date": wager.settled_at or wager.created_at,
                    "kind": "wager_won",
                    "icon": "🎰",
                    "label": "Apuesta ganada",
                    "detail": f"{versus} · {pick_label} · apostaste {wager.stake_hp} HP",
                    "hp": wager.stake_hp,
                }
            )
        elif wager.status == WagerStatus.LOST:
            entries.append(
                {
                    "date": wager.settled_at or wager.created_at,
                    "kind": "wager_lost",
                    "icon": "💔",
                    "label": "Apuesta perdida",
                    "detail": f"{versus} · {pick_label}",
                    "hp": -wager.stake_hp,
                }
            )
        else:
            entries.append(
                {
                    "date": wager.created_at,
                    "kind": "wager_pending",
                    "icon": "⏳",
                    "label": "Apuesta en juego",
                    "detail": f"{versus} · {pick_label}",
                    "hp": 0,
                    "pending_stake": wager.stake_hp,
                }
            )

    entries.sort(key=lambda e: e["date"] or datetime.min, reverse=True)
    return entries
