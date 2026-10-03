#!/usr/bin/env bash
# ==============================================================================
# BHAM – Debian/Ubuntu .deb Package Generator
# Generates bham_<version>_amd64.deb
# ==============================================================================

set -e

VERSION="${1:-0.8.0}"
ARCH="amd64"
PKG_NAME="bham_${VERSION}_${ARCH}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/build_deb/${PKG_NAME}"
BIN_SOURCE="${ROOT_DIR}/dist/bham"

if [ ! -f "$BIN_SOURCE" ]; then
  echo "❌ Binario $BIN_SOURCE non trovato. Eseguire prima: pyinstaller bham.spec"
  exit 1
fi

echo "📦 Creazione struttura pacchetto Debian: ${PKG_NAME}..."
rm -rf "${ROOT_DIR}/build_deb"
mkdir -p "${BUILD_DIR}/DEBIAN"
mkdir -p "${BUILD_DIR}/usr/bin"
mkdir -p "${BUILD_DIR}/etc/systemd/system"
mkdir -p "${BUILD_DIR}/usr/share/applications"
mkdir -p "${BUILD_DIR}/usr/share/doc/bham"

# 1. Copia binario eseguibile
cp "$BIN_SOURCE" "${BUILD_DIR}/usr/bin/bham"
chmod 755 "${BUILD_DIR}/usr/bin/bham"

# 2. File di controllo DEBIAN/control
cat << CONTROL_EOF > "${BUILD_DIR}/DEBIAN/control"
Package: bham
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: libc6 (>= 2.31)
Maintainer: BACS Help <info@bacshelp.it>
Homepage: https://www.bacshelp.com
Description: BACS Help Auto Mapper (BHAM)
 Industrial discovery and diagnostics daemon for Building Automation systems.
 Supports Modbus RTU/TCP, BACnet/IP, KNXnet/IP, ARP L2, and RS485 Zero-TX Sniffing.
CONTROL_EOF

# 3. Script di post-installazione DEBIAN/postinst
cat << 'POSTINST_EOF' > "${BUILD_DIR}/DEBIAN/postinst"
#!/bin/sh
set -e

# Aggiunge l'utente chiamante al gruppo dialout per accesso seriale RS485
if [ -n "$SUDO_USER" ]; then
    usermod -aG dialout "$SUDO_USER" || true
fi

# Ricarica systemd se presente
if [ -d /run/systemd/system ]; then
    systemctl daemon-reload || true
fi

exit 0
POSTINST_EOF
chmod 755 "${BUILD_DIR}/DEBIAN/postinst"

# 4. Servizio systemd
cat << 'SERVICE_EOF' > "${BUILD_DIR}/etc/systemd/system/bham.service"
[Unit]
Description=BHAM – BACS Help Auto Mapper Daemon
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/bham
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE_EOF
chmod 644 "${BUILD_DIR}/etc/systemd/system/bham.service"

# 5. Desktop Entry
cat << 'DESKTOP_EOF' > "${BUILD_DIR}/usr/share/applications/bham.desktop"
[Desktop Entry]
Name=BHAM – BACS Help Auto Mapper
Comment=Industrial Telemetry & Network Discovery Daemon
Exec=/usr/bin/bham
Icon=utilities-system-monitor
Terminal=true
Type=Application
Categories=Development;Engineering;Network;
DESKTOP_EOF
chmod 644 "${BUILD_DIR}/usr/share/applications/bham.desktop"

# 6. Documentazione
cp "${ROOT_DIR}/LICENSE" "${BUILD_DIR}/usr/share/doc/bham/copyright"
cp "${ROOT_DIR}/README.md" "${BUILD_DIR}/usr/share/doc/bham/README.md"
cp "${ROOT_DIR}/MANUALE_UTENTE.md" "${BUILD_DIR}/usr/share/doc/bham/MANUALE_UTENTE.md"

# 7. Compilazione pacchetto .deb
echo "🔨 Compilazione archivio .deb con dpkg-deb..."
dpkg-deb --build --root-owner-group "$BUILD_DIR" "${ROOT_DIR}/${PKG_NAME}.deb"

echo "✅ Pacchetto generato con successo: ${ROOT_DIR}/${PKG_NAME}.deb"
sha256sum "${ROOT_DIR}/${PKG_NAME}.deb" > "${ROOT_DIR}/${PKG_NAME}.deb.sha256"
rm -rf "${ROOT_DIR}/build_deb"
