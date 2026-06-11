"""Contexto de la página de ranking."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Category, User
from app.timezone import pet_timestamp_ms


def build_ranking_page_context(
    db: Session,
    current_user: Optional[User],
    *,
    category_id: Optional[int] = None,
) -> dict:
    from app.points import leaderboard, user_hamster_points
    from app.points_rules import rules_dict
    from app.prize_tiers import get_current_tier
    from app.routers.v2_demo import build_v2_dashboard_context
    from app.services import (
        champion_predictions_open,
        get_champion_deadline,
        get_champion_prediction_stats,
        get_tournament_starts_at,
        get_tournament_teams,
        get_user_champion_prediction,
    )

    categories = db.query(Category).filter(Category.is_active.is_(True)).order_by(Category.name).all()
    selected = category_id or (categories[0].id if categories else None)
    selected_category = next((c for c in categories if c.id == selected), None)

    board = leaderboard(db, selected, limit=500)
    my_points = user_hamster_points(db, current_user.id, selected) if current_user else None
    hp_rules = rules_dict(db, selected)
    tier_ctx = get_current_tier(db)
    home_dashboard = build_v2_dashboard_context(db, current_user, category_id=selected)

    countdown_ms = None
    countdown_label = ""
    tournament_teams: list[str] = []
    my_champion = None
    champion_open = False
    champion_stats = {"total": 0, "teams": [], "by_team": {}}
    champion_deadline = None

    if selected_category:
        starts_at = get_tournament_starts_at(db, selected_category)
        if starts_at:
            countdown_ms = pet_timestamp_ms(starts_at)
            countdown_label = selected_category.name
        tournament_teams = get_tournament_teams(db, selected)
        champion_open = champion_predictions_open(db, selected_category)
        champion_deadline = get_champion_deadline(db, selected_category)
        champion_stats = get_champion_prediction_stats(db, selected_category.id)
        if current_user:
            my_champion = get_user_champion_prediction(db, current_user.id, selected_category.id)

    return {
        "categories": categories,
        "selected_category_id": selected,
        "selected_category": selected_category,
        "leaderboard": board,
        "my_points": my_points,
        "hp_rules": hp_rules,
        "countdown_ms": countdown_ms,
        "countdown_label": countdown_label,
        "home_dashboard": home_dashboard,
        "tournament_teams": tournament_teams,
        "my_champion": my_champion,
        "champion_open": champion_open,
        "champion_deadline": champion_deadline,
        "champion_stats": champion_stats,
        **tier_ctx,
    }
