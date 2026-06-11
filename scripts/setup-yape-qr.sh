#!/usr/bin/env bash
# Copia tu QR de Yape a la carpeta privada del proyecto.
# Uso: ./scripts/setup-yape-qr.sh /ruta/a/tu-qr.png
set -euo pipefail
cd "$(dirname "$0")/.."

DEST_DIR="app/private/yape"

if [ $# -lt 1 ]; then
  echo "Uso: $0 /ruta/a/tu-qr-yape.png"
  echo ""
  echo "Ejemplo:"
  echo "  $0 ~/Downloads/yape-qr.png"
  exit 1
fi

SRC="$1"
if [ ! -f "$SRC" ]; then
  echo "Error: no existe el archivo: $SRC"
  exit 1
fi

lower=$(echo "$SRC" | tr '[:upper:]' '[:lower:]')
case "$lower" in
  *.png|*.jpg|*.jpeg|*.webp) ;;
  *)
    echo "Error: formato no soportado (usa PNG, JPG o WebP)."
    exit 1
    ;;
esac

mkdir -p "$DEST_DIR"
rm -f "$DEST_DIR"/qr.png "$DEST_DIR"/qr.jpg "$DEST_DIR"/qr.jpeg "$DEST_DIR"/qr.webp

if echo "$lower" | grep -q '\.png$'; then
  cp "$SRC" "$DEST_DIR/qr.png"
  OUT="$DEST_DIR/qr.png"
else
  ext="${lower##*.}"
  cp "$SRC" "$DEST_DIR/qr.$ext"
  OUT="$DEST_DIR/qr.$ext"
fi

BYTES=$(wc -c < "$OUT" | tr -d ' ')
if [ "$BYTES" -gt 512000 ]; then
  echo "Advertencia: el archivo pesa más de 512 KB; la app podría rechazarlo."
fi

if .venv/bin/python -c "from app.yape_qr import yape_qr_available; import sys; sys.exit(0 if yape_qr_available() else 1)"; then
  echo "✓ QR instalado y validado: $OUT"
else
  echo "Error: la imagen no pasó la validación (PNG/JPG/WebP válido, máx. 512 KB)."
  exit 1
fi

echo "  Recarga http://127.0.0.1:8000/comprar-yape"
