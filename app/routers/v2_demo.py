"""Contexto y helpers para la demo UI v2."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Category, Match, Prediction, PredictionResult, PredictionType, User
from app.points import leaderboard, user_hamster_points
from app.referrals import referral_stats
from app.services import get_match_outcome_stats_batch, get_mundial_category
from app.timezone import peru_now

_WEEKDAYS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")


def _friendly_match_time(dt) -> str:
    today = peru_now().date()
    day = dt.date()
    clock = dt.strftime("%H:%M")
    if day == today:
        return f"Hoy · {clock}"
    if day == today + timedelta(days=1):
        return f"Mañ · {clock}"
    return f"{_WEEKDAYS[day.weekday()]} · {clock}"


def _fmt_hp(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _user_accuracy(db: Session, user_id: int, category_id: Optional[int]) -> Optional[int]:
    query = (
        db.query(Prediction)
        .filter(
            Prediction.user_id == user_id,
            Prediction.type == PredictionType.SCORE,
        )
    )
    if category_id:
        query = query.join(Match).filter(Match.category_id == category_id)
    preds = query.all()
    hits = sum(1 for p in preds if p.result == PredictionResult.HIT)
    misses = sum(1 for p in preds if p.result == PredictionResult.MISS)
    resolved = hits + misses
    if not resolved:
        return None
    return round(hits * 100 / resolved)


def _user_predictions_by_match(
    db: Session, user_id: int, match_ids: list[int]
) -> dict[int, Prediction]:
    if not match_ids:
        return {}
    rows = (
        db.query(Prediction)
        .filter(
            Prediction.user_id == user_id,
            Prediction.match_id.in_(match_ids),
            Prediction.type == PredictionType.SCORE,
        )
        .all()
    )
    return {p.match_id: p for p in rows}


def _score_stats(db: Session, match_id: int, limit: int = 3) -> list[dict]:
    rows = (
        db.query(Prediction.predicted_home_score, Prediction.predicted_away_score)
        .filter(
            Prediction.match_id == match_id,
            Prediction.type == PredictionType.SCORE,
            Prediction.predicted_home_score.isnot(None),
            Prediction.predicted_away_score.isnot(None),
        )
        .all()
    )
    if not rows:
        return []
    counts = Counter(f"{h}-{a}" for h, a in rows)
    total = sum(counts.values())
    return [
        {"label": label, "pct": round(count * 100 / total)}
        for label, count in counts.most_common(limit)
    ]


def _community_outcomes(stats: dict) -> list[dict]:
    if not stats.get("total"):
        return []
    return [
        {"label": "Local", "pct": stats["home_pct"]},
        {"label": "Empate", "pct": stats["draw_pct"]},
        {"label": "Visitante", "pct": stats["away_pct"]},
    ]


def _build_matches(
    db: Session,
    category_id: int,
    user_id: Optional[int],
    *,
    limit: int = 8,
) -> list[dict]:
    now = peru_now()
    matches = (
        db.query(Match)
        .filter(
            Match.category_id == category_id,
            Match.home_score.is_(None),
            Match.match_date >= now - timedelta(hours=6),
        )
        .order_by(Match.match_date)
        .limit(limit)
        .all()
    )
    if not matches:
        matches = (
            db.query(Match)
            .filter(Match.category_id == category_id)
            .order_by(Match.match_date.desc())
            .limit(limit)
            .all()
        )

    match_ids = [m.id for m in matches]
    user_preds = _user_predictions_by_match(db, user_id, match_ids) if user_id else {}

    rows = []
    for m in matches:
        pred = user_preds.get(m.id)
        if pred and pred.predicted_home_score is not None and pred.predicted_away_score is not None:
            prediction = f"{pred.predicted_home_score}-{pred.predicted_away_score}"
        else:
            prediction = None
        group = f"Grupo {m.group_name}" if m.group_name else "Mundial"
        rows.append(
            {
                "id": m.id,
                "group": group,
                "time": _friendly_match_time(m.match_date),
                "home": m.home_team,
                "away": m.away_team,
                "prediction": prediction,
                "open": m.predictions_open,
            }
        )
    return rows


def _build_leaderboard(
    db: Session,
    category_id: int,
    current_user_id: Optional[int],
    *,
    limit: int = 5,
) -> list[dict]:
    board = leaderboard(db, category_id, limit=50)
    rows = []
    for idx, row in enumerate(board[:limit], start=1):
        user = row["user"]
        rows.append(
            {
                "rank": idx,
                "name": user.name.split()[0],
                "hp": _fmt_hp(row["competitive"]),
                "hp_raw": row["competitive"],
                "is_me": current_user_id == user.id,
                "user_id": user.id,
                "has_avatar": bool(user.picture),
            }
        )
    return rows


def _user_rank(db: Session, category_id: int, user_id: int) -> Optional[int]:
    board = leaderboard(db, category_id, limit=500)
    for idx, row in enumerate(board, start=1):
        if row["user"].id == user_id:
            return idx
    return None


def _build_friends(
    db: Session, user_id: int, category_id: Optional[int]
) -> list[dict]:
    stats = referral_stats(db, user_id, category_id)
    rows = []
    for u in stats["referred_users"][:5]:
        pts = user_hamster_points(db, u.id, category_id)
        rows.append(
            {
                "name": u.name.split()[0],
                "league": "Referido verificado",
                "hp": _fmt_hp(pts["competitive"]),
                "user_id": u.id,
                "has_avatar": bool(u.picture),
            }
        )
    return rows


def _build_achievements(
    my_points: Optional[dict],
    rank: Optional[int],
    friends_count: int,
) -> list[dict]:
    if not my_points:
        return []
    achievements = []
    if my_points.get("score_hits", 0) > 0:
        achievements.append(
            {"icon": "🎯", "label": f"{my_points['score_hits']} marcador(es) exacto(s)"}
        )
    if my_points.get("outcome_hits", 0) > 0:
        achievements.append(
            {"icon": "⚽", "label": f"{my_points['outcome_hits']} acierto(s) 1X2"}
        )
    if rank and rank <= 10:
        achievements.append({"icon": "🏆", "label": f"Top {rank} del ranking"})
    if friends_count > 0:
        achievements.append({"icon": "👥", "label": f"{friends_count} referido(s) verificado(s)"})
    if my_points.get("champion_hits", 0) > 0:
        achievements.append({"icon": "👑", "label": "Campeón acertado"})
    return achievements[:4]


def build_v2_dashboard_context(
    db: Session,
    current_user: Optional[User],
    *,
    category_id: Optional[int] = None,
    featured_match_id: Optional[int] = None,
) -> dict:
    category = None
    if category_id:
        category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        category = get_mundial_category(db)
    resolved_category_id = category.id if category else None

    my_points = (
        user_hamster_points(db, current_user.id, resolved_category_id) if current_user else None
    )
    rank = (
        _user_rank(db, resolved_category_id, current_user.id)
        if current_user and resolved_category_id
        else None
    )
    accuracy = (
        _user_accuracy(db, current_user.id, resolved_category_id) if current_user else None
    )

    matches = _build_matches(
        db,
        resolved_category_id,
        current_user.id if current_user else None,
    ) if resolved_category_id else []

    if featured_match_id:
        featured_id = featured_match_id
        featured_match = db.query(Match).filter(Match.id == featured_match_id).first()
        community_match_label = (
            f"{featured_match.home_team} vs {featured_match.away_team}"
            if featured_match
            else None
        )
    else:
        featured_id = matches[0]["id"] if matches else None
        community_match_label = (
            f"{matches[0]['home']} vs {matches[0]['away']}" if matches else None
        )

    outcome_stats = (
        get_match_outcome_stats_batch(db, [featured_id]).get(featured_id, {})
        if featured_id
        else {}
    )
    community_outcomes = _community_outcomes(outcome_stats)
    community_scores = _score_stats(db, featured_id) if featured_id else []

    friends = (
        _build_friends(db, current_user.id, resolved_category_id) if current_user else []
    )

    competitive = my_points["competitive"] if my_points else 0
    total = my_points["total"] if my_points else 0
    score_hits = my_points.get("score_hits", 0) if my_points else 0

    if current_user:
        display_name = current_user.name.split()[0]
        level = max(1, min(99, 1 + competitive // 250))
    else:
        display_name = "Invitado"
        level = 1

    return {
        "category": category,
        "user_name": display_name,
        "level": level,
        "streak": score_hits,
        "rank": rank,
        "points": _fmt_hp(competitive),
        "points_total": _fmt_hp(total),
        "accuracy": accuracy if accuracy is not None else 0,
        "has_accuracy": accuracy is not None,
        "matches": matches,
        "community_outcomes": community_outcomes,
        "community_scores": community_scores,
        "community_match_label": community_match_label,
        "leaderboard": _build_leaderboard(
            db, resolved_category_id, current_user.id if current_user else None
        ) if resolved_category_id else [],
        "friends": friends,
        "achievements": _build_achievements(my_points, rank, len(friends)),
        "selected_category_id": resolved_category_id,
    }
