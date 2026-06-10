from collections import Counter, defaultdict
from typing import List, Literal, Optional

from datetime import date, datetime, time

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Category, ChampionPrediction, Match, Prediction, PredictionResult, PredictionType
from app.timezone import peru_now


def get_available_match_dates(db: Session, category_id: Optional[int] = None) -> List[date]:
    query = db.query(Match.match_date).order_by(Match.match_date)
    if category_id:
        query = query.filter(Match.category_id == category_id)
    seen: set = set()
    dates: List[date] = []
    for (match_dt,) in query.all():
        day = match_dt.date()
        if day not in seen:
            seen.add(day)
            dates.append(day)
    return dates


def filter_matches_by_date(query, match_date: str):
    try:
        day = datetime.strptime(match_date, "%Y-%m-%d").date()
    except ValueError:
        return query, None
    day_start = datetime.combine(day, time.min)
    day_end = datetime.combine(day, time.max)
    return query.filter(Match.match_date >= day_start, Match.match_date <= day_end), match_date


def get_available_groups(db: Session, category_id: Optional[int] = None) -> List[str]:
    query = db.query(Match.group_name).filter(
        Match.group_name.isnot(None),
        Match.group_name != "",
    )
    if category_id:
        query = query.filter(Match.category_id == category_id)
    groups = sorted({g for (g,) in query.distinct().all() if g})
    return groups


def filter_matches_by_group(query, group_name: Optional[str]):
    if not group_name or not group_name.strip():
        return query, None
    group = group_name.strip().upper()
    return query.filter(Match.group_name == group), group


def is_mundial_2026(category: Category) -> bool:
    if category.season == "2026":
        return True
    name = (category.name or "").lower()
    return name == "mundial" or "mundial" in name


def get_mundial_category(db: Session) -> Optional[Category]:
    for cat in db.query(Category).order_by(Category.id).all():
        if is_mundial_2026(cat):
            return cat
    return None


def evaluate_double_chance(home: int, away: int, pick: str) -> bool:
    if pick == "1X":
        return home >= away
    if pick == "X2":
        return away >= home
    if pick == "12":
        return home != away
    return False


def evaluate_over_under(total: int, line: float, pick: str) -> bool:
    if pick == "over":
        return total > line
    if pick == "under":
        return total < line
    return False


def evaluate_score(home: int, away: int, pred_home: int, pred_away: int) -> bool:
    return home == pred_home and away == pred_away


def evaluate_prediction(prediction: Prediction, match: Match) -> PredictionResult:
    if not match.is_finished:
        return PredictionResult.PENDING

    home, away = match.home_score, match.away_score
    assert home is not None and away is not None

    if (
        prediction.type == PredictionType.SCORE
        and prediction.predicted_home_score is not None
        and prediction.predicted_away_score is not None
    ):
        ok = evaluate_score(
            home, away, prediction.predicted_home_score, prediction.predicted_away_score
        )
    elif prediction.type == PredictionType.DOUBLE_CHANCE and prediction.double_chance:
        ok = evaluate_double_chance(home, away, prediction.double_chance)
    elif (
        prediction.type == PredictionType.OVER_UNDER
        and prediction.over_under_line is not None
        and prediction.over_under_pick
    ):
        ok = evaluate_over_under(
            home + away, prediction.over_under_line, prediction.over_under_pick
        )
    else:
        return PredictionResult.PENDING

    return PredictionResult.HIT if ok else PredictionResult.MISS


def reevaluate_match_predictions(db: Session, match: Match) -> None:
    for prediction in match.predictions:
        prediction.result = evaluate_prediction(prediction, match)
    db.commit()


def get_stats(db: Session, category_id: Optional[int] = None) -> dict:
    query = db.query(Prediction).filter(Prediction.type == PredictionType.SCORE)
    if category_id:
        query = query.join(Match).filter(Match.category_id == category_id)

    predictions = query.all()
    hits = sum(1 for p in predictions if p.result == PredictionResult.HIT)
    misses = sum(1 for p in predictions if p.result == PredictionResult.MISS)
    pending = sum(1 for p in predictions if p.result == PredictionResult.PENDING)
    resolved = hits + misses

    return {
        "total": len(predictions),
        "hits": hits,
        "misses": misses,
        "pending": pending,
        "accuracy": round((hits / resolved) * 100, 1) if resolved else None,
    }


