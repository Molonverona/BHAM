#!/usr/bin/env bash
# ==============================================================================
# BHAM – 1-Command Local Release Trigger
# Usage:
#   ./scripts/release.sh patch   (0.8.0 -> 0.8.1)
#   ./scripts/release.sh minor   (0.8.0 -> 0.9.0)
#   ./scripts/release.sh major   (0.8.0 -> 1.0.0)
# ==============================================================================

set -e

BUMP_TYPE="${1:-patch}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=========================================================="
echo "  🚀 BHAM – Avvio Release Automatica ($BUMP_TYPE)"
echo "=========================================================="

# 1. Verifica modifiche pendenti
if [ -n "$(git status --porcelain)" ]; then
  echo "⚠️  Ci sono file non tracciati o modifiche pendenti."
  echo "   Esegui prima il commit o ripulisci l'albero di lavoro."
  git status -s
  exit 1
fi

# 2. Esecuzione test locali di sicurezza
echo "🧪 Esecuzione test suite di verifica..."
.venv/bin/python3 -W error -m unittest discover -s tests -p "test_*.py"

# 3. Avanzamento versione automatico
OLD_VER=$(python3 scripts/bump_version.py --get)
NEW_VER=$(python3 scripts/bump_version.py "$BUMP_TYPE")

echo "📈 Avanzamento versione: v${OLD_VER} ➔ v${NEW_VER}"

# 4. Commit automatico e Creazione Tag
git add $(python3 scripts/bump_version.py --files)
git commit -m "chore(release): v${NEW_VER}"
git tag -a "v${NEW_VER}" -m "Release v${NEW_VER}"

echo "✅ Commit e Tag 'v${NEW_VER}' creati localmente."
echo ""
echo "Per inviare la release a GitHub e scatenare i build automatici per Windows, Linux e WinGet:"
echo "   git push origin main --tags"
echo "=========================================================="
