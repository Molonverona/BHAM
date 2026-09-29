#!/usr/bin/env bash
# ==============================================================================
# BHAM – Quick Local Launch Script
# ==============================================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [ ! -f ".venv/bin/uvicorn" ]; then
  echo "❌ Ambiente virtuale non trovato in .venv!"
  echo "   Creazione ambiente ed installazione dipendenze..."
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi

echo "=========================================================="
echo "  ⚡ BHAM – BACS Help Auto Mapper"
echo "=========================================================="
echo "  Dashboard Web: http://localhost:8765"
echo "  Swagger Docs:  http://localhost:8765/docs"
echo "  Premi CTRL+C per arrestare il server."
echo "=========================================================="

# ── Controllo permessi (Linux) ──────────────────────────────────────────────
if [ "$(uname -s)" = "Linux" ]; then
  NEED_SUDO=0

  # Controlla gruppo dialout (porte seriali RS485)
  if ! groups | grep -qw dialout; then
    echo ""
    echo "⚠️  Porte seriali RS485: utente non in gruppo 'dialout'"
    NEED_SUDO=1
  fi

  # Controlla CAP_NET_RAW (ARP Sniffer)
  CAP_PRM=$(awk '/^CapPrm:/{print $2}' /proc/self/status 2>/dev/null)
  if [ -n "$CAP_PRM" ]; then
    CAP_INT=$((16#$CAP_PRM))
    HAS_NET_RAW=$(( (CAP_INT >> 13) & 1 ))
  else
    HAS_NET_RAW=0
  fi

  if [ "$HAS_NET_RAW" -eq 0 ] && [ "$(id -u)" -ne 0 ]; then
    echo "⚠️  ARP Sniffer: CAP_NET_RAW non configurata"
    NEED_SUDO=1
  fi

  # Offri esecuzione con sudo se mancano permessi
  if [ "$NEED_SUDO" -eq 1 ]; then
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║ Permessi insufficienti rilevati                        ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
    echo "Per configurare i permessi in modo permanente, esegui:"
    echo "  sudo ./scripts/setup_permissions.sh"
    echo ""
    echo "Opzioni per avviare BHAM:"
    echo "  1. Avvia con sudo (accesso completo subito):"
    echo "     sudo ./start.sh"
    echo ""
    echo "  2. Esegui setup e poi avvia normalmente:"
    echo "     sudo ./scripts/setup_permissions.sh"
    echo "     (logout/login se aggiunti a 'dialout')"
    echo "     ./start.sh"
    echo ""
    read -p "Avvio con sudo? (s/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Ss]$ ]]; then
      exec sudo .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8765 --reload
    fi
  else
    echo "  ✅  Permessi OK (dialout + cap_net_raw)"
  fi
fi

echo ""

exec .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8765 --reload
