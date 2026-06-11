"""Niveles de premios desbloqueables según usuarios verificados."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import PlatformSetting, User
from app.timezone import peru_now

MAX_PRIZE_TIER_KEY = "max_prize_tier_level"

PRIZE_TIERS: list[dict[str, Any]] = [
    {
        "level": 1,
        "threshold": 0,
        "label": "Arranque",
        "prizes": {
            "podio": {"1": "S/ 150 Yape", "2": "S/ 70 Yape", "3": "S/ 30 Yape"},
            "sorteo": None,
        },
    },
    {
        "level": 2,
        "threshold": 300,
        "label": "Nivel 2",
        "prizes": {
            "podio": {"1": "S/ 500", "2": "S/ 150", "3": "S/ 50"},
            "sorteo": "S/ 100",
        },
    },
    {
        "level": 3,
        "threshold": 800,
        "label": "Nivel 3",
        "prizes": {
            "podio": {"1": 'TV 60"', "2": "S/ 300", "3": "S/ 100"},
            "sorteo": "S/ 300",
        },
    },
    {
        "level": 4,
        "threshold": 1500,
        "label": "Nivel 4",
        "prizes": {
            "podio": {"1": 'TV 60"', "2": "S/ 400", "3": "S/ 150"},
            "sorteo": "S/ 600 Yape",
        },
    },
    {
        "level": 5,
        "threshold": 2500,
        "label": "Nivel 5",
        "prizes": {
            "podio": {"1": 'TV 60"', "2": "S/ 500", "3": "S/ 200"},
            "sorteo": "PS5",
        },
    },
]


def count_verified_users(db: Session) -> int:
    return db.query(User).filter(User.phone_verified.is_(True)).count()


def tier_for_verified_count(count: int) -> dict[str, Any]:
    active = PRIZE_TIERS[0]
    for tier in PRIZE_TIERS:
        if count >= tier["threshold"]:
            active = tier
        else:
            break
    return active


def tier_by_level(level: int) -> dict[str, Any]:
    for tier in PRIZE_TIERS:
        if tier["level"] == level:
            return tier
    return PRIZE_TIERS[0]


def get_stored_max_tier_level(db: Session) -> int:
    row = db.get(PlatformSetting, MAX_PRIZE_TIER_KEY)
    if not row:
        return 1
    try:
        return max(1, min(int(row.value), PRIZE_TIERS[-1]["level"]))
    except ValueError:
        return 1


def update_stored_max_tier_level(db: Session, level: int) -> int:
    stored = get_stored_max_tier_level(db)
    new_level = max(stored, level)
    if new_level <= stored:
        return stored

    row = db.get(PlatformSetting, MAX_PRIZE_TIER_KEY)
    if row:
        row.value = str(new_level)
        row.updated_at = peru_now()
    else:
        db.add(PlatformSetting(key=MAX_PRIZE_TIER_KEY, value=str(new_level)))
    db.commit()
    return new_level


def get_current_tier(db: Session) -> dict[str, Any]:
    verified_count = count_verified_users(db)
    computed_level = tier_for_verified_count(verified_count)["level"]
    effective_level = update_stored_max_tier_level(db, computed_level)
    current_tier = tier_by_level(effective_level)

    next_tier: Optional[dict[str, Any]] = None
    for tier in PRIZE_TIERS:
        if tier["level"] == effective_level + 1:
            next_tier = tier
            break

    if next_tier:
        target = next_tier["threshold"]
        percent = min(100.0, (verified_count / target * 100) if target else 100.0)
        progreso = {
            "current": verified_count,
            "target": target,
            "percent": round(percent, 1),
        }
    else:
        progreso = {
            "current": verified_count,
            "target": None,
            "percent": 100.0,
        }

    locked_tiers = [tier for tier in PRIZE_TIERS if tier["level"] > effective_level]

    return {
        "verified_count": verified_count,
        "current_tier": current_tier,
        "next_tier": next_tier,
        "progreso": progreso,
        "locked_tiers": locked_tiers,
        "is_max_tier": next_tier is None,
    }
