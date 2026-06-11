"""Rutas de demostración UI v2 — aisladas del sitio principal."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.rendering import render

router = APIRouter(tags=["v2-demo"])

_DEMO_DATA = {
    "user_name": "MaxTorres",
    "level": 12,
    "streak": 7,
    "rank": 38,
    "points": "2,450",
    "accuracy": 68,
    "matches": [
        {"group": "Grupo A", "time": "Hoy · 18:00", "home": "Perú", "home_flag": "🇵🇪", "away": "Chile", "away_flag": "🇨🇱", "prediction": "2-1"},
        {"group": "Grupo B", "time": "Mañ · 15:00", "home": "Brasil", "home_flag": "🇧🇷", "away": "Colombia", "away_flag": "🇨🇴", "prediction": "1-1"},
        {"group": "Grupo C", "time": "Sáb · 20:00", "home": "Argentina", "home_flag": "🇦🇷", "away": "Uruguay", "away_flag": "🇺🇾", "prediction": "3-0"},
        {"group": "Grupo D", "time": "Dom · 17:00", "home": "España", "home_flag": "🇪🇸", "away": "Francia", "away_flag": "🇫🇷", "prediction": "2-2"},
    ],
    "community_outcomes": [
        {"label": "Local", "pct": 42},
        {"label": "Empate", "pct": 28},
        {"label": "Visitante", "pct": 30},
    ],
    "community_scores": [
        {"label": "2-1", "pct": 18},
        {"label": "1-0", "pct": 14},
        {"label": "1-1", "pct": 12},
    ],
    "leaderboard": [
        {"rank": 1, "name": "HamsterPro", "hp": "4,820", "is_me": False},
        {"rank": 2, "name": "GolazoKing", "hp": "4,510", "is_me": False},
        {"rank": 3, "name": "LaChispa", "hp": "4,200", "is_me": False},
        {"rank": 4, "name": "Futbolera", "hp": "3,980", "is_me": False},
        {"rank": 5, "name": "MaxTorres", "hp": "2,450", "is_me": True},
    ],
    "friends": [
        {"name": "Carla", "league": "Amigos del barrio", "hp": "1,890"},
        {"name": "Diego", "league": "Oficina FC", "hp": "1,540"},
        {"name": "Luisa", "league": "Uni 2026", "hp": "980"},
    ],
    "achievements": [
        {"icon": "🔥", "label": "Racha de 5 aciertos"},
        {"icon": "🎯", "label": "Marcador exacto"},
        {"icon": "🏆", "label": "Top 50 semanal"},
        {"icon": "👥", "label": "3 referidos"},
    ],
}


@router.get("/demo/v2", response_class=HTMLResponse, include_in_schema=False)
def dashboard_v2_demo(request: Request, db: Session = Depends(get_db)):
    return render(
        "v2/dashboard.html",
        {"demo": _DEMO_DATA, "hp_rules": {}},
        request=request,
        db=db,
        current_user=None,
    )
