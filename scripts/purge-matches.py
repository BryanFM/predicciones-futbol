#!/usr/bin/env python3
"""Elimina partidos, predicciones y apuestas; repuebla el calendario del Mundial."""

from __future__ import annotations

import os
import sys


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)

    os.environ.setdefault("ENVIRONMENT", os.environ.get("ENVIRONMENT", "development"))

    from app.database import SessionLocal
    from app.models import Match, PointWager, Prediction
    from app.services import get_mundial_category, sync_mundial_schedule

    db = SessionLocal()
    try:
        wagers = db.query(PointWager).delete()
        predictions = db.query(Prediction).delete()
        matches = db.query(Match).delete()
        db.commit()
        print(f"→ Apuestas eliminadas: {wagers}")
        print(f"→ Predicciones eliminadas: {predictions}")
        print(f"→ Partidos eliminados: {matches}")

        sync_mundial_schedule(db)
        mundial = get_mundial_category(db)
        fresh = (
            db.query(Match).filter(Match.category_id == mundial.id).count()
            if mundial
            else 0
        )
        print(f"→ Calendario Mundial repoblado: {fresh} partidos")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
