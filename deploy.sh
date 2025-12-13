#!/bin/bash
# Script de déploiement vers Home Assistant sur Raspberry Pi
# Usage: ./deploy.sh [--restart]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/custom_components/thermal_learning"

echo "🚀 Déploiement de Thermal Learning vers Home Assistant..."

# Créer les dossiers si nécessaire
ssh ha "mkdir -p /config/custom_components/thermal_learning/translations"

# Copier les fichiers Python et JSON
echo "📦 Copie des fichiers..."
scp "$SOURCE_DIR"/*.py ha:/config/custom_components/thermal_learning/
scp "$SOURCE_DIR"/*.json ha:/config/custom_components/thermal_learning/
scp "$SOURCE_DIR"/translations/*.json ha:/config/custom_components/thermal_learning/translations/

echo "✅ Fichiers synchronisés avec succès !"

# Redémarrage optionnel
if [ "$1" == "--restart" ]; then
    echo "🔄 Redémarrage de Home Assistant..."
    ssh ha "ha core restart"
    echo "⏳ Home Assistant redémarre... (1-2 minutes)"
fi

echo ""
echo "📋 Commandes utiles :"
echo "   ssh ha 'ha core logs | grep thermal_learning'  # Voir les logs"
echo "   ssh ha 'ha core restart'                       # Redémarrer HA"
