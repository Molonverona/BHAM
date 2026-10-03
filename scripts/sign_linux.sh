#!/usr/bin/env bash
# ==============================================================================
# BHAM – Firma Digitale Autonoma per Pacchetti Linux
# Firma crittografica di pacchetti .deb, archivi .tar.gz e SHA256SUMS tramite GPG.
#
# Utilizzo:
#   ./scripts/sign_linux.sh              # Firma con la chiave GPG predefinita
#   ./scripts/sign_linux.sh <KEY_ID>     # Firma con una chiave specifica (Key ID / Email)
# ==============================================================================

set -e

KEY_ID="$1"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=========================================================="
echo "  🔏 BHAM – Firma Digitale Autonoma Linux (GPG)"
echo "=========================================================="

if ! command -v gpg >/dev/null 2>&1; then
  echo "❌ Errore: 'gpg' non è installato. Installa GnuPG con: sudo apt install gnupg"
  exit 1
fi

GPG_OPTS=()
if [ -n "$KEY_ID" ]; then
  echo "🔑 Chiave GPG selezionata: $KEY_ID"
  GPG_OPTS=(-u "$KEY_ID")
else
  echo "🔑 Utilizzo della chiave GPG predefinita del portachiavi locale."
fi

# Cerca artefatti Linux da firmare
ARTIFACTS=()
shopt -s nullglob
for f in bham_*.deb bham-linux-x64.tar.gz bham-source-*.zip; do
  ARTIFACTS+=("$f")
done
shopt -u nullglob

if [ ${#ARTIFACTS[@]} -eq 0 ]; then
  echo "⚠️  Nessun artefatto Linux trovato nella radice del progetto."
  echo "   Genera prima il pacchetto con: ./scripts/package_deb.sh"
  exit 1
fi

echo "📦 Artefatti trovati:"
for a in "${ARTIFACTS[@]}"; do
  echo "   - $a"
done
echo ""

# 1. Genera SHA256SUMS unificato
echo "1️⃣  Generazione tabella checksum SHA256SUMS..."
sha256sum "${ARTIFACTS[@]}" > SHA256SUMS
echo "   ✅ SHA256SUMS generato."

# 2. Firma SHA256SUMS in chiaro (Clear-Sign)
echo "2️⃣  Creazione firma in chiaro SHA256SUMS.asc..."
rm -f SHA256SUMS.asc
gpg "${GPG_OPTS[@]}" --clearsign --armor --output SHA256SUMS.asc SHA256SUMS
echo "   ✅ SHA256SUMS.asc firmato con successo."

# 3. Firma staccata (Detached Signatures) per ciascun file
echo "3️⃣  Generazione firme staccate (.asc)..."
for a in "${ARTIFACTS[@]}"; do
  rm -f "${a}.asc"
  gpg "${GPG_OPTS[@]}" --detach-sign --armor --output "${a}.asc" "$a"
  echo "   ✅ Firmato: ${a}.asc"
done

# 4. Firma interna pacchetto Debian (.deb) se dpkg-sig è disponibile
shopt -s nullglob
DEB_FILES=(bham_*.deb)
shopt -u nullglob

if [ ${#DEB_FILES[@]} -gt 0 ] && command -v dpkg-sig >/dev/null 2>&1; then
  echo "4️⃣  Firma interna pacchetto .deb con dpkg-sig..."
  for deb in "${DEB_FILES[@]}"; do
    if [ -n "$KEY_ID" ]; then
      dpkg-sig -k "$KEY_ID" --sign builder "$deb" || echo "   ⚠️ dpkg-sig non riuscito per $deb (procedo con firma staccata GPG)"
    else
      dpkg-sig --sign builder "$deb" || echo "   ⚠️ dpkg-sig non riuscito per $deb (procedo con firma staccata GPG)"
    fi
  done
  echo "   ✅ Firma dpkg-sig completata."
fi

# 5. Verifica della firma appena creata
echo ""
echo "5️⃣  Verifica integrità firma..."
gpg --verify SHA256SUMS.asc

echo ""
echo "=========================================================="
echo "  🎉 FIRMA DIGITALE LINUX COMPLETATA CON SUCCESSO!"
echo "=========================================================="
echo "Artefatti e firme pronti per il rilascio:"
for a in "${ARTIFACTS[@]}"; do
  echo "  - $a"
  echo "  - ${a}.asc"
done
echo "  - SHA256SUMS"
echo "  - SHA256SUMS.asc"
echo ""
echo "Per verificare la firma su un'altra macchina Linux:"
echo "  gpg --verify SHA256SUMS.asc"
echo "  sha256sum --check SHA256SUMS"
echo "=========================================================="
