"""Apuestas de Hamster puntos: apuesta al 1/X/2 de un partido y duplica o pierde lo apostado."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models import Match, PointWager, User, WagerStatus
from app.timezone import peru_now

WAGER_PICKS = {
    "1": "Gana local",
    "X": "Empate",
    "2": "Gana visitante",
}

MIN_STAKE = 1
MAX_STAKE = 9999


def match_outcome(match: Match) -> Optional[str]:
    if not match.is_finished:
        return None
    if match.home_score > match.away_score:
        return "1"
    if match.home_score < match.away_score:
        return "2"
    return "X"


def wager_balance(db: Session, user_id: int, category_id: Optional[int] = None) -> dict:
    """Total HP, HP en juego (apuestas pendientes) y disponible para apostar."""
    from app.points import user_hamster_points

    points = user_hamster_points(db, user_id, category_id)
    pending = points["wager_pending_stake"]
    return {
        "total": points["total"],
        "pending_stake": pending,
        "available": max(points["total"] - pending, 0),
    }


def place_wager(
    db: Session,
    user: User,
    match: Match,
    pick: str,
    stake: int,
) -> PointWager:
    if pick not in WAGER_PICKS:
        raise ValueError("Elige un resultado válido: local, empate o visitante.")
    if stake < MIN_STAKE:
        raise ValueError(f"La apuesta mínima es {MIN_STAKE} HP.")
    if stake > MAX_STAKE:
        raise ValueError(f"La apuesta máxima es {MAX_STAKE} HP.")
    if not match.predictions_open:
        raise ValueError("Este partido ya no acepta apuestas (cierra 5 min antes del inicio).")

    existing = (
        db.query(PointWager)
        .filter(
            PointWager.user_id == user.id,
            PointWager.match_id == match.id,
            PointWager.status == WagerStatus.PENDING,
        )
        .first()
    )
    if existing:
        raise ValueError("Ya tienes una apuesta activa en este partido.")

    balance = wager_balance(db, user.id, match.category_id)
    if stake > balance["available"]:
        raise ValueError(
            f"No te alcanzan los HP: tienes {balance['available']} disponibles en este torneo."
        )

    wager = PointWager(
        user_id=user.id,
        match_id=match.id,
        category_id=match.category_id,
        pick=pick,
        stake_hp=stake,
        status=WagerStatus.PENDING,
    )
    db.add(wager)
    db.commit()
    db.refresh(wager)
    return wager


def cancel_wager(db: Session, user: User, wager_id: int) -> None:
    wager = db.get(PointWager, wager_id)
    if not wager or wager.user_id != user.id:
        raise ValueError("Apuesta no encontrada.")
    if wager.status != WagerStatus.PENDING:
        raise ValueError("Esta apuesta ya fue liquidada.")
    if not wager.match.predictions_open:
        raise ValueError("El partido ya cerró: no puedes retirar la apuesta.")
    db.delete(wager)
    db.commit()


def settle_wagers_for_match(db: Session, match: Match) -> None:
    """Liquida (o revierte a pendiente si se borró el marcador) las apuestas del partido."""
    outcome = match_outcome(match)
    wagers = db.query(PointWager).filter(PointWager.match_id == match.id).all()
    now = peru_now()
    for wager in wagers:
        if outcome is None:
            wager.status = WagerStatus.PENDING
            wager.settled_at = None
        else:
            wager.status = WagerStatus.WON if wager.pick == outcome else WagerStatus.LOST
            wager.settled_at = now
    db.commit()


def user_wagers(
    db: Session,
    user_id: int,
    category_id: Optional[int] = None,
    limit: int = 100,
) -> list[PointWager]:
    query = (
        db.query(PointWager)
        .options(joinedload(PointWager.match))
        .filter(PointWager.user_id == user_id)
    )
    if category_id:
        query = query.filter(PointWager.category_id == category_id)
    return query.order_by(PointWager.created_at.desc()).limit(limit).all()
