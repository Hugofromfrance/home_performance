# Home Performance

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/hugohardier/home_performance.svg)](https://github.com/hugohardier/home_performance/releases)

Une intégration Home Assistant pour analyser et surveiller les performances thermiques de votre logement.

## ✨ Fonctionnalités principales

- 🎴 **Carte Lovelace intégrée** - Design moderne, prête à l'emploi
- 📊 **Compteur d'énergie mesuré** - Intégration de capteur de puissance (Utility Meter)
- 💾 **Persistance des données** - Conservation après redémarrage
- 🎯 **Performance énergétique** - Comparaison à la moyenne nationale
- ⏱️ **Progression d'analyse** - Suivi en temps réel de la collecte

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

## 📊 Capteurs créés

### Coefficients thermiques

| Capteur | Description |
|---------|-------------|
| **Coefficient K** | Déperdition thermique (W/°C) - plus c'est bas, mieux c'est |
| **K par m²** | Normalisé par surface - comparable entre pièces |
| **K par m³** | Normalisé par volume - meilleur si hauteurs différentes |
| **Note d'isolation** | Qualitative (excellent → très mal isolé) |

### Énergie (estimée - toujours disponible)

| Capteur | Description |
|---------|-------------|
| **Énergie totale (estimée)** | kWh cumulés basés sur puissance déclarée × temps ON |
| **Énergie 24h (estimée)** | kWh sur fenêtre glissante 24h |

### Énergie (mesurée - si capteur de puissance configuré)

| Capteur | Description |
|---------|-------------|
| **Énergie jour (mesurée)** | Compteur kWh avec reset à minuit (Utility Meter) |
| **Énergie totale (mesurée)** | kWh cumulés (compatible Dashboard Énergie HA) |

### Performance & Confort

| Capteur | Description |
|---------|-------------|
| **Performance énergétique** | Comparaison à la moyenne nationale (excellent/standard/à optimiser) |
| **Temps de chauffe (24h)** | Durée de fonctionnement (format: `Xh Ymin`) |
| **Ratio de chauffe** | % du temps où le chauffage est actif |
| **ΔT moyen (24h)** | Écart moyen intérieur/extérieur |

### Statut

| Capteur | Description |
|---------|-------------|
| **Heures de données** | Durée de données collectées (format: `Xh Ymin`) |
| **Temps restant analyse** | Temps avant que les données soient prêtes |
| **Progression analyse** | Pourcentage de complétion (0-100%) |
| **Données prêtes** | Binary sensor indiquant si l'analyse est disponible |
| **Fenêtre ouverte** | Détection par chute rapide de température |

## 🎴 Carte Lovelace Intégrée

L'intégration inclut une **carte custom moderne** prête à l'emploi !

### Installation de la carte

1. Ajouter la ressource Lovelace :
   - **Paramètres → Tableaux de bord → ⋮ → Ressources**
   - URL : `/home_performance/home-performance-card.js`
   - Type : `Module JavaScript`

2. Ajouter la carte dans votre dashboard :

```yaml
type: custom:home-performance-card
zone: Salon
title: Performance Thermique
```

### Options de la carte

| Option | Défaut | Description |
|--------|--------|-------------|
| `zone` | *requis* | Nom exact de votre zone |
| `title` | "Performance Thermique" | Titre affiché |
| `demo` | false | Mode démo avec données fictives |

### Fonctionnalités de la carte

- 📊 **Scores visuels** - Isolation et Performance avec couleurs
- 🌡️ **Températures** - Intérieur/Extérieur en temps réel
- 📈 **Métriques détaillées** - Coefficient K, Énergie, Temps de chauffe
- ⏳ **Progression** - Barre de progression pendant l'analyse initiale
- 🎨 **Design adaptatif** - S'adapte au thème clair/sombre

## 📋 Prérequis

- Home Assistant 2024.1.0 ou plus récent
- Capteur de température intérieure
- Capteur de température extérieure
- Entité climate OU switch contrôlant le chauffage

## ⚙️ Configuration

### Paramètres obligatoires

| Paramètre | Description |
|-----------|-------------|
| Nom de zone | Nom de la pièce (ex: Salon) |
| Capteur T° intérieure | sensor.xxx_temperature |
| Capteur T° extérieure | sensor.xxx_outdoor (partageable entre zones) |
| Entité chauffage | climate.xxx ou switch.xxx |
| Puissance radiateur | Puissance déclarée en Watts |

### Paramètres optionnels

| Paramètre | Description |
|-----------|-------------|
| Surface | m² (pour K/m²) |
| Volume | m³ (pour K/m³ et note d'isolation) |
| Capteur de puissance | sensor.xxx_power en Watts (pour énergie mesurée) |

## 💾 Persistance des données

Les données sont **automatiquement sauvegardées** et restaurées après un redémarrage de Home Assistant :

- ✅ Historique thermique (jusqu'à 48h)
- ✅ Coefficient K calculé
- ✅ Compteurs d'énergie
- ✅ Pas besoin de réattendre 12h après chaque restart !

**Stockage** : `/config/.storage/home_performance.{zone}`

**Fréquence de sauvegarde** : Toutes les 5 minutes + à l'arrêt de HA

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

1. Aller dans **Paramètres → Appareils et services**
2. Cliquer sur **"Ajouter une intégration"**
3. Chercher **"Home Performance"**
4. Suivre les étapes de configuration

**Note** : Les calculs commencent après **12h** de données collectées et nécessitent un ΔT minimum de 5°C pour être fiables.

## 🎨 Exemples Dashboard

Des exemples supplémentaires sont disponibles dans [`examples/dashboard_card.yaml`](examples/dashboard_card.yaml) :

| Option | Dépendances | Description |
|--------|-------------|-------------|
| **Carte custom** | Aucune | Carte intégrée moderne ⭐ |
| **Option 1** | Aucune | Cartes natives HA |
| **Option 2** | Mushroom Cards | Look moderne et épuré |
| **Bonus** | ApexCharts | Graphique historique sur 7 jours |

### Installation des dépendances (optionnel)

Pour les options avancées, installez via HACS :
- [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom)
- [stack-in-card](https://github.com/custom-cards/stack-in-card)
- [ApexCharts Card](https://github.com/RomRider/apexcharts-card)

## 📈 Performance Énergétique

Le capteur de performance compare votre consommation à la moyenne nationale française :

| Niveau | Signification |
|--------|--------------|
| 🟢 **Excellent** | -40% vs moyenne nationale |
| 🟡 **Standard** | Dans la moyenne |
| 🟠 **À optimiser** | Au-dessus de la moyenne |

Seuils basés sur la puissance du radiateur :
- 1000W → Excellent < 4 kWh/jour, Standard < 6 kWh/jour
- 1500W → Excellent < 6 kWh/jour, Standard < 9 kWh/jour
- 2000W → Excellent < 8 kWh/jour, Standard < 12 kWh/jour

## 🗺️ Roadmap

### ✅ Réalisé (v0.1.0)

- [x] Coefficient K (W/°C)
- [x] Normalisation K/m² et K/m³
- [x] Énergie journalière (estimée et mesurée)
- [x] Détection fenêtre ouverte
- [x] Note d'isolation
- [x] Carte Lovelace intégrée
- [x] Persistance des données
- [x] Performance énergétique vs moyenne nationale
- [x] Compteur Utility Meter (reset minuit)

### 🔜 Prochaines fonctionnalités

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
