#!/usr/bin/env bash
# Comprueba que el proyecto está listo para Render antes de push.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="python3"
if [ -d .venv ]; then
  PYTHON=".venv/bin/python"
else
  echo "→ Instalando dependencias (sin venv)…"
  pip install -q -r requirements.txt
fi

echo "→ Importando app (ENVIRONMENT=production)…"
ENVIRONMENT=production HTTPS_ONLY=true "$PYTHON" -c "from app.main import app; assert app.title"

echo "→ OK — listo para deploy en Render"
echo "  Push a master → auto-deploy si está activado"
echo "  URL pública: https://hamsterfijas.com/"
