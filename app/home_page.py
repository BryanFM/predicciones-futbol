"""Contexto compartido de la página de inicio."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models import Category, Match, Prediction, User
from app.timezone import pet_timestamp_ms


def build_home_page_context(
    db: Session,
    current_user: Optional[User],
    *,
    category_id: Optional[int] = None,
    match_date: Optional[str] = None,
    group: Optional[str] = None,
) -> dict:
    from app.services import (
        champion_predictions_open,
        filter_matches_by_date,
        filter_matches_by_group,
        get_available_groups,
        get_available_match_dates,
        get_champion_deadline,
        get_champion_prediction_stats,
        get_group_summaries,
        get_match_outcome_stats_batch,
        get_stats,
        get_tournament_starts_at,
        get_tournament_teams,
        get_user_champion_prediction,
    )

    categories_query = db.query(Category).order_by(Category.name)
    if not (current_user and current_user.is_admin):
        categories_query = categories_query.filter(Category.is_active.is_(True))
    categories = categories_query.all()
    selected = category_id or (categories[0].id if categories else None)
    selected_category = next((c for c in categories if c.id == selected), None)

    matches_query = (
        db.query(Match)
        .options(joinedload(Match.predictions).joinedload(Prediction.user), joinedload(Match.category))
        .order_by(Match.match_date)
    )
    if selected:
        matches_query = matches_query.filter(Match.category_id == selected)

    matches_query, selected_date = (
        filter_matches_by_date(matches_query, match_date) if match_date else (matches_query, None)
    )
    matches_query, selected_group = filter_matches_by_group(matches_query, group)
    matches = matches_query.all()
    available_dates = get_available_match_dates(db, selected)
    available_groups = get_available_groups(db, selected)
    group_summaries = (
        get_group_summaries(db, selected, current_user.id if current_user else None) if selected else []
    )
    stats = get_stats(db, selected)

    tournament_teams: list[str] = []
    my_champion = None
    champion_open = False
    champion_stats = {"total": 0, "teams": [], "by_team": {}}
    match_outcome_stats: dict = {}
    countdown_ms = None
    countdown_label = ""

    champion_deadline = None
    if selected_category:
        tournament_teams = get_tournament_teams(db, selected)
        champion_open = champion_predictions_open(db, selected_category)
        champion_deadline = get_champion_deadline(db, selected_category)
        champion_stats = get_champion_prediction_stats(db, selected_category.id)
        starts_at = get_tournament_starts_at(db, selected_category)
        if starts_at:
            countdown_ms = pet_timestamp_ms(starts_at)
            countdown_label = selected_category.name
        if current_user:
            my_champion = get_user_champion_prediction(db, current_user.id, selected_category.id)

    if matches:
        match_outcome_stats = get_match_outcome_stats_batch(db, [m.id for m in matches])

    user_wagers_by_match: dict[int, object] = {}
    wager_ctx = None
    if current_user and current_user.phone_verified and selected:
        from app.models import PointWager
        from app.wagers import MAX_STAKE, MIN_STAKE, WAGER_PICKS, wager_balance

        match_ids = [m.id for m in matches]
        if match_ids:
            for w in (
                db.query(PointWager)
                .filter(PointWager.user_id == current_user.id, PointWager.match_id.in_(match_ids))
                .order_by(PointWager.created_at.desc())
                .all()
            ):
                user_wagers_by_match.setdefault(w.match_id, w)
        wager_balance_info = wager_balance(db, current_user.id, selected)
        wager_ctx = {
            "picks": WAGER_PICKS,
            "min_stake": MIN_STAKE,
            "max_stake": MAX_STAKE,
            "balance": wager_balance_info,
        }

    from app.routers.v2_demo import build_v2_dashboard_context

    featured_match_id = None
    for m in matches:
        if not m.is_finished:
            featured_match_id = m.id
            break
    if not featured_match_id and matches:
        featured_match_id = matches[0].id

    home_dashboard = build_v2_dashboard_context(
        db,
        current_user,
        category_id=selected,
        featured_match_id=featured_match_id,
    )

    return {
        "categories": categories,
        "selected_category": selected_category,
        "selected_category_id": selected,
        "selected_match_date": selected_date or "",
        "selected_group": selected_group or "",
        "available_dates": available_dates,
        "available_groups": available_groups,
        "group_summaries": group_summaries,
        "matches": matches,
        "stats": stats,
        "tournament_teams": tournament_teams,
        "my_champion": my_champion,
        "champion_open": champion_open,
        "champion_deadline": champion_deadline,
        "champion_stats": champion_stats,
        "match_outcome_stats": match_outcome_stats,
        "countdown_ms": countdown_ms,
        "countdown_label": countdown_label,
        "user_wagers_by_match": user_wagers_by_match,
        "wager_ctx": wager_ctx,
        "home_dashboard": home_dashboard,
    }
