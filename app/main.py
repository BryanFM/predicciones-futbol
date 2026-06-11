import app.env  # noqa: F401
import os
from typing import Optional

from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.avatars import avatar_url as avatar_url_for_user, fetch_avatar
from app.auth import get_current_user, oauth, require_admin, require_login, require_verified, upsert_user
from app.database import Base, engine, get_db
from app.hf_response import ajax_or_redirect, wants_ajax
from app.models import Category, ChampionPrediction, Match, Prediction, PredictionResult, PredictionType, User
from app.rendering import render, render_error_page, static_url, templates

BASE_DIR = Path(__file__).resolve().parent

from app.routers import account, admin, referrals, verify, wagers, yape

app = FastAPI(title="Hamster Fijas")
app.include_router(verify.router)
app.include_router(account.router)
app.include_router(admin.router)
app.include_router(yape.router)
app.include_router(referrals.router)
app.include_router(wagers.router)


class NoCacheHTMLMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if "text/html" in response.headers.get("content-type", ""):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


class StaticCacheMiddleware(BaseHTTPMiddleware):
    """Caché larga en estáticos versionados (?v=) y avatares."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if response.status_code != 200:
            return response
        if path.startswith("/static/"):
            if request.query_params.get("v"):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                response.headers["Cache-Control"] = "public, max-age=604800"
        elif path.startswith("/avatars/"):
            response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
        return response


class ReferralCaptureMiddleware(BaseHTTPMiddleware):
    """Guarda ?ref= en sesión (debe ejecutarse dentro de SessionMiddleware)."""

    async def dispatch(self, request, call_next):
        ref = request.query_params.get("ref")
        if ref:
            from app.referrals import capture_referral_code

            capture_referral_code(request, ref)
        return await call_next(request)


class CanonicalHostMiddleware(BaseHTTPMiddleware):
    """Redirige *.onrender.com al dominio público definido en SITE_URL."""

    async def dispatch(self, request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        configured = os.environ.get("SITE_URL", "").strip().rstrip("/")
        if not configured or os.environ.get("ENVIRONMENT", "").lower() != "production":
            return await call_next(request)
        host = (request.url.hostname or "").lower()
        if host.endswith(".onrender.com"):
            target = configured + request.url.path
            if request.url.query:
                target += "?" + request.url.query
            return RedirectResponse(target, status_code=301)
        return await call_next(request)


app.add_middleware(ReferralCaptureMiddleware)
app.add_middleware(NoCacheHTMLMiddleware)
app.add_middleware(StaticCacheMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SECRET_KEY", "dev-secret-change-in-production"),
    session_cookie="hf_session",
    same_site="lax",
    https_only=os.environ.get("HTTPS_ONLY", "false").lower() == "true",
)
app.add_middleware(CanonicalHostMiddleware)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/health")
def health():
    commit = os.environ.get("RENDER_GIT_COMMIT", "").strip()
    payload: dict = {"status": "ok"}
    if commit:
        payload["commit"] = commit[:7]
    return payload


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(
        BASE_DIR / "static" / "favicon-32.png",
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400, stale-while-revalidate=604800"},
    )


@app.get("/avatars/{user_id}", include_in_schema=False)
async def user_avatar_image(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user or not user.picture:
        raise HTTPException(status_code=404, detail="Avatar no encontrado")
    try:
        body, content_type = await fetch_avatar(user.picture)
    except Exception:
        return FileResponse(
            BASE_DIR / "static" / "favicon-32.png",
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=300"},
        )
    return Response(
        content=body,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/robots.txt", include_in_schema=False)
def robots_txt(request: Request):
    base = site_base_url(request)
    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin/",
            "Disallow: /auth/",
            "Disallow: /cuenta",
            "Disallow: /verificar-telefono",
            "Disallow: /avatars/",
            "",
            f"Sitemap: {base}/sitemap.xml",
            "",
        ]
    )
    return Response(content=body, media_type="text/plain; charset=utf-8")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml(request: Request, db: Session = Depends(get_db)):
    from xml.sax.saxutils import escape

    base = site_base_url(request)
    static_routes = [
        ("/", "daily", "1.0", None),
        ("/proximamente", "weekly", "0.8", None),
        ("/privacidad", "monthly", "0.4", None),
        ("/terminos", "monthly", "0.4", None),
        ("/preguntas-frecuentes", "monthly", "0.5", None),
    ]
    urls: list[str] = []
    for path, changefreq, priority, lastmod in static_routes:
        loc = escape(f"{base}{path}")
        chunk = [f"  <url><loc>{loc}</loc>", f"    <changefreq>{changefreq}</changefreq>", f"    <priority>{priority}</priority>"]
        if lastmod:
            chunk.append(f"    <lastmod>{lastmod}</lastmod>")
        chunk.append("  </url>")
        urls.append("\n".join(chunk))

    matches = db.query(Match).order_by(Match.match_date.desc()).limit(300).all()
    for match in matches:
        path = f"/partidos/{match.id}"
        loc = escape(f"{base}{path}")
        lastmod = format_sitemap_lastmod(match.match_date)
        urls.append(
            "\n".join(
                [
                    f"  <url><loc>{loc}</loc>",
                    f"    <lastmod>{lastmod}</lastmod>",
                    "    <changefreq>weekly</changefreq>",
                    "    <priority>0.6</priority>",
                    "  </url>",
                ]
            )
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )
    return Response(content=xml, media_type="application/xml; charset=utf-8")


async def _html_http_error(request: Request, status_code: int, detail: str):
    if wants_ajax(request):
        return JSONResponse({"ok": False, "error": detail}, status_code=status_code)
    if status_code == 404:
        return render_error_page(
            request,
            status_code=404,
            title="Página no encontrada",
            message="El enlace no existe o el balón ya se fue del estadio. Vuelve al inicio para seguir con tus predicciones.",
        )
    return await http_exception_handler(request, HTTPException(status_code=status_code, detail=detail))


@app.exception_handler(StarletteHTTPException)
async def hf_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return await _html_http_error(request, exc.status_code, exc.detail)


@app.exception_handler(404)
async def hf_not_found_handler(request: Request, exc: StarletteHTTPException):
    return await _html_http_error(request, 404, getattr(exc, "detail", "Not Found"))


@app.exception_handler(Exception)
async def hf_unhandled_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, RequestValidationError):
        return await request_validation_exception_handler(request, exc)
    if wants_ajax(request):
        return JSONResponse(
            {"ok": False, "error": "Error interno del servidor"},
            status_code=500,
        )
    import logging

    logging.getLogger("uvicorn.error").exception("Unhandled server error")
    return render_error_page(
        request,
        status_code=500,
        title="Error del servidor",
        message="Algo falló en nuestro lado. El hamster está revisando la jugada — inténtalo de nuevo en un momento.",
    )


@app.on_event("startup")
def on_startup():
    from app.yape_policy import yape_payments_enabled

    templates.env.globals["YAPE_PAYMENTS_ENABLED"] = yape_payments_enabled()
    templates.env.globals["SORTEO_POPUP_ENABLED"] = sorteo_popup_enabled()
    _validate_oauth_config()
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    db = next(get_db())
    try:
        from app.services import seed_database
        from app.points_rules import seed_default_rules
        from app.referrals import ensure_referral_code

        seed_database(db)
        seed_default_rules(db)
        for user in db.query(User).filter(User.referral_code.is_(None)).all():
            ensure_referral_code(db, user)
    finally:
        db.close()


def _validate_oauth_config() -> None:
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        import logging
        logging.getLogger("uvicorn.error").warning(
            "GOOGLE_CLIENT_ID o GOOGLE_CLIENT_SECRET vacíos. "
            "Configura .env y reinicia el servidor (make dev)."
        )


def _run_migrations():
    from sqlalchemy import text

    from app.phone_policy import enforce_unique_phone

    is_pg = "postgresql" in str(engine.url)

    if is_pg:
        # ALTER TYPE ADD VALUE requiere autocommit (no puede correr en transacción)
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("ALTER TYPE predictiontype ADD VALUE IF NOT EXISTS 'SCORE';"))
            conn.execute(text("ALTER TYPE predictiontype ADD VALUE IF NOT EXISTS 'OUTCOME';"))

    with engine.begin() as conn:
        if is_pg:
            conn.execute(text(
                "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS user_id INTEGER"
                " REFERENCES users(id) ON DELETE SET NULL;"
            ))
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20);"
            ))
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN"
                " NOT NULL DEFAULT FALSE;"
            ))
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified_at TIMESTAMP;"
            ))
            conn.execute(text(
                "ALTER TABLE categories ADD COLUMN IF NOT EXISTS description VARCHAR(255);"
            ))
            conn.execute(text(
                "ALTER TABLE categories ADD COLUMN IF NOT EXISTS season VARCHAR(20);"
            ))
            conn.execute(text(
                "ALTER TABLE categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN"
                " NOT NULL DEFAULT TRUE;"
            ))
            if enforce_unique_phone():
                conn.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone_number"
                    " ON users (phone_number) WHERE phone_number IS NOT NULL;"
                ))
            else:
                conn.execute(text("DROP INDEX IF EXISTS ix_users_phone_number"))
            conn.execute(text(
                "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS predicted_home_score INTEGER;"
            ))
            conn.execute(text(
                "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS predicted_away_score INTEGER;"
            ))
            conn.execute(text(
                "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS outcome_pick VARCHAR(2);"
            ))
            conn.execute(text(
                "ALTER TABLE categories ADD COLUMN IF NOT EXISTS starts_at TIMESTAMP;"
            ))
            conn.execute(text(
                "ALTER TABLE categories ADD COLUMN IF NOT EXISTS champion_team VARCHAR(100);"
            ))
            conn.execute(text(
                "ALTER TABLE categories ADD COLUMN IF NOT EXISTS champion_closes_at TIMESTAMP;"
            ))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_predictions_user_match_type"
                " ON predictions (user_id, match_id, type);"
            ))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_champion_predictions_user_category"
                " ON champion_predictions (user_id, category_id);"
            ))
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR(12);"
            ))
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by_id INTEGER"
                " REFERENCES users(id) ON DELETE SET NULL;"
            ))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_referral_code"
                " ON users (referral_code) WHERE referral_code IS NOT NULL;"
            ))
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS platform_settings (
                    key VARCHAR(64) PRIMARY KEY,
                    value VARCHAR(255) NOT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            ))
        else:
            user_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(users)"))}
            if "phone_number" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN phone_number VARCHAR(20);"))
            if "phone_verified" not in user_cols:
                conn.execute(text(
                    "ALTER TABLE users ADD COLUMN phone_verified BOOLEAN NOT NULL DEFAULT 0;"
                ))
            if "phone_verified_at" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN phone_verified_at DATETIME;"))
            if "referral_code" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN referral_code VARCHAR(12);"))
            if "referred_by_id" not in user_cols:
                conn.execute(text(
                    "ALTER TABLE users ADD COLUMN referred_by_id INTEGER REFERENCES users(id);"
                ))

            cat_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(categories)"))}
            if "description" not in cat_cols:
                conn.execute(text("ALTER TABLE categories ADD COLUMN description VARCHAR(255);"))
            if "season" not in cat_cols:
                conn.execute(text("ALTER TABLE categories ADD COLUMN season VARCHAR(20);"))
            if "is_active" not in cat_cols:
                conn.execute(text(
                    "ALTER TABLE categories ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1;"
                ))

            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(predictions)"))}
            if "user_id" not in cols:
                conn.execute(text(
                    "ALTER TABLE predictions ADD COLUMN user_id INTEGER REFERENCES users(id);"
                ))
            if "predicted_home_score" not in cols:
                conn.execute(text("ALTER TABLE predictions ADD COLUMN predicted_home_score INTEGER;"))
            if "predicted_away_score" not in cols:
                conn.execute(text("ALTER TABLE predictions ADD COLUMN predicted_away_score INTEGER;"))
            if "outcome_pick" not in cols:
                conn.execute(text("ALTER TABLE predictions ADD COLUMN outcome_pick VARCHAR(2);"))

            if "starts_at" not in cat_cols:
                conn.execute(text("ALTER TABLE categories ADD COLUMN starts_at DATETIME;"))
            if "champion_team" not in cat_cols:
                conn.execute(text("ALTER TABLE categories ADD COLUMN champion_team VARCHAR(100);"))
            if "champion_closes_at" not in cat_cols:
                conn.execute(text("ALTER TABLE categories ADD COLUMN champion_closes_at DATETIME;"))

            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_predictions_user_match_type"
                " ON predictions (user_id, match_id, type);"
            ))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_champion_predictions_user_category"
                " ON champion_predictions (user_id, category_id);"
            ))

            tables = {
                row[0]
                for row in conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
            }
            if "platform_settings" not in tables:
                conn.execute(text(
                    """
                    CREATE TABLE platform_settings (
                        key VARCHAR(64) PRIMARY KEY,
                        value VARCHAR(255) NOT NULL,
                        updated_at DATETIME NOT NULL
                    );
                    """
                ))


def prediction_label(p: Prediction) -> str:
    if p.type == PredictionType.SCORE:
        if p.predicted_home_score is not None and p.predicted_away_score is not None:
            return f"Marcador: {p.predicted_home_score} - {p.predicted_away_score}"
        return "Marcador"
    if p.type == PredictionType.OUTCOME:
        labels = {"1": "Gana local", "X": "Empate", "2": "Gana visitante"}
        return f"Resultado: {labels.get(p.outcome_pick or '', p.outcome_pick)}"
    if p.type == PredictionType.DOUBLE_CHANCE:
        labels = {"1X": "Local o Empate", "X2": "Empate o Visitante", "12": "Local o Visitante"}
        return f"Doble oportunidad: {labels.get(p.double_chance or '', p.double_chance)}"
    direction = "Más de" if p.over_under_pick == "over" else "Menos de"
    return f"{direction} {p.over_under_line} goles"


from app.predictions_view import (
    match_hamster_gif,
    match_user_outcome,
    match_user_score,
    outcome_pick_label,
    predictions_cutoff_ms,
    score_label,
    user_has_predictions,
    SHOW_MATCH_HAMSTER_GIFS,
)
from app.flags import team_flag_url
from app.timezone import format_pet, pet_timestamp_ms
from app.points import CHAMPION_HIT_POINTS, SCORE_HIT_POINTS, leaderboard, user_hamster_points

templates.env.globals["static_url"] = static_url
templates.env.globals["prediction_label"] = prediction_label
templates.env.globals["format_pet"] = format_pet
templates.env.globals["pet_timestamp_ms"] = pet_timestamp_ms
templates.env.globals["predictions_cutoff_ms"] = predictions_cutoff_ms
templates.env.globals["match_user_score"] = match_user_score
templates.env.globals["match_user_outcome"] = match_user_outcome
templates.env.globals["outcome_pick_label"] = outcome_pick_label
templates.env.globals["match_hamster_gif"] = match_hamster_gif
templates.env.globals["SHOW_MATCH_HAMSTER_GIFS"] = SHOW_MATCH_HAMSTER_GIFS
templates.env.globals["user_has_predictions"] = user_has_predictions
templates.env.globals["score_label"] = score_label
templates.env.globals["team_flag_url"] = team_flag_url
templates.env.globals["SCORE_HIT_POINTS"] = SCORE_HIT_POINTS
templates.env.globals["CHAMPION_HIT_POINTS"] = CHAMPION_HIT_POINTS
templates.env.globals["PredictionResult"] = PredictionResult
templates.env.globals["PredictionType"] = PredictionType

from app.yape_policy import YAPE_PACKAGES, YAPE_RECIPIENT_NAME, yape_payments_enabled


def sorteo_popup_enabled() -> bool:
    return os.environ.get("SORTEO_POPUP_ENABLED", "false").strip().lower() in ("1", "true", "yes")


templates.env.globals["YAPE_PAYMENTS_ENABLED"] = yape_payments_enabled()
templates.env.globals["SORTEO_POPUP_ENABLED"] = sorteo_popup_enabled()
templates.env.globals["YAPE_PACKAGES"] = YAPE_PACKAGES
templates.env.globals["YAPE_RECIPIENT_NAME"] = YAPE_RECIPIENT_NAME

SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "soporte@hamsterfijas.com").strip() or "soporte@hamsterfijas.com"
SUPPORT_INSTAGRAM_URL = os.environ.get(
    "SUPPORT_INSTAGRAM_URL", "https://www.instagram.com/hamsterfijas/"
).strip() or "https://www.instagram.com/hamsterfijas/"
SUPPORT_INSTAGRAM_HANDLE = os.environ.get("SUPPORT_INSTAGRAM_HANDLE", "@hamsterfijas").strip() or "@hamsterfijas"

templates.env.globals["SUPPORT_EMAIL"] = SUPPORT_EMAIL
templates.env.globals["SUPPORT_INSTAGRAM_URL"] = SUPPORT_INSTAGRAM_URL
templates.env.globals["SUPPORT_INSTAGRAM_HANDLE"] = SUPPORT_INSTAGRAM_HANDLE
templates.env.globals["SUPPORT_INSTAGRAM_EXTERNAL"] = SUPPORT_INSTAGRAM_URL.startswith("http")

def _public_env(name: str, *, production_default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    if os.environ.get("ENVIRONMENT", "").lower() == "production":
        return production_default
    return ""


templates.env.globals["GA_MEASUREMENT_ID"] = _public_env(
    "GA_MEASUREMENT_ID", production_default="G-W394R9W8E7"
)
templates.env.globals["CLARITY_PROJECT_ID"] = _public_env(
    "CLARITY_PROJECT_ID", production_default="x51o85xggi"
)
templates.env.globals["avatar_url"] = avatar_url_for_user

from app.seo import (
    DEFAULT_META_DESCRIPTION,
    SITE_NAME,
    canonical_url,
    default_robots,
    format_sitemap_lastmod,
    og_image_url,
    site_base_url,
)

templates.env.globals["SITE_NAME"] = SITE_NAME
templates.env.globals["DEFAULT_META_DESCRIPTION"] = DEFAULT_META_DESCRIPTION
templates.env.globals["site_base_url"] = site_base_url
templates.env.globals["canonical_url"] = canonical_url
templates.env.globals["og_image_url"] = og_image_url
templates.env.globals["default_robots"] = default_robots


def _home_url(
    category_id: Optional[int] = None,
    match_date: Optional[str] = None,
    group: Optional[str] = None,
) -> str:
    from app.hf_response import home_url

    return home_url(category_id, match_date, group)


templates.env.globals["home_url"] = _home_url

# ── Auth ────────────────────────────────────────────────────────────────────

@app.get("/auth/login")
async def auth_login(request: Request):
    from app.referrals import capture_referral_code

    capture_referral_code(request, request.query_params.get("ref"))
    redirect_uri = request.url_for("auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    from app.flash import flash
    from app.referrals import resolve_referrer_id

    token = await oauth.google.authorize_access_token(request)
    info = token.get("userinfo") or await oauth.google.userinfo(token=token)
    ref_code = request.session.get("referral_code")
    referred_by_id = resolve_referrer_id(db, ref_code) if ref_code else None
    had_referrer = bool(
        db.query(User).filter(User.google_id == info["sub"], User.referred_by_id.isnot(None)).first()
    )
    user = upsert_user(
        db,
        google_id=info["sub"],
        email=info["email"],
        name=info.get("name", info["email"]),
        picture=info.get("picture", ""),
        referred_by_id=referred_by_id,
    )
    if ref_code:
        request.session.pop("referral_code", None)
    if referred_by_id and user.referred_by_id == referred_by_id and not had_referrer:
        referrer = db.get(User, referred_by_id)
        if referrer:
            flash(request, msg=f"Invitación de {referrer.name.split()[0]} registrada. Verifica tu celular para ganar HP extra.")
    request.session["user_id"] = user.id
    if not user.phone_verified and not user.is_admin:
        return RedirectResponse("/verificar-telefono", status_code=303)
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
    match_date: Optional[str] = None,
    group: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
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

    matches_query, selected_date = filter_matches_by_date(matches_query, match_date) if match_date else (matches_query, None)
    matches_query, selected_group = filter_matches_by_group(matches_query, group)
    matches = matches_query.all()
    available_dates = get_available_match_dates(db, selected)
    available_groups = get_available_groups(db, selected)
    group_summaries = get_group_summaries(db, selected, current_user.id if current_user else None) if selected else []
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
    wager_balance_info = None
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
    else:
        wager_ctx = None

    return render(
        "index.html",
        {
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
        },
        request=request,
        db=db,
        current_user=current_user,
    )


@app.get("/proximamente", response_class=HTMLResponse)
def puntos_page(
    request: Request,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    categories = db.query(Category).filter(Category.is_active.is_(True)).order_by(Category.name).all()
    selected = category_id or (categories[0].id if categories else None)
    selected_category = next((c for c in categories if c.id == selected), None)
    board = leaderboard(db, selected)
    my_points = user_hamster_points(db, current_user.id, selected) if current_user else None
    from app.points_rules import rules_dict

    hp_rules = rules_dict(db, selected)
    countdown_ms = None
    if selected_category:
        from app.services import get_tournament_starts_at
        starts_at = get_tournament_starts_at(db, selected_category)
        if starts_at:
            countdown_ms = pet_timestamp_ms(starts_at)

    from app.prize_tiers import get_current_tier

    tier_ctx = get_current_tier(db)

    return render(
        "proximamente.html",
        {
            "categories": categories,
            "selected_category_id": selected,
            "selected_category": selected_category,
            "leaderboard": board,
            "my_points": my_points,
            "hp_rules": hp_rules,
            "countdown_ms": countdown_ms,
            "current_tier": tier_ctx["current_tier"],
            "next_tier": tier_ctx["next_tier"],
            "verified_count": tier_ctx["verified_count"],
            "progreso": tier_ctx["progreso"],
            "locked_tiers": tier_ctx["locked_tiers"],
            "is_max_tier": tier_ctx["is_max_tier"],
        },
        request=request,
        db=db,
        current_user=current_user,
    )


@app.get("/privacidad", response_class=HTMLResponse)
def privacy_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    return render("privacidad.html", {}, request=request, db=db, current_user=current_user)


@app.get("/terminos", response_class=HTMLResponse)
def terms_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    return render("terminos.html", {}, request=request, db=db, current_user=current_user)


@app.get("/preguntas-frecuentes", response_class=HTMLResponse)
def faq_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    return render("preguntas_frecuentes.html", {}, request=request, db=db, current_user=current_user)


@app.get("/demo/v2", response_class=HTMLResponse, include_in_schema=False)
def demo_v2_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    from app.routers.v2_demo import build_v2_dashboard_context

    demo = build_v2_dashboard_context(db, current_user)
    return render(
        "v2/dashboard.html",
        {"demo": demo, "selected_category_id": demo.get("selected_category_id")},
        request=request,
        db=db,
        current_user=current_user,
    )


@app.get("/partidos/{match_id}", response_class=HTMLResponse)
def match_predictions_page(
    match_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    match = (
        db.query(Match)
        .options(joinedload(Match.predictions).joinedload(Prediction.user), joinedload(Match.category))
        .filter(Match.id == match_id)
        .first()
    )
    if not match:
        raise HTTPException(404, "Partido no encontrado")

    my_predictions = [
        p for p in match.predictions
        if current_user and p.user_id == current_user.id and p.type == PredictionType.SCORE
    ]
    my_outcome = next(
        (
            p for p in match.predictions
            if current_user and p.user_id == current_user.id and p.type == PredictionType.OUTCOME
        ),
        None,
    )
    others = []
    if current_user:
        others = [
            p for p in match.predictions
            if (
                p.type == PredictionType.SCORE
                and p.user_id is not None
                and p.user_id != current_user.id
            )
        ]

    my_wager = None
    wager_ctx = None
    if current_user and current_user.phone_verified:
        from app.models import PointWager, WagerStatus
        from app.wagers import MAX_STAKE, MIN_STAKE, WAGER_PICKS, wager_balance

        my_wager = (
            db.query(PointWager)
            .filter(PointWager.user_id == current_user.id, PointWager.match_id == match.id)
            .order_by(PointWager.created_at.desc())
            .first()
        )
        wager_ctx = {
            "balance": wager_balance(db, current_user.id, match.category_id),
            "picks": WAGER_PICKS,
            "min_stake": MIN_STAKE,
            "max_stake": MAX_STAKE,
            "WagerStatus": WagerStatus,
        }

    return render(
        "match_detail.html",
        {
            "match": match,
            "my_predictions": my_predictions,
            "my_outcome": my_outcome,
            "outcome_labels": OUTCOME_PICK_LABELS,
            "other_predictions": others,
            "my_wager": my_wager,
            "wager_ctx": wager_ctx,
        },
        request=request,
        db=db,
        current_user=current_user,
    )


# ── Admin: Categories ────────────────────────────────────────────────────────

@app.post("/categories")
def create_category(
    name: str = Form(...),
    description: str = Form(""),
    season: str = Form(""),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    name = name.strip()
    if not name:
        raise HTTPException(400, "Nombre requerido")
    if db.query(Category).filter(Category.name == name).first():
        raise HTTPException(400, "El torneo ya existe")
    db.add(Category(
        name=name,
        description=description.strip() or None,
        season=season.strip() or None,
        is_active=True,
    ))
    db.commit()
    return RedirectResponse("/admin/torneos", status_code=303)


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


def _official_score_payload(db: Session, match: Match, admin: User) -> dict:
    data: dict = {
        "match_id": match.id,
        "home_score": match.home_score,
        "away_score": match.away_score,
        "finished": match.is_finished,
        "predictions_open": match.predictions_open,
        "official_label": (
            f"{match.home_score} - {match.away_score}" if match.is_finished else None
        ),
    }
    pred = (
        db.query(Prediction)
        .filter(
            Prediction.match_id == match.id,
            Prediction.user_id == admin.id,
            Prediction.type == PredictionType.SCORE,
        )
        .first()
    )
    if pred:
        data["result"] = pred.result.value
    return data


@app.post("/matches/{match_id}/score")
def update_score(
    request: Request,
    match_id: int,
    home_score: int = Form(...),
    away_score: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    match = db.query(Match).options(joinedload(Match.predictions)).get(match_id)
    if not match:
        raise HTTPException(404)
    match.home_score = home_score
    match.away_score = away_score
    from app.services import reevaluate_match_predictions
    from app.group_leader import evaluate_group_leaders
    from app.wagers import settle_wagers_for_match

    reevaluate_match_predictions(db, match)
    evaluate_group_leaders(db, match.category_id)
    settle_wagers_for_match(db, match)
    return ajax_or_redirect(
        request,
        f"/partidos/{match_id}",
        _official_score_payload(db, match, current_user),
    )


@app.post("/matches/{match_id}/score/clear")
def clear_score(
    request: Request,
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    match = db.query(Match).options(joinedload(Match.predictions)).get(match_id)
    if not match:
        raise HTTPException(404)
    if not match.is_finished:
        return ajax_or_redirect(
            request,
            f"/partidos/{match_id}",
            _official_score_payload(db, match, current_user),
        )
    match.home_score = None
    match.away_score = None
    from app.services import reevaluate_match_predictions
    from app.wagers import settle_wagers_for_match

    reevaluate_match_predictions(db, match)
    settle_wagers_for_match(db, match)
    return ajax_or_redirect(
        request,
        f"/partidos/{match_id}?msg=Marcador+oficial+eliminado",
        _official_score_payload(db, match, current_user),
    )


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
    request: Request,
    match_id: int = Form(...),
    predicted_home_score: int = Form(...),
    predicted_away_score: int = Form(...),
    return_category_id: Optional[int] = Form(None),
    return_match_date: str = Form(""),
    return_group: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified),
):
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(404)
    cat_id = return_category_id or match.category_id
    url = _home_url(cat_id, return_match_date.strip() or None, return_group.strip() or None)
    from app.hf_response import ajax_error

    if not match.predictions_open:
        if match.is_finished:
            return ajax_error(request, url, "No puedes modificar predicciones: el partido ya tiene resultado oficial", status_code=403)
        return ajax_error(request, url, "Las predicciones cerraron 5 minutos antes del inicio", status_code=403)
    if predicted_home_score < 0 or predicted_away_score < 0:
        return ajax_error(request, url, "Marcador inválido", status_code=400)

    existing = (
        db.query(Prediction)
        .filter(
            Prediction.match_id == match_id,
            Prediction.user_id == current_user.id,
            Prediction.type == PredictionType.SCORE,
        )
        .first()
    )

    if existing:
        if existing.user_id != current_user.id:
            raise HTTPException(403, "No puedes modificar la predicción de otro usuario")
        existing.predicted_home_score = predicted_home_score
        existing.predicted_away_score = predicted_away_score
        if match.is_finished:
            from app.services import evaluate_prediction
            existing.result = evaluate_prediction(existing, match)
        else:
            existing.result = PredictionResult.PENDING
        prediction = existing
    else:
        prediction = Prediction(
            match_id=match_id,
            user_id=current_user.id,
            type=PredictionType.SCORE,
            predicted_home_score=predicted_home_score,
            predicted_away_score=predicted_away_score,
        )
        db.add(prediction)

    if match.is_finished:
        from app.services import evaluate_prediction
        prediction.result = evaluate_prediction(prediction, match)

    db.commit()

    from app.points import user_hamster_points

    return ajax_or_redirect(
        request,
        url,
        {
            "match_id": match_id,
            "predicted_home_score": predicted_home_score,
            "predicted_away_score": predicted_away_score,
            "label": f"{predicted_home_score} - {predicted_away_score}",
            "result": prediction.result.value,
            "updated": existing is not None,
            "user_points": user_hamster_points(db, current_user.id, cat_id),
        },
    )


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
    return RedirectResponse(f"/partidos/{prediction.match_id}", status_code=303)


OUTCOME_PICK_LABELS = {"1": "Gana local", "X": "Empate", "2": "Gana visitante"}


@app.post("/predictions/outcome")
def save_outcome_prediction(
    request: Request,
    match_id: int = Form(...),
    outcome_pick: str = Form(...),
    return_category_id: Optional[int] = Form(None),
    return_match_date: str = Form(""),
    return_group: str = Form(""),
    return_to: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified),
):
    from app.hf_response import ajax_error, ajax_or_redirect, safe_back
    from app.services import evaluate_prediction

    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(404)
    cat_id = return_category_id or match.category_id
    back = safe_back(
        return_to,
        _home_url(cat_id, return_match_date.strip() or None, return_group.strip() or None),
    )
    pick = outcome_pick.strip().upper()
    if pick not in OUTCOME_PICK_LABELS:
        return ajax_error(request, back, "Elige un resultado válido: local, empate o visitante.")
    if not match.predictions_open:
        return ajax_error(request, back, "Las predicciones cerraron para este partido.")

    existing = (
        db.query(Prediction)
        .filter(
            Prediction.match_id == match_id,
            Prediction.user_id == current_user.id,
            Prediction.type == PredictionType.OUTCOME,
        )
        .first()
    )
    if existing:
        existing.outcome_pick = pick
        existing.result = PredictionResult.PENDING
        prediction = existing
        updated = True
    else:
        prediction = Prediction(
            match_id=match_id,
            user_id=current_user.id,
            type=PredictionType.OUTCOME,
            outcome_pick=pick,
        )
        db.add(prediction)
        updated = False

    if match.is_finished:
        prediction.result = evaluate_prediction(prediction, match)

    db.commit()
    db.refresh(prediction)

    from app.points import user_hamster_points

    label = OUTCOME_PICK_LABELS[pick]
    if pick == "1":
        label = f"Gana {match.home_team}"
    elif pick == "2":
        label = f"Gana {match.away_team}"

    return ajax_or_redirect(
        request,
        back,
        {
            "match_id": match_id,
            "outcome_pick": pick,
            "outcome_label": label,
            "result": prediction.result.value,
            "updated": updated,
            "user_points": user_hamster_points(db, current_user.id, cat_id),
        },
    )


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
    if not current_user.is_admin and not prediction.match.predictions_open:
        raise HTTPException(403, "No puedes eliminar predicciones después del cierre")
    db.delete(prediction)
    db.commit()
    return RedirectResponse(f"/?category_id={prediction.match.category_id}", status_code=303)


@app.post("/champion-predictions")
def save_champion_prediction(
    request: Request,
    category_id: int = Form(...),
    champion_team: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified),
):
    from app.flags import team_flag_url
    from app.services import champion_predictions_open, get_tournament_teams

    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Torneo no encontrado")
    if not champion_predictions_open(db, category):
        raise HTTPException(403, "Las predicciones de campeón ya cerraron")

    team = champion_team.strip()
    allowed = get_tournament_teams(db, category_id)
    if team not in allowed:
        raise HTTPException(400, "Selección no válida para este torneo")

    existing = (
        db.query(ChampionPrediction)
        .filter(
            ChampionPrediction.user_id == current_user.id,
            ChampionPrediction.category_id == category_id,
        )
        .first()
    )
    if existing:
        existing.champion_team = team
        existing.result = PredictionResult.PENDING
        cp = existing
    else:
        cp = ChampionPrediction(
            user_id=current_user.id,
            category_id=category_id,
            champion_team=team,
        )
        db.add(cp)

    if category.champion_decided and category.champion_team:
        winner = category.champion_team.strip()
        cp.result = PredictionResult.HIT if team == winner else PredictionResult.MISS

    db.commit()
    from app.points import user_hamster_points
    from app.services import get_champion_prediction_stats

    stats = get_champion_prediction_stats(db, category_id)
    champion_stats = {
        "total": stats["total"],
        "by_team": stats["by_team"],
        "teams": [
            {
                "team": row["team"],
                "count": row["count"],
                "pct": row["pct"],
                "flag_url": team_flag_url(row["team"]),
            }
            for row in stats["teams"]
        ],
    }

    return ajax_or_redirect(
        request,
        f"/?category_id={category_id}#campeon",
        {
            "category_id": category_id,
            "champion_team": team,
            "flag_url": team_flag_url(team),
            "result": cp.result.value,
            "updated": existing is not None,
            "user_points": user_hamster_points(db, current_user.id, category_id),
            "champion_stats": champion_stats,
        },
    )
