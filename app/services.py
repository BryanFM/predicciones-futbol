from typing import Optional

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Category, Match, Prediction, PredictionResult, PredictionType


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


def evaluate_prediction(prediction: Prediction, match: Match) -> PredictionResult:
    if not match.is_finished:
        return PredictionResult.PENDING

    home, away = match.home_score, match.away_score
    assert home is not None and away is not None

    if prediction.type == PredictionType.DOUBLE_CHANCE and prediction.double_chance:
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
    if not match.is_finished:
        return
    for prediction in match.predictions:
        prediction.result = evaluate_prediction(prediction, match)
    db.commit()


def get_stats(db: Session, category_id: Optional[int] = None) -> dict:
    query = db.query(Prediction)
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


MUNDIAL_2026_MATCHDAY_1 = [
    ("México", "Sudáfrica", "2026-06-11T19:00", "A", "Estadio Azteca, Ciudad de México"),
    ("Corea del Sur", "República Checa", "2026-06-12T02:00", "A", "Estadio Akron, Guadalajara"),
    ("Canadá", "Bosnia y Herzegovina", "2026-06-12T19:00", "B", "BMO Field, Toronto"),
    ("Estados Unidos", "Paraguay", "2026-06-13T01:00", "D", "SoFi Stadium, Los Ángeles"),
    ("Qatar", "Suiza", "2026-06-13T19:00", "B", "Levi's Stadium, San Francisco"),
    ("Brasil", "Marruecos", "2026-06-13T22:00", "C", "MetLife Stadium, Nueva York"),
    ("Haití", "Escocia", "2026-06-14T01:00", "C", "Gillette Stadium, Boston"),
    ("Australia", "Turquía", "2026-06-14T04:00", "D", "BC Place, Vancouver"),
    ("Alemania", "Curazao", "2026-06-14T17:00", "E", "NRG Stadium, Houston"),
    ("Países Bajos", "Japón", "2026-06-14T20:00", "F", "AT&T Stadium, Dallas"),
    ("Costa de Marfil", "Ecuador", "2026-06-14T23:00", "E", "Lincoln Financial Field, Filadelfia"),
    ("Suecia", "Túnez", "2026-06-15T02:00", "F", "Estadio BBVA, Monterrey"),
    ("España", "Cabo Verde", "2026-06-15T16:00", "H", "Mercedes-Benz Stadium, Atlanta"),
    ("Bélgica", "Egipto", "2026-06-15T19:00", "G", "Lumen Field, Seattle"),
    ("Arabia Saudita", "Uruguay", "2026-06-15T22:00", "H", "Hard Rock Stadium, Miami"),
    ("Irán", "Nueva Zelanda", "2026-06-16T01:00", "G", "SoFi Stadium, Los Ángeles"),
    ("Francia", "Senegal", "2026-06-16T19:00", "I", "MetLife Stadium, Nueva York"),
    ("Irak", "Noruega", "2026-06-16T22:00", "I", "Gillette Stadium, Boston"),
    ("Argentina", "Argelia", "2026-06-17T01:00", "J", "Arrowhead Stadium, Kansas City"),
    ("Austria", "Jordania", "2026-06-17T04:00", "J", "Levi's Stadium, San Francisco"),
    ("Portugal", "Rep. Dem. del Congo", "2026-06-17T17:00", "K", "NRG Stadium, Houston"),
    ("Uzbekistán", "Colombia", "2026-06-18T02:00", "K", "Estadio Azteca, Ciudad de México"),
    ("Ghana", "Panamá", "2026-06-17T20:00", "L", "BMO Field, Toronto"),
    ("Inglaterra", "Croacia", "2026-06-17T23:00", "L", "AT&T Stadium, Dallas"),
]


def seed_database(db: Session) -> None:
    if db.query(Category).first():
        return

    mundial = Category(name="Mundial")
    db.add(mundial)
    db.flush()

    for home, away, date_str, group, venue in MUNDIAL_2026_MATCHDAY_1:
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

    db.commit()