# Fase de grupos Mundial 2026 — horarios en PET (UTC-5).
# Formato: (local, visitante, fecha_hora ISO, grupo, estadio)
MUNDIAL_2026_GROUP_STAGE = [
    # Grupo A
    ("México", "Sudáfrica", "2026-06-11T14:00", "A", "Estadio Azteca"),
    ("Corea del Sur", "República Checa", "2026-06-11T21:00", "A", "Estadio Akron"),
    ("República Checa", "Sudáfrica", "2026-06-18T23:00", "A", "Mercedes-Benz Stadium"),
    ("México", "Corea del Sur", "2026-06-18T20:00", "A", "Estadio Akron"),
    ("República Checa", "México", "2026-06-24T20:00", "A", "Estadio Azteca"),
    ("Sudáfrica", "Corea del Sur", "2026-06-24T20:00", "A", "Estadio BBVA"),
    # Grupo B
    ("Canadá", "Bosnia y Herzegovina", "2026-06-12T14:00", "B", "BMO Field"),
    ("Catar", "Suiza", "2026-06-13T14:00", "B", "Levi's Stadium"),
    ("Suiza", "Bosnia y Herzegovina", "2026-06-18T14:00", "B", "SoFi Stadium"),
    ("Canadá", "Catar", "2026-06-18T17:00", "B", "BC Place"),
    ("Suiza", "Canadá", "2026-06-24T14:00", "B", "BC Place"),
    ("Bosnia y Herzegovina", "Catar", "2026-06-24T14:00", "B", "Lumen Field"),
    # Grupo C
    ("Brasil", "Marruecos", "2026-06-13T17:00", "C", "MetLife Stadium"),
    ("Haití", "Escocia", "2026-06-13T20:00", "C", "Gillette Stadium"),
    ("Escocia", "Marruecos", "2026-06-19T17:00", "C", "Gillette Stadium"),
    ("Brasil", "Haití", "2026-06-19T19:30", "C", "Lincoln Financial Field"),
    ("Marruecos", "Haití", "2026-06-24T17:00", "C", "Mercedes-Benz Stadium"),
    ("Escocia", "Haití", "2026-06-24T17:00", "C", "Hard Rock Stadium"),
    # Grupo D
    ("Estados Unidos", "Paraguay", "2026-06-12T20:00", "D", "SoFi Stadium"),
    ("Australia", "Turquía", "2026-06-13T23:00", "D", "BC Place"),
    ("Estados Unidos", "Australia", "2026-06-19T14:00", "D", "Lumen Field"),
    ("Turquía", "Paraguay", "2026-06-19T22:00", "D", "Levi's Stadium"),
    ("Paraguay", "Australia", "2026-06-25T21:00", "D", "Levi's Stadium"),
    ("Turquía", "Estados Unidos", "2026-06-25T21:00", "D", "SoFi Stadium"),
    # Grupo E
    ("Alemania", "Curazao", "2026-06-14T12:00", "E", "NRG Stadium"),
    ("Costa de Marfil", "Ecuador", "2026-06-14T18:00", "E", "Lincoln Financial Field"),
    ("Alemania", "Costa de Marfil", "2026-06-20T15:00", "E", "BMO Field"),
    ("Ecuador", "Curazao", "2026-06-20T19:00", "E", "Arrowhead Stadium"),
    ("Ecuador", "Alemania", "2026-06-25T15:00", "E", "MetLife Stadium"),
    ("Curazao", "Costa de Marfil", "2026-06-25T15:00", "E", "Lincoln Financial Field"),
    # Grupo F
    ("Países Bajos", "Japón", "2026-06-14T15:00", "F", "AT&T Stadium"),
    ("Suecia", "Túnez", "2026-06-14T21:00", "F", "Estadio BBVA"),
    ("Países Bajos", "Suecia", "2026-06-20T12:00", "F", "NRG Stadium"),
    ("Túnez", "Japón", "2026-06-20T23:00", "F", "Estadio BBVA"),
    ("Túnez", "Países Bajos", "2026-06-25T18:00", "F", "Arrowhead Stadium"),
    ("Japón", "Suecia", "2026-06-25T18:00", "F", "AT&T Stadium"),
    # Grupo G
    ("Bélgica", "Egipto", "2026-06-15T14:00", "G", "Lumen Field"),
    ("Irán", "Nueva Zelanda", "2026-06-15T20:00", "G", "SoFi Stadium"),
    ("Bélgica", "Irán", "2026-06-21T14:00", "G", "SoFi Stadium"),
    ("Nueva Zelanda", "Egipto", "2026-06-21T20:00", "G", "BC Place"),
    ("Egipto", "Irán", "2026-06-26T22:00", "G", "Lumen Field"),
    ("Nueva Zelanda", "Bélgica", "2026-06-26T22:00", "G", "BC Place"),
    # Grupo H
    ("España", "Cabo Verde", "2026-06-15T11:00", "H", "Mercedes-Benz Stadium"),
    ("Arabia Saudita", "Uruguay", "2026-06-15T17:00", "H", "Hard Rock Stadium"),
    ("España", "Arabia Saudita", "2026-06-21T11:00", "H", "Mercedes-Benz Stadium"),
    ("Uruguay", "Cabo Verde", "2026-06-21T17:00", "H", "Hard Rock Stadium"),
    ("Uruguay", "España", "2026-06-26T19:00", "H", "Estadio Akron"),
    ("Cabo Verde", "Arabia Saudita", "2026-06-26T19:00", "H", "NRG Stadium"),
    # Grupo I
    ("Francia", "Senegal", "2026-06-16T14:00", "I", "MetLife Stadium"),
    ("Irak", "Noruega", "2026-06-16T17:00", "I", "Gillette Stadium"),
    ("Francia", "Irak", "2026-06-22T16:00", "I", "Lincoln Financial Field"),
    ("Noruega", "Senegal", "2026-06-22T19:00", "I", "MetLife Stadium"),
    ("Noruega", "Francia", "2026-06-26T14:00", "I", "Gillette Stadium"),
    ("Senegal", "Irak", "2026-06-26T14:00", "I", "BMO Field"),
    # Grupo J
    ("Argentina", "Argelia", "2026-06-16T20:00", "J", "Arrowhead Stadium"),
    ("Austria", "Jordania", "2026-06-16T23:00", "J", "Levi's Stadium"),
    ("Argentina", "Austria", "2026-06-22T12:00", "J", "AT&T Stadium"),
    ("Jordania", "Argelia", "2026-06-22T22:00", "J", "Levi's Stadium"),
    ("Jordania", "Argentina", "2026-06-27T21:00", "J", "AT&T Stadium"),
    ("Argelia", "Austria", "2026-06-27T21:00", "J", "Arrowhead Stadium"),
    # Grupo K
    ("Portugal", "Rep. Dem. del Congo", "2026-06-17T12:00", "K", "NRG Stadium"),
    ("Uzbekistán", "Colombia", "2026-06-17T21:00", "K", "Estadio Azteca"),
    ("Portugal", "Uzbekistán", "2026-06-23T12:00", "K", "NRG Stadium"),
    ("Colombia", "Rep. Dem. del Congo", "2026-06-23T21:00", "K", "Estadio Akron"),
    ("Colombia", "Portugal", "2026-06-27T18:30", "K", "Hard Rock Stadium"),
    ("Rep. Dem. del Congo", "Uzbekistán", "2026-06-27T18:30", "K", "Mercedes-Benz Stadium"),
    # Grupo L
    ("Inglaterra", "Croacia", "2026-06-17T15:00", "L", "AT&T Stadium"),
    ("Ghana", "Panamá", "2026-06-17T18:00", "L", "BMO Field"),
    ("Inglaterra", "Ghana", "2026-06-23T15:00", "L", "Gillette Stadium"),
    ("Panamá", "Croacia", "2026-06-23T18:00", "L", "BMO Field"),
    ("Panamá", "Inglaterra", "2026-06-27T16:00", "L", "MetLife Stadium"),
    ("Croacia", "Ghana", "2026-06-27T16:00", "L", "Lincoln Financial Field"),
]

