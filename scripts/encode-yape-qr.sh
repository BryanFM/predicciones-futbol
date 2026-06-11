#!/usr/bin/env bash
# Genera base64 del QR para Render Secret File (no uses YAPE_QR_BASE64 si pesa >100 KB).
set -euo pipefail
cd "$(dirname "$0")/.."

QR="${1:-app/private/yape/qr.png}"
OUT="${2:-app/private/yape/qr.base64.txt}"

if [ ! -f "$QR" ]; then
  echo "Error: no existe $QR"
  echo "Primero: ./scripts/setup-yape-qr.sh /ruta/a/tu-qr.png"
  exit 1
fi

python3 - <<PY
import base64
from pathlib import Path
src = Path("$QR")
out = Path("$OUT")
data = src.read_bytes()
b64 = base64.b64encode(data).decode("ascii")
out.write_text(b64)
print(f"Imagen: {src} ({len(data)} bytes)")
print(f"Base64: {out} ({len(b64)} caracteres)")
print("Media type: image/png")
if len(b64) > 100_000:
    print("")
    print("⚠️  Base64 grande — NO pegues en YAPE_QR_BASE64 en Render.")
    print("   Usa Secret File (ver abajo).")
PY

if command -v pbcopy >/dev/null 2>&1; then
  pbcopy < "$OUT"
  echo "✓ Copiado al portapapeles"
fi

echo ""
echo "── Render (recomendado) ──"
echo "1. Environment → elimina YAPE_QR_BASE64 si la creaste"
echo "2. Secret Files → + Add Secret File"
echo "   Filename: yape-qr.b64"
echo "   Contents: pega todo el archivo $OUT"
echo "3. Save Changes → redeploy"
echo ""
echo "Prueba: https://predicciones-futbol-tmyr.onrender.com/comprar-yape"
