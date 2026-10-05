#!/usr/bin/env bash
# ==============================================================================
# BHAM – Linux Universal One-Line Installer
# Hosted on: https://www.bacshelp.com / https://github.com/BacsHelp/BHAM
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/BacsHelp/BHAM/main/scripts/install.sh | sudo bash
#   oppure:
#   curl -fsSL https://bacshelp.com/bham/install.sh | sudo bash
# ==============================================================================

set -e

REPO="BacsHelp/BHAM"
INSTALL_DIR="/usr/local/bin"
SYSTEMD_DIR="/etc/systemd/system"
DESKTOP_DIR="/usr/share/applications"

echo "=========================================================="
echo "  ⚡ BHAM – BACS Help Auto Mapper (Linux Installer)"
echo "  Dominio Ufficiale: https://www.bacshelp.com"
echo "=========================================================="

# 1. Verifica permessi root
if [ "$(id -u)" -ne 0 ]; then
  echo "❌ Questo script deve essere eseguito con privilegi di root (sudo)."
  exit 1
fi

# 2. Rilevamento Architettura
ARCH=$(uname -m)
case "$ARCH" in
  x86_64)
    PKG_ARCH="x64"
    ;;
  *)
    echo "❌ Architettura $ARCH non supportata ufficialmente dal binario standalone (richiesto x86_64)."
    echo "   Per altre architetture, installare via git e virtualenv Python 3.12."
    exit 1
    ;;
esac

# 3. Recupero ultima release da GitHub
echo "🔍 Ricerca ultima versione rilasciata su GitHub..."
RELEASE_JSON=$(curl -s "https://api.github.com/repos/${REPO}/releases/latest" || true)
TAG_NAME=$(echo "$RELEASE_JSON" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')

if [ -z "$TAG_NAME" ]; then
  TAG_NAME="v0.9.1"
  echo "⚠️  Impossibile determinare ultima release via API. Utilizzo fallback versione $TAG_NAME"
else
  echo "✅ Ultima versione rilevata: $TAG_NAME"
fi

DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${TAG_NAME}/bham-linux-x64.tar.gz"
TMP_DIR=$(mktemp -d)

# 4. Download ed estrazione
echo "⬇️  Download del pacchetto binario da:"
echo "   $DOWNLOAD_URL"
curl -fL "$DOWNLOAD_URL" -o "${TMP_DIR}/bham-linux.tar.gz"

echo "📦 Estrazione archivio..."
tar -xzf "${TMP_DIR}/bham-linux.tar.gz" -C "${TMP_DIR}"

if [ ! -f "${TMP_DIR}/bham" ]; then
  echo "❌ Binario bham non trovato nell'archivio scaricato."
  rm -rf "$TMP_DIR"
  exit 1
fi

# 5. Installazione binario
echo "🚀 Installazione binario in ${INSTALL_DIR}/bham..."
install -m 755 "${TMP_DIR}/bham" "${INSTALL_DIR}/bham"

# 6. Abilitazione permessi seriali dialout
ACTUAL_USER="${SUDO_USER:-$USER}"
if [ -n "$ACTUAL_USER" ] && [ "$ACTUAL_USER" != "root" ]; then
  echo "🔌 Assegnazione permessi seriali RS485 (gruppo dialout) all'utente '$ACTUAL_USER'..."
  usermod -aG dialout "$ACTUAL_USER" || true
fi

# 7. Configurazione servizio systemd (opzionale/disattivato di default per uso da terminale o desktop)
cat << SERVICE_EOF > "${SYSTEMD_DIR}/bham.service"
[Unit]
Description=BHAM – BACS Help Auto Mapper Daemon
After=network.target

[Service]
Type=simple
User=${ACTUAL_USER:-root}
ExecStart=${INSTALL_DIR}/bham
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload || true

# 8. Creazione voce di menu Desktop
if [ -d "$DESKTOP_DIR" ]; then
  cat << DESKTOP_EOF > "${DESKTOP_DIR}/bham.desktop"
[Desktop Entry]
Name=BHAM – BACS Help Auto Mapper
Comment=Industrial Telemetry & Network Discovery Daemon
Exec=${INSTALL_DIR}/bham
Icon=utilities-system-monitor
Terminal=true
Type=Application
Categories=Development;Engineering;Network;
DESKTOP_EOF
  chmod 644 "${DESKTOP_DIR}/bham.desktop"
fi

rm -rf "$TMP_DIR"

echo ""
echo "=========================================================="
echo "  ✅ Installazione di BHAM completata con successo!"
echo "=========================================================="
echo "  Avvio manuale da terminale:"
echo "    bham"
echo ""
echo "  Avvio come servizio di sistema in background (opzionale):"
echo "    sudo systemctl start bham"
echo "    sudo systemctl enable bham"
echo ""
echo "  Dashboard Web: http://localhost:8765"
echo "  Manuale Tecnico & Documentazione: https://www.bacshelp.com"
echo "=========================================================="