# Alias de equipos en BD antigua → nombre actual
_TEAM_ALIASES = {
    "Qatar": "Catar",
}


MUNDIAL_2026_KICKOFF = datetime.fromisoformat("2026-06-11T14:00")
# Fin fase de grupos Mundial 2026 — 27/06/2026 23:59:59 PET (medianoche del día 27)
MUNDIAL_2026_GROUP_STAGE_END = datetime(2026, 6, 27, 23, 59, 59)


def sync_champion_deadline(db: Session, category: Category) -> None:
    """Fecha límite campeón. Mundial: 27/06 medianoche PET; otros: último partido de grupos."""
    if is_mundial_2026(category):
        category.champion_closes_at = MUNDIAL_2026_GROUP_STAGE_END
        return

    last_group = (
        db.query(func.max(Match.match_date))
        .filter(
            Match.category_id == category.id,
            Match.group_name.isnot(None),
            Match.group_name != "",
        )
        .scalar()
    )
    if last_group:
        category.champion_closes_at = datetime.combine(last_group.date(), time(23, 59, 59))


def get_champion_deadline(db: Session, category: Category) -> Optional[datetime]:
    if category.champion_closes_at:
        return category.champion_closes_at
    if is_mundial_2026(category):
        return MUNDIAL_2026_GROUP_STAGE_END

    last_group = (
        db.query(func.max(Match.match_date))
        .filter(
            Match.category_id == category.id,
            Match.group_name.isnot(None),
            Match.group_name != "",
        )
        .scalar()
    )
    if last_group:
        return datetime.combine(last_group.date(), time(23, 59, 59))
    return None


