#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Ejecuta primero: make setup"
  exit 1
fi

source .venv/bin/activate

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

pip install -q -r requirements-dev.txt

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"

echo "→ Hamster Fijas — http://${HOST}:${PORT}"
echo "  Producción: https://predicciones-futbol-tmyr.onrender.com/"
echo "  DB: ${DATABASE_URL:-sqlite:///./predicciones.db}"
echo ""

exec uvicorn app.main:app --reload --host "$HOST" --port "$PORT"
