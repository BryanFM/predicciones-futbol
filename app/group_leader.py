"""Bonificación por líder de grupo en fase de grupos."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import Category, Match, PointBonus, PointBonusType, Prediction, PredictionResult, PredictionType
from app.points_rules import RULE_GROUP_LEADER, get_hp


def _group_is_complete(db: Session, category_id: int, group_name: str) -> bool:
    matches = (
        db.query(Match)
        .filter(
            Match.category_id == category_id,
            Match.group_name == group_name,
        )
        .all()
    )
    if not matches:
        return False
    return all(m.is_finished for m in matches)


def _leader_for_group(db: Session, category_id: int, group_name: str) -> list[tuple[int, int]]:
    """Devuelve [(user_id, hits)] empatados en el máximo si hay empate."""
    match_ids = [
        m.id
        for m in db.query(Match)
        .filter(Match.category_id == category_id, Match.group_name == group_name)
        .all()
    ]
    if not match_ids:
        return []

    hits_by_user: dict[int, int] = defaultdict(int)
    preds = (
        db.query(Prediction)
        .filter(
            Prediction.match_id.in_(match_ids),
            Prediction.type == PredictionType.SCORE,
            Prediction.result == PredictionResult.HIT,
            Prediction.user_id.isnot(None),
        )
        .all()
    )
    for p in preds:
        if p.user_id:
            hits_by_user[p.user_id] += 1

    if not hits_by_user:
        return []

    max_hits = max(hits_by_user.values())
    return [(uid, max_hits) for uid, n in hits_by_user.items() if n == max_hits]


def evaluate_group_leaders(db: Session, category_id: int) -> int:
    """Asigna bonus de líder de grupo. Devuelve cantidad de bonos nuevos."""
    category = db.get(Category, category_id)
    if not category:
        return 0

    hp = get_hp(db, RULE_GROUP_LEADER, category_id)
    if hp <= 0:
        return 0

    groups = (
        db.query(Match.group_name)
        .filter(
            Match.category_id == category_id,
            Match.group_name.isnot(None),
            Match.group_name != "",
        )
        .distinct()
        .all()
    )
    created = 0
    for (group_name,) in groups:
        if not group_name or not _group_is_complete(db, category_id, group_name):
            continue
        ref_key = f"group:{group_name.upper()}"
        leaders = _leader_for_group(db, category_id, group_name)
        for user_id, hits in leaders:
            exists = (
                db.query(PointBonus)
                .filter(
                    PointBonus.user_id == user_id,
                    PointBonus.category_id == category_id,
                    PointBonus.bonus_type == PointBonusType.GROUP_LEADER,
                    PointBonus.reference_key == ref_key,
                )
                .first()
            )
            if exists:
                continue
            db.add(
                PointBonus(
                    user_id=user_id,
                    category_id=category_id,
                    bonus_type=PointBonusType.GROUP_LEADER,
                    hp=hp,
                    reference_key=ref_key,
                    notes=f"Líder grupo {group_name} ({hits} aciertos)",
                )
            )
            created += 1

    if created:
        db.commit()
    return created
