"""Reglas de HP configurables por admin."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import PointsRule
from app.timezone import peru_now

RULE_SCORE_HIT = "score_hit"
RULE_OUTCOME_HIT = "outcome_hit"
RULE_CHAMPION_HIT = "champion_hit"
RULE_REFERRAL_REFERRER = "referral_referrer"
RULE_REFERRAL_REFERRED = "referral_referred"
RULE_GROUP_LEADER = "group_leader"

DEFAULT_RULES: list[dict] = [
    {
        "rule_key": RULE_SCORE_HIT,
        "label": "Marcador exacto",
        "description": "HP por acertar local y visitante en un partido.",
        "hp_value": 5,
    },
    {
        "rule_key": RULE_OUTCOME_HIT,
        "label": "Resultado acertado (1X2)",
        "description": "HP por acertar si gana local, empatan o gana visitante.",
        "hp_value": 2,
    },
    {
        "rule_key": RULE_CHAMPION_HIT,
        "label": "Campeón acertado",
        "description": "HP por predecir correctamente al campeón del torneo.",
        "hp_value": 50,
    },
    {
        "rule_key": RULE_REFERRAL_REFERRER,
        "label": "Referido verificado (quien invita)",
        "description": "HP cuando tu invitado verifica su celular.",
        "hp_value": 10,
    },
    {
        "rule_key": RULE_REFERRAL_REFERRED,
        "label": "Bonus por invitación (invitado)",
        "description": "HP extra al verificar celular si entraste con enlace de referido.",
        "hp_value": 5,
    },
    {
        "rule_key": RULE_GROUP_LEADER,
        "label": "Líder de grupo",
        "description": "HP al liderar un grupo (más aciertos de marcador en fase de grupos).",
        "hp_value": 15,
    },
]

RULE_KEYS = [r["rule_key"] for r in DEFAULT_RULES]


def seed_default_rules(db: Session) -> None:
    for spec in DEFAULT_RULES:
        exists = (
            db.query(PointsRule)
            .filter(PointsRule.category_id.is_(None), PointsRule.rule_key == spec["rule_key"])
            .first()
        )
        if exists:
            continue
        db.add(
            PointsRule(
                category_id=None,
                rule_key=spec["rule_key"],
                label=spec["label"],
                description=spec["description"],
                hp_value=spec["hp_value"],
            )
        )
    db.commit()


def get_hp(db: Session, rule_key: str, category_id: Optional[int] = None) -> int:
    if category_id:
        row = (
            db.query(PointsRule)
            .filter(PointsRule.category_id == category_id, PointsRule.rule_key == rule_key)
            .first()
        )
        if row:
            return row.hp_value
    row = (
        db.query(PointsRule)
        .filter(PointsRule.category_id.is_(None), PointsRule.rule_key == rule_key)
        .first()
    )
    if row:
        return row.hp_value
    for spec in DEFAULT_RULES:
        if spec["rule_key"] == rule_key:
            return spec["hp_value"]
    return 0


def get_rules_for_admin(db: Session, category_id: Optional[int] = None) -> list[dict]:
    seed_default_rules(db)
    rows: list[dict] = []
    for spec in DEFAULT_RULES:
        key = spec["rule_key"]
        override = None
        if category_id:
            override = (
                db.query(PointsRule)
                .filter(PointsRule.category_id == category_id, PointsRule.rule_key == key)
                .first()
            )
        global_row = (
            db.query(PointsRule)
            .filter(PointsRule.category_id.is_(None), PointsRule.rule_key == key)
            .first()
        )
        effective = override or global_row
        rows.append(
            {
                "rule_key": key,
                "label": effective.label if effective else spec["label"],
                "description": effective.description if effective else spec["description"],
                "hp_value": effective.hp_value if effective else spec["hp_value"],
                "has_override": override is not None,
                "global_hp": global_row.hp_value if global_row else spec["hp_value"],
            }
        )
    return rows


def save_rule_hp(
    db: Session,
    rule_key: str,
    hp_value: int,
    category_id: Optional[int] = None,
) -> None:
    if rule_key not in RULE_KEYS:
        raise ValueError("Regla no válida")
    if hp_value < 0 or hp_value > 9999:
        raise ValueError("HP fuera de rango")

    seed_default_rules(db)
    spec = next(s for s in DEFAULT_RULES if s["rule_key"] == rule_key)
    query = db.query(PointsRule).filter(PointsRule.rule_key == rule_key)
    if category_id:
        query = query.filter(PointsRule.category_id == category_id)
    else:
        query = query.filter(PointsRule.category_id.is_(None))
    row = query.first()
    if row:
        row.hp_value = hp_value
        row.updated_at = peru_now()
    else:
        db.add(
            PointsRule(
                category_id=category_id,
                rule_key=rule_key,
                label=spec["label"],
                description=spec["description"],
                hp_value=hp_value,
            )
        )
    db.commit()


def rules_dict(db: Session, category_id: Optional[int] = None) -> dict[str, int]:
    return {key: get_hp(db, key, category_id) for key in RULE_KEYS}