def get_tournament_teams(db: Session, category_id: int) -> list[str]:
    matches = db.query(Match).filter(Match.category_id == category_id).all()
    teams: set[str] = set()
    for m in matches:
        teams.add(m.home_team)
        teams.add(m.away_team)
    return sorted(teams)


def get_tournament_starts_at(db: Session, category: Category):
    if category.starts_at:
        return category.starts_at
    first = (
        db.query(Match.match_date)
        .filter(Match.category_id == category.id)
        .order_by(Match.match_date)
        .first()
    )
    return first[0] if first else None


def champion_predictions_open(db: Session, category: Category) -> bool:
    if category.champion_decided:
        return False
    deadline = get_champion_deadline(db, category)
    if not deadline:
        return True
    return peru_now() <= deadline


def get_user_champion_prediction(db: Session, user_id: int, category_id: int):
    return (
        db.query(ChampionPrediction)
        .filter(
            ChampionPrediction.user_id == user_id,
            ChampionPrediction.category_id == category_id,
        )
        .first()
    )


Outcome = Literal["home", "draw", "away"]


def score_outcome(home: int, away: int) -> Outcome:
    if home > away:
        return "home"
    if home < away:
        return "away"
    return "draw"


def _empty_outcome_stats() -> dict:
    return {
        "total": 0,
        "home": 0,
        "draw": 0,
        "away": 0,
        "home_pct": 0,
        "draw_pct": 0,
        "away_pct": 0,
    }


def get_match_outcome_stats_batch(db: Session, match_ids: list[int]) -> dict[int, dict]:
    if not match_ids:
        return {}

    preds = (
        db.query(
            Prediction.match_id,
            Prediction.predicted_home_score,
            Prediction.predicted_away_score,
        )
        .filter(
            Prediction.match_id.in_(match_ids),
            Prediction.type == PredictionType.SCORE,
            Prediction.predicted_home_score.isnot(None),
            Prediction.predicted_away_score.isnot(None),
        )
        .all()
    )

    by_match: dict[int, Counter] = defaultdict(Counter)
    for match_id, home_score, away_score in preds:
        by_match[match_id][score_outcome(home_score, away_score)] += 1

    result: dict[int, dict] = {}
    for match_id in match_ids:
        counts = by_match.get(match_id)
        if not counts:
            result[match_id] = _empty_outcome_stats()
            continue
        total = sum(counts.values())
        result[match_id] = {
            "total": total,
            "home": counts["home"],
            "draw": counts["draw"],
            "away": counts["away"],
            "home_pct": round(counts["home"] * 100 / total),
            "draw_pct": round(counts["draw"] * 100 / total),
            "away_pct": round(counts["away"] * 100 / total),
        }
    return result


