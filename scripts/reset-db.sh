#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

source .venv/bin/activate 2>/dev/null || true

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

URL="${DATABASE_URL:-sqlite:///./predicciones.db}"

if [[ "$URL" == sqlite* ]]; then
  rm -f predicciones.db
  echo "→ SQLite eliminado. Se recreará al iniciar la app."
else
  echo "→ Reseteando PostgreSQL local..."
  docker compose exec -T db psql -U predicciones -d predicciones -c "
    DROP SCHEMA public CASCADE;
    CREATE SCHEMA public;
    GRANT ALL ON SCHEMA public TO predicciones;
  " 2>/dev/null || echo "  (¿Está corriendo 'make db-up'?)"
fi

python3 -c "
from app.database import Base, engine
from app.services import seed_database
from app.database import SessionLocal
Base.metadata.create_all(bind=engine)
db = SessionLocal()
seed_database(db)
db.close()
print('→ Tablas creadas y seed del Mundial aplicado.')
"
