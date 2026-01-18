#!/bin/bash
# Script de déploiement vers Home Assistant sur Raspberry Pi
# Usage: ./deploy.sh [--restart]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/custom_components/home_performance"

echo "🚀 Déploiement de Home Performance vers Home Assistant..."

# Synchroniser la version du manifest vers la card JS
VERSION=$(grep '"version"' "$SOURCE_DIR/manifest.json" | sed 's/.*"version": "\([^"]*\)".*/\1/')
echo "📌 Version: $VERSION"
sed -i.bak "s/const CARD_VERSION = \"[^\"]*\"/const CARD_VERSION = \"$VERSION\"/" "$SOURCE_DIR/www/home-performance-card.js"
rm -f "$SOURCE_DIR/www/home-performance-card.js.bak"

# Créer les dossiers si nécessaire
ssh ha "mkdir -p /config/custom_components/home_performance/translations"
ssh ha "mkdir -p /config/custom_components/home_performance/frontend"
ssh ha "mkdir -p /config/custom_components/home_performance/www"

# Copier les fichiers Python et JSON
echo "📦 Copie des fichiers..."
scp "$SOURCE_DIR"/*.py ha:/config/custom_components/home_performance/
scp "$SOURCE_DIR"/*.json ha:/config/custom_components/home_performance/
scp "$SOURCE_DIR"/services.yaml ha:/config/custom_components/home_performance/
scp "$SOURCE_DIR"/translations/*.json ha:/config/custom_components/home_performance/translations/
scp "$SOURCE_DIR"/frontend/__init__.py ha:/config/custom_components/home_performance/frontend/

# Copier la carte Lovelace custom
echo "🎨 Copie de la carte Lovelace..."
scp "$SOURCE_DIR"/www/*.js ha:/config/custom_components/home_performance/www/

echo "✅ Fichiers synchronisés avec succès !"

# Redémarrage optionnel
if [ "$1" == "--restart" ]; then
    echo "🔄 Redémarrage de Home Assistant..."
    ssh ha "ha core restart"
    echo "⏳ Home Assistant redémarre... (1-2 minutes)"
fi

echo ""
echo "📋 Commandes utiles :"
echo "   ssh ha 'ha core logs | grep home_performance'  # Voir les logs"
echo "   ssh ha 'ha core restart'                       # Redémarrer HA"