def get_champion_prediction_stats(db: Session, category_id: int) -> dict:
    rows = (
        db.query(ChampionPrediction.champion_team)
        .filter(ChampionPrediction.category_id == category_id)
        .all()
    )
    total = len(rows)
    if total == 0:
        return {"total": 0, "teams": [], "by_team": {}}

    counts = Counter(team.strip() for (team,) in rows if team and team.strip())
    teams = []
    by_team: dict[str, int] = {}
    for team, count in counts.most_common():
        pct = round(count * 100 / total)
        teams.append({"team": team, "count": count, "pct": pct})
        by_team[team] = pct

    return {"total": total, "teams": teams, "by_team": by_team}


def evaluate_champion_predictions(db: Session, category: Category) -> None:
    if not category.champion_team:
        return
    winner = category.champion_team.strip()
    predictions = (
        db.query(ChampionPrediction)
        .filter(ChampionPrediction.category_id == category.id)
        .all()
    )
    for cp in predictions:
        cp.result = (
            PredictionResult.HIT if cp.champion_team.strip() == winner else PredictionResult.MISS
        )
    db.commit()


def _normalize_team(name: str) -> str:
    return _TEAM_ALIASES.get(name, name)


def _match_key(home: str, away: str) -> tuple[str, str]:
    return (_normalize_team(home), _normalize_team(away))


def sync_mundial_schedule(db: Session) -> None:
    """Sincroniza calendario completo de fase de grupos (actualiza y agrega partidos)."""
    mundial = get_mundial_category(db)
    if not mundial:
        return

    for match in db.query(Match).filter(Match.category_id == mundial.id).all():
        if match.home_team in _TEAM_ALIASES:
            match.home_team = _TEAM_ALIASES[match.home_team]
        if match.away_team in _TEAM_ALIASES:
            match.away_team = _TEAM_ALIASES[match.away_team]

    schedule = {
        _match_key(home, away): (date_str, group, venue, home, away)
        for home, away, date_str, group, venue in MUNDIAL_2026_GROUP_STAGE
    }

    existing: dict[tuple[str, str], Match] = {}
    for match in db.query(Match).filter(Match.category_id == mundial.id).all():
        key = _match_key(match.home_team, match.away_team)
        existing[key] = match

    for key, (date_str, group, venue, home, away) in schedule.items():
        if key in existing:
            m = existing[key]
            m.home_team = home
            m.away_team = away
            m.match_date = datetime.fromisoformat(date_str)
            m.group_name = group
            m.venue = venue
        else:
            db.add(
                Match(
                    category_id=mundial.id,
                    home_team=home,
                    away_team=away,
                    match_date=datetime.fromisoformat(date_str),
                    group_name=group,
                    venue=venue,
                )
            )

    if not mundial.starts_at:
        mundial.starts_at = MUNDIAL_2026_KICKOFF

    sync_champion_deadline(db, mundial)
    db.commit()


def seed_database(db: Session) -> None:
    if db.query(Category).first():
        sync_mundial_schedule(db)
        return

    mundial = Category(
        name="Mundial",
        description="Copa Mundial FIFA 2026",
        season="2026",
        is_active=True,
        starts_at=MUNDIAL_2026_KICKOFF,
    )
    db.add(mundial)
    db.flush()

    for home, away, date_str, group, venue in MUNDIAL_2026_GROUP_STAGE:
        db.add(
            Match(
                category_id=mundial.id,
                home_team=home,
                away_team=away,
                match_date=datetime.fromisoformat(date_str),
                group_name=group,
                venue=venue,
            )
        )

    sync_champion_deadline(db, mundial)
    db.commit()
