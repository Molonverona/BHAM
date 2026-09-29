#!/usr/bin/env bash
# ==============================================================================
# BHAM – Setup Permessi per Accesso Hardware
# Configura i permessi necessari per porte seriali e ARP sniffing su Linux.
# ==============================================================================

set -e

SYSTEM=$(uname -s)
USER_NAME=${SUDO_USER:-$USER}

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  BHAM – Setup Permessi Hardware                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

if [ "$SYSTEM" != "Linux" ]; then
  echo "❌ Questo script è per Linux. Su Windows/macOS segui le istruzioni nel README."
  exit 1
fi

if [ "$EUID" -ne 0 ]; then
  echo "❌ Questo script richiede privilegi root. Esegui con:"
  echo "   sudo $0"
  exit 1
fi

echo "Configurazione permessi per: $USER_NAME"
echo ""

# ── 1. Aggiungi utente al gruppo dialout (porte seriali RS485) ──────────────
echo "📝 Passo 1/2: Configurazione accesso porte seriali (gruppo 'dialout')..."
if id -nG "$USER_NAME" | grep -qw dialout; then
  echo "  ✅ $USER_NAME è già nel gruppo dialout"
else
  echo "  → Aggiunta di $USER_NAME al gruppo dialout..."
  usermod -aG dialout "$USER_NAME"
  echo "  ✅ Fatto. Richiede logout/login per avere effetto."
fi

echo ""

# ── 2. Imposta CAP_NET_RAW per ARP sniffer ─────────────────────────────────
echo "📝 Passo 2/2: Configurazione ARP sniffer (CAP_NET_RAW)..."
VENV_PYTHON=".venv/bin/python3"
if [ ! -f "$VENV_PYTHON" ]; then
  echo "  ⚠️  Ambiente virtuale non trovato in .venv"
  echo "     Crea l'ambiente con: python3 -m venv .venv && pip install -r requirements.txt"
  VENV_PYTHON="$(which python3)"
  echo "     Userò il Python di sistema: $VENV_PYTHON"
fi

if [ -f "$VENV_PYTHON" ]; then
  echo "  → Impostazione CAP_NET_RAW su $VENV_PYTHON..."
  setcap cap_net_raw+eip "$VENV_PYTHON" 2>/dev/null && {
    echo "  ✅ Fatto. ARP sniffer ora disponibile senza sudo."
  } || {
    echo "  ⚠️  Impostazione CAP_NET_RAW fallita (potrebbe non essere supportato)."
    echo "     Soluzione alternativa: esegui BHAM con:  sudo python3 main.py"
  }
else
  echo "  ❌ Python non trovato"
  exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✅ Setup completato!"
echo ""
echo "  📌 Prossimi passi:"
echo "  1. Se hai aggiunto $USER_NAME a 'dialout': LOGOUT e LOGIN"
echo "  2. Avvia BHAM con:  ./start.sh"
echo ""
echo "════════════════════════════════════════════════════════════"
