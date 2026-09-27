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
  WARN=0

  # Controlla gruppo dialout (porte seriali RS485)
  if ! groups | grep -qw dialout; then
    echo ""
    echo "⚠️  AVVISO – Porte seriali RS485"
    echo "   Il tuo utente non è nel gruppo 'dialout'."
    echo "   L'ARS Sniffer RS485 NON sarà disponibile finché non esegui:"
    echo ""
    echo "     sudo usermod -aG dialout $USER"
    echo "     (poi effettua logout e login)"
    echo ""
    WARN=1
  fi

  # Controlla CAP_NET_RAW (ARP Sniffer)
  # Legge il bitmask CapPrm da /proc/self/status; bit 13 = CAP_NET_RAW
  CAP_PRM=$(awk '/^CapPrm:/{print $2}' /proc/self/status 2>/dev/null)
  if [ -n "$CAP_PRM" ]; then
    CAP_INT=$((16#$CAP_PRM))
    HAS_NET_RAW=$(( (CAP_INT >> 13) & 1 ))
  else
    HAS_NET_RAW=0
  fi

  if [ "$HAS_NET_RAW" -eq 0 ] && [ "$(id -u)" -ne 0 ]; then
    echo ""
    echo "⚠️  AVVISO – ARP Sniffer (raw socket)"
    echo "   CAP_NET_RAW non impostata su $(which python3)."
    echo "   L'ARP Sniffer NON sarà disponibile finché non esegui:"
    echo ""
    echo "     sudo setcap cap_net_raw+eip .venv/bin/python3"
    echo "   (oppure: sudo python3 main.py  per avvio immediato)"
    echo ""
    WARN=1
  fi

  if [ "$WARN" -eq 0 ]; then
    echo "  ✅  Permessi OK (dialout e cap_net_raw rilevati)"
  fi
fi

echo ""

exec .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8765 --reload
