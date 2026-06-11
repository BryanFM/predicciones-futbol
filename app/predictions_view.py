from app.models import PredictionResult, PredictionType
from app.timezone import peru_now, pet_timestamp_ms

HAMSTER_GIF_SILBATO = "/static/hamster_silbato.gif"
HAMSTER_GIF_HOY = "/static/hamster_hoy.gif"
HAMSTER_GIF_FIN = "/static/hamster_fin.gif"
HAMSTER_GIF_WIN = "/static/hamster_win.gif"
HAMSTER_GIF_LOSE = "/static/hamster_lose.gif"

# Ocultar GIFs en filas hasta tener assets finales
SHOW_MATCH_HAMSTER_GIFS = False


def match_user_score(match, user):
    """Retorna la predicción de marcador del usuario para un partido."""
    if not user:
        return None
    for p in match.predictions:
        if (
            p.user_id is not None
            and p.user_id == user.id
            and p.type == PredictionType.SCORE
        ):
            return p
    return None


def match_user_outcome(match, user):
    """Predicción 1X2 del usuario para un partido."""
    if not user:
        return None
    for p in match.predictions:
        if (
            p.user_id is not None
            and p.user_id == user.id
            and p.type == PredictionType.OUTCOME
        ):
            return p
    return None


def outcome_pick_label(pick: str) -> str:
    labels = {"1": "Gana local", "X": "Empate", "2": "Gana visitante"}
    return labels.get(pick or "", pick or "—")


def user_has_predictions(match, user) -> bool:
    return match_user_score(match, user) is not None or match_user_outcome(match, user) is not None


def score_label(p) -> str:
    if p.predicted_home_score is None or p.predicted_away_score is None:
        return "—"
    return f"{p.predicted_home_score} - {p.predicted_away_score}"


def predictions_cutoff_ms(match) -> int:
    """Epoch ms (PET) en que cierran predicciones: 5 min antes del inicio."""
    from datetime import timedelta

    from app.models import PREDICTIONS_CLOSE_MINUTES

    cutoff = match.match_date - timedelta(minutes=PREDICTIONS_CLOSE_MINUTES)
    return pet_timestamp_ms(cutoff)


def match_hamster_gif(match, user) -> str:
    """GIF del hamster según estado del partido y predicción del usuario."""
    score_pred = match_user_score(match, user)

    if match.is_finished:
        if score_pred and score_pred.result == PredictionResult.HIT:
            return HAMSTER_GIF_WIN
        if score_pred and score_pred.result == PredictionResult.MISS:
            return HAMSTER_GIF_LOSE
        return HAMSTER_GIF_FIN

    if match.match_date.date() == peru_now().date():
        return HAMSTER_GIF_HOY

    return HAMSTER_GIF_SILBATO
