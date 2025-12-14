# Home Performance

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/hugohardier/home_performance.svg)](https://github.com/hugohardier/home_performance/releases)

Une intégration Home Assistant pour analyser et surveiller les performances thermiques de votre logement.

## 🎯 Concept

Cette intégration calcule le **coefficient de déperdition thermique K** de chaque pièce en utilisant une approche physique simple :

```
K (W/°C) = Énergie fournie / (ΔT × durée)
         = (Puissance_radiateur × temps_chauffe) / (ΔT_moyen × 24h)
```

**Exemple concret** : Un radiateur de 1000W qui tourne 6h sur 24h pour maintenir 19°C alors qu'il fait 5°C dehors :
- Énergie = 1000W × 6h = 6 kWh
- ΔT = 14°C
- **K = 6000 / (14 × 24) ≈ 18 W/°C**

→ Cette pièce perd 18W par degré d'écart avec l'extérieur.

## 📊 Sensors créés

| Sensor | Description |
|--------|-------------|
| **Coefficient K** | Déperdition thermique (W/°C) - plus c'est bas, mieux c'est |
| **K par m²** | Normalisé par surface - comparable entre pièces |
| **K par m³** | Normalisé par volume - meilleur si hauteurs différentes |
| **Énergie journalière** | kWh consommés sur 24h |
| **Temps de chauffe** | Heures de fonctionnement du radiateur |
| **Ratio de chauffe** | % du temps où le chauffage est actif |
| **ΔT moyen** | Écart moyen intérieur/extérieur |
| **Note d'isolation** | Qualitative (excellent → très mal isolé) |
| **Fenêtre ouverte** | Détection par chute rapide de température |

## 📋 Prérequis

- Home Assistant 2024.1.0 ou plus récent
- Capteur de température intérieure
- Capteur de température extérieure
- Entité climate OU switch contrôlant le chauffage

## ⚙️ Configuration requise

| Paramètre | Obligatoire | Description |
|-----------|-------------|-------------|
| Nom de zone | ✅ | Nom de la pièce (ex: Salon) |
| Capteur T° intérieure | ✅ | sensor.xxx_temperature |
| Capteur T° extérieure | ✅ | sensor.xxx_outdoor (partageable) |
| Entité chauffage | ✅ | climate.xxx ou switch.xxx |
| Puissance radiateur | ✅ | Puissance déclarée en Watts |
| Surface | ❌ | m² (pour K/m²) |
| Volume | ❌ | m³ (pour K/m³ et note d'isolation) |

## 📦 Installation

### HACS (Recommandé)

1. Ouvrir HACS
2. Cliquer sur "Intégrations"
3. Menu ⋮ → "Dépôts personnalisés"
4. Ajouter `https://github.com/hugohardier/home_performance` (catégorie: Integration)
5. Installer "Home Performance"
6. Redémarrer Home Assistant

### Manuel

1. Copier `custom_components/home_performance` dans votre dossier `config/custom_components/`
2. Redémarrer Home Assistant

## 🚀 Utilisation

1. Aller dans Paramètres → Appareils et services
2. Cliquer sur "Ajouter une intégration"
3. Chercher "Home Performance"
4. Suivre les étapes de configuration

**Note** : Les calculs commencent après **12h** de données collectées et nécessitent un ΔT minimum de 5°C pour être fiables.

## 🗺️ Roadmap

### Thermique (v1.0) ✅
- [x] Coefficient K (W/°C)
- [x] Normalisation K/m² et K/m³
- [x] Énergie journalière
- [x] Détection fenêtre ouverte
- [x] Note d'isolation

### Prochaines fonctionnalités
- [ ] Historique de K dans le temps
- [ ] Correction vent/ensoleillement (météo)
- [ ] Module humidité (HR, risque moisissure)
- [ ] Module qualité d'air (CO2)
- [ ] Module confort (PMV/PPD)
- [ ] Comparaison multi-zones
- [ ] Export des données

## 🤝 Contribuer

Les contributions sont les bienvenues ! Ouvrez une issue pour discuter avant de soumettre une PR.

## 📄 Licence

[MIT](LICENSE)
