import os
from typing import Optional

from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from starlette.middleware.sessions import SessionMiddleware

from app.auth import get_current_user, oauth, require_admin, require_login, upsert_user
from app.database import Base, engine, get_db
from app.models import Category, Match, Prediction, PredictionResult, PredictionType, User

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Hamster Fijas")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SECRET_KEY", "dev-secret-change-in-production"),
    session_cookie="hf_session",
    same_site="lax",
    https_only=os.environ.get("HTTPS_ONLY", "false").lower() == "true",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        from app.services import seed_database
        seed_database(db)
    finally:
        db.close()


def prediction_label(p: Prediction) -> str:
    if p.type == PredictionType.DOUBLE_CHANCE:
        labels = {"1X": "Local o Empate", "X2": "Empate o Visitante", "12": "Local o Visitante"}
        return f"Doble oportunidad: {labels.get(p.double_chance or '', p.double_chance)}"
    direction = "Más de" if p.over_under_pick == "over" else "Menos de"
    return f"{direction} {p.over_under_line} goles"


templates.env.globals["prediction_label"] = prediction_label
templates.env.globals["PredictionResult"] = PredictionResult
templates.env.globals["PredictionType"] = PredictionType


# ── Auth ────────────────────────────────────────────────────────────────────

@app.get("/auth/login")
async def auth_login(request: Request):
    redirect_uri = request.url_for("auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    info = token.get("userinfo") or await oauth.google.userinfo(token=token)
    user = upsert_user(
        db,
        google_id=info["sub"],
        email=info["email"],
        name=info.get("name", info["email"]),
        picture=info.get("picture", ""),
    )
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@app.get("/auth/logout")
def auth_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# ── Pages ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    categories = db.query(Category).order_by(Category.name).all()
    selected = category_id or (categories[0].id if categories else None)

    matches_query = (
        db.query(Match)
        .options(joinedload(Match.predictions).joinedload(Prediction.user), joinedload(Match.category))
        .order_by(Match.match_date)
    )
    if selected:
        matches_query = matches_query.filter(Match.category_id == selected)

    matches = matches_query.all()

    from app.services import get_stats
    stats = get_stats(db, selected)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "current_user": current_user,
            "categories": categories,
            "selected_category_id": selected,
            "matches": matches,
            "stats": stats,
        },
    )


@app.get("/proximamente", response_class=HTMLResponse)
def proximamente(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    return templates.TemplateResponse("proximamente.html", {
        "request": request,
        "current_user": current_user,
    })


# ── Admin: Categories ────────────────────────────────────────────────────────

@app.post("/categories")
def create_category(
    name: str = Form(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    name = name.strip()
    if not name:
        raise HTTPException(400, "Nombre requerido")
    if db.query(Category).filter(Category.name == name).first():
        raise HTTPException(400, "La categoría ya existe")
    db.add(Category(name=name))
    db.commit()
    return RedirectResponse("/", status_code=303)


# ── Admin: Matches ───────────────────────────────────────────────────────────

@app.post("/matches")
def create_match(
    category_id: int = Form(...),
    home_team: str = Form(...),
    away_team: str = Form(...),
    match_date: str = Form(...),
    group_name: str = Form(""),
    venue: str = Form(""),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    parsed_date = match_date.strip()
    if len(parsed_date) == 16:
        parsed_date += ":00"

    match = Match(
        category_id=category_id,
        home_team=home_team.strip(),
        away_team=away_team.strip(),
        match_date=datetime.fromisoformat(parsed_date),
        group_name=group_name.strip() or None,
        venue=venue.strip() or None,
    )
    db.add(match)
    db.commit()
    return RedirectResponse(f"/?category_id={category_id}", status_code=303)


@app.post("/matches/{match_id}/score")
def update_score(
    match_id: int,
    home_score: int = Form(...),
    away_score: int = Form(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    match = db.query(Match).options(joinedload(Match.predictions)).get(match_id)
    if not match:
        raise HTTPException(404)
    match.home_score = home_score
    match.away_score = away_score
    db.commit()
    from app.services import reevaluate_match_predictions
    reevaluate_match_predictions(db, match)
    return RedirectResponse(f"/?category_id={match.category_id}", status_code=303)


@app.post("/matches/{match_id}/delete")
def delete_match(
    match_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(404)
    category_id = match.category_id
    db.delete(match)
    db.commit()
    return RedirectResponse(f"/?category_id={category_id}", status_code=303)


# ── Predictions (any logged-in user) ────────────────────────────────────────

@app.post("/predictions")
def create_prediction(
    match_id: int = Form(...),
    type: str = Form(...),
    double_chance: str = Form(""),
    over_under_line: float = Form(2.5),
    over_under_pick: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(404)

    prediction = Prediction(
        match_id=match_id,
        user_id=current_user.id,
        type=PredictionType(type),
        double_chance=double_chance or None,
        over_under_line=over_under_line if type == "over_under" else None,
        over_under_pick=over_under_pick or None,
        notes=notes.strip() or None,
    )

    if match.is_finished:
        from app.services import evaluate_prediction
        prediction.result = evaluate_prediction(prediction, match)

    db.add(prediction)
    db.commit()
    return RedirectResponse(f"/?category_id={match.category_id}", status_code=303)


@app.post("/predictions/{prediction_id}/result")
def set_prediction_result(
    prediction_id: int,
    result: str = Form(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    prediction = db.query(Prediction).options(joinedload(Prediction.match)).get(prediction_id)
    if not prediction:
        raise HTTPException(404)
    prediction.result = PredictionResult(result)
    db.commit()
    return RedirectResponse(f"/?category_id={prediction.match.category_id}", status_code=303)


@app.post("/predictions/{prediction_id}/delete")
def delete_prediction(
    prediction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    prediction = db.query(Prediction).options(joinedload(Prediction.match)).get(prediction_id)
    if not prediction:
        raise HTTPException(404)
    if not current_user.is_admin and prediction.user_id != current_user.id:
        raise HTTPException(403, "No puedes eliminar predicciones ajenas")
    category_id = prediction.match.category_id
    db.delete(prediction)
    db.commit()
    return RedirectResponse(f"/?category_id={category_id}", status_code=303)
