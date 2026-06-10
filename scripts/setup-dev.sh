#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "→ Hamster Fijas — setup de desarrollo"

if [ ! -d .venv ]; then
  echo "  Creando entorno virtual..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements-dev.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "  Creado .env desde .env.example — edítalo con tus credenciales de Google."
else
  echo "  .env ya existe, no se sobrescribe."
fi

echo ""
echo "✓ Listo. Próximos pasos:"
echo "  1. Edita .env (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, ADMIN_EMAILS)"
echo "  2. make dev          → SQLite local (http://127.0.0.1:8000)"
echo "  3. make dev-postgres → PostgreSQL como Render (make db-up primero)"
