#!/usr/bin/env bash
# ==============================================================================
# BHAM – Open Dashboard
# Apre la pagina di BHAM nel browser (http://localhost:8765)
# Se il server non è ancora attivo, lo avvia automaticamente.
# ==============================================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

URL="http://localhost:8765"

open_page() {
  if command -v firefox >/dev/null 2>&1; then
    firefox "$URL" >/dev/null 2>&1 &
  elif command -v google-chrome >/dev/null 2>&1; then
    google-chrome "$URL" >/dev/null 2>&1 &
  elif command -v chromium >/dev/null 2>&1; then
    chromium "$URL" >/dev/null 2>&1 &
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 &
  else
    echo "Browser non rilevato automaticamente. Apri manualmente: $URL"
  fi
}

if (echo > /dev/tcp/127.0.0.1/8765) 2>/dev/null; then
  echo "✅ BHAM è già in esecuzione su $URL"
  echo "🌐 Apertura dashboard nel browser..."
  open_page
  exit 0
fi

echo "⚡ Avvio di BHAM su $URL ..."
exec ./start.sh "$@"
