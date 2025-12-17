# Home Performance

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/Hugofromfrance/home_performance.svg)](https://github.com/Hugofromfrance/home_performance/releases)

Une intégration Home Assistant pour analyser et surveiller les performances thermiques de votre logement.

## 🤔 Pourquoi Home Performance ?

Vous chauffez à l'électrique et vous vous demandez :
- **"Ma pièce est-elle bien isolée ?"** → Coefficient K mesuré
- **"Combien je consomme vraiment ?"** → Énergie journalière
- **"Ai-je oublié de fermer une fenêtre ?"** → Détection automatique
- **"Quelle pièce coûte le plus cher ?"** → Comparaison multi-zones

**Home Performance** répond à ces questions en analysant vos données de chauffage **réelles**, sans calcul théorique.

### 💡 Cas d'usage

| Situation | Ce que Home Performance vous apporte |
|-----------|--------------------------------------|
| Achat/Location | Vérifier la performance thermique réelle (vs le DPE théorique) |
| Travaux d'isolation | Mesurer l'amélioration avant/après |
| Optimisation facture | Identifier les pièces énergivores |
| Diagnostic | Détecter fenêtres ouvertes, ponts thermiques |
| Comparaison | Comparer vos pièces entre elles (K/m²) |

## ✨ Fonctionnalités principales

- 🏠 **Multi-zones** - Gérez toutes vos pièces depuis une seule intégration
- 🎴 **Carte Lovelace intégrée** - Design moderne, prête à l'emploi
- 📊 **Compteur d'énergie mesuré** - Intégration de capteur de puissance (Utility Meter)
- 💾 **Persistance des données** - Conservation après redémarrage
- 🎯 **Performance énergétique** - Comparaison à la moyenne nationale
- ⚡ **Architecture event-driven** - Détection instantanée (chauffe, fenêtres)
- 🪟 **Détection fenêtre ouverte** - Alerte temps réel sur chute de température

## 🔌 Compatibilité matérielle

**L'intégration est 100% agnostique du matériel !** Elle fonctionne avec tout ce qui expose des entités Home Assistant standard.

### Minimum requis

| Besoin | Exemples compatibles |
|--------|---------------------|
| Capteur T° intérieure | Aqara, Sonoff SNZB-02, Xiaomi, Netatmo, Ecobee, Shelly H&T, ESPHome... |
| Capteur T° extérieure | Station météo locale, Météo-France, OpenWeatherMap, Netatmo Outdoor... |
| Entité chauffage | Tout `climate.*`, `switch.*` ou `input_boolean.*` |

### Optionnel (recommandé)

| Capteur | Exemples | Avantage |
|---------|----------|----------|
| Puissance instantanée | Shelly Plug S, TP-Link, Tuya, Sonoff POW, NodOn | Temps de chauffe précis |
| Compteur d'énergie | Utility Meter HA, compteur natif | Énergie mesurée vs estimée |

### Types de chauffage supportés

| Type | Compatible ? | Notes |
|------|--------------|-------|
| Radiateur + prise connectée | ✅ | Idéal avec mesure de puissance |
| Radiateur + fil pilote | ✅ | NodOn, Qubino, etc. |
| Convecteur avec thermostat | ✅ | Via switch ou climate |
| Pompe à chaleur / Clim | ✅ | Via climate entity |
| Plancher chauffant électrique | ✅ | Avec capteur de puissance |
| Chauffage central gaz/fioul | ⚠️ | Possible mais moins précis (pas de mesure puissance individuelle) |

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

### Approche empirique vs théorique

Cette intégration utilise une **mesure empirique** des performances thermiques, contrairement aux méthodes théoriques :

| | Approche théorique (DPE, RT2012...) | Approche empirique (Home Performance) |
|--|-------------------------------------|---------------------------------------|
| **Méthode** | Calcul basé sur les caractéristiques des matériaux (coefficients U, R) | Observation des données réelles de chauffage |
| **Données** | Specs fabricant, normes, hypothèses | Énergie consommée, températures mesurées |
| **Inclut** | Ce qui est documenté | **Tout** : ponts thermiques, infiltrations, défauts de pose... |
| **Précision** | Théorique (peut différer du réel) | Reflète la performance réelle in-situ |

> **Exemple** : Une fenêtre certifiée Uw=1,1 W/(m²·K) peut en réalité avoir des performances dégradées si mal posée ou avec des joints usés. La mesure empirique capture ces imperfections.

#### Différence avec les coefficients U/Uw/Ug

Les coefficients **U** (anciennement "K" dans la norme) mesurent la transmission thermique d'une **paroi spécifique** (fenêtre, mur) en W/(m²·K). Ils sont mesurés en laboratoire et permettent de comparer des produits.

Le **coefficient K** de Home Performance mesure les **déperditions globales** d'une pièce entière en W/°C. C'est équivalent au coefficient **G** (ou GV) utilisé en thermique du bâtiment, mais mesuré empiriquement plutôt que calculé.

## 📊 Capteurs créés (par zone)

### Coefficients thermiques

| Capteur | Description |
|---------|-------------|
| **Coefficient K** | Déperdition thermique (W/°C) - plus c'est bas, mieux c'est |
| **K par m²** | Normalisé par surface - comparable entre pièces |
| **K par m³** | Normalisé par volume - meilleur si hauteurs différentes |
| **Note d'isolation** | Intelligente : calculée, déduite, ou conservée selon la saison |

### 🎯 Note d'isolation intelligente

La note d'isolation s'adapte automatiquement à toutes les situations :

| Situation | Affichage | Description |
|-----------|-----------|-------------|
| K calculé | **A à G** | Note basée sur le coefficient K/m³ |
| Peu de chauffe + T° stable | **🏆 Excellente (déduite)** | Isolation excellente déduite automatiquement |
| Mode été (T° ext > T° int) | **☀️ Mode été** | Mesure impossible + dernier K conservé |
| Hors saison (ΔT < 5°C) | **🌤️ Hors saison** | ΔT insuffisant + dernier K conservé |
| Collecte en cours | **En attente** | < 12h de données |

#### Isolation déduite automatiquement 🏆

Si après **24h** d'observation :
- Le ΔT est significatif (≥ 5°C)
- Le radiateur a très peu chauffé (< 30 min)
- La température intérieure est restée **stable** (variation < 2°C)

→ L'intégration déduit automatiquement que l'isolation est **excellente** !

> **Logique** : Si la pièce maintient sa température sans chauffer alors qu'il fait froid dehors, c'est que les déperditions sont très faibles.

#### Conservation du dernier K valide

En été ou hors saison de chauffe, l'intégration **conserve le dernier coefficient K calculé** et l'affiche avec le message de saison approprié. Vous gardez ainsi une référence utile toute l'année.

### Énergie journalière

| Capteur | Description |
|---------|-------------|
| **Énergie 24h (estimée)** | kWh sur fenêtre glissante 24h (puissance déclarée × temps ON) |
| **Énergie jour (mesurée)** | Compteur kWh journalier réel (si capteur de puissance ou compteur externe configuré) |

> **Note** : L'énergie mesurée est prioritaire sur l'estimée dans la carte. L'attribut `source` indique l'origine : `external` (compteur HA) ou `integrated` (calcul depuis capteur de puissance).

### Performance & Confort

| Capteur | Description |
|---------|-------------|
| **Performance énergétique** | Comparaison à la moyenne nationale (excellent/standard/à optimiser) |
| **Temps de chauffe (24h)** | Durée de fonctionnement (format: `Xh Ymin`) |
| **Ratio de chauffe** | % du temps où le chauffage est actif |
| **ΔT moyen (24h)** | Écart moyen intérieur/extérieur |

L'attribut `source` sur Temps/Ratio indique : `measured` (via power sensor > 50W) ou `estimated` (via état switch).

### Statut

| Capteur | Description |
|---------|-------------|
| **Heures de données** | Durée de données collectées (format: `Xh Ymin`) |
| **Temps restant analyse** | Temps avant que les données soient prêtes |
| **Progression analyse** | Pourcentage de complétion (0-100%) |
| **Données prêtes** | Binary sensor indiquant si l'analyse est disponible |
| **Fenêtre ouverte** | Détection par chute rapide de température |

## 🏠 Multi-zones

Gérez toutes vos pièces facilement !

### Ajouter des zones

1. **Paramètres → Appareils et services**
2. Cliquer sur **"+ Ajouter une intégration"**
3. Chercher **"Home Performance"**
4. Configurer la nouvelle zone

Chaque zone apparaît comme une entrée séparée, toutes regroupées sous "Home Performance" :

```
Home Performance - Chambre Flavien
Home Performance - Salon
Home Performance - Bureau
```

### Gérer une zone

Dans la liste des intégrations, cliquez sur **Options** (⚙️) de la zone à modifier pour :
- Modifier les paramètres (puissance, surface, capteurs...)
- Supprimer la zone

Chaque zone a ses **propres capteurs** et sa **propre carte Lovelace**.

## 🎴 Carte Lovelace Intégrée

L'intégration inclut une **carte custom moderne** prête à l'emploi !

### Installation de la carte

**La ressource Lovelace est automatiquement enregistrée** lors de l'installation de l'intégration (mode storage par défaut de HA).

Ajoutez simplement une carte par zone dans votre dashboard :

```yaml
type: custom:home-performance-card
zone: Salon
title: Performance Salon
```

```yaml
type: custom:home-performance-card
zone: Chambre
title: Performance Chambre
```

<details>
<summary>📝 Mode YAML (si la ressource n'est pas auto-détectée)</summary>

Si vous utilisez un dashboard en mode YAML, ajoutez manuellement la ressource :
- **Paramètres → Tableaux de bord → ⋮ → Ressources**
- URL : `/home_performance/home-performance-card.js`
- Type : `Module JavaScript`

</details>

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
- Capteur de température intérieure (par zone)
- Capteur de température extérieure (partageable entre zones)
- Entité climate OU switch contrôlant le chauffage (par zone)

## ⚙️ Configuration

### Paramètres obligatoires (par zone)

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
| Capteur de puissance | sensor.xxx_power en Watts (pour énergie + détection chauffe précise) |
| Compteur d'énergie externe | sensor.xxx_energy (votre propre Utility Meter HA) |

> **Notes** :
> - Si vous fournissez un compteur d'énergie externe ET un capteur de puissance, le compteur externe est utilisé en priorité pour l'énergie.
> - Le capteur de puissance permet aussi une **détection précise de la chauffe** (power > 50W), idéal pour les radiateurs avec thermostat interne ou fil pilote.
> - Les options sont **modifiables après coup** et l'intégration se recharge automatiquement.

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
4. Ajouter `https://github.com/Hugofromfrance/home_performance` (catégorie: Integration)
5. Installer "Home Performance"
6. Redémarrer Home Assistant

### Manuel

1. Copier `custom_components/home_performance` dans votre dossier `config/custom_components/`
2. Redémarrer Home Assistant

## 🚀 Utilisation

### Première configuration

1. Aller dans **Paramètres → Appareils et services**
2. Cliquer sur **"Ajouter une intégration"**
3. Chercher **"Home Performance"**
4. Configurer votre première zone

### Ajouter des pièces

1. Aller dans **Paramètres → Appareils et services**
2. Cliquer sur **"+ Ajouter une intégration"**
3. Chercher **"Home Performance"**
4. Configurer la nouvelle zone

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

### Formule de calcul

Les seuils sont calculés dynamiquement selon la puissance du radiateur :

```
Excellent   : < (Puissance_W / 1000) × 4 kWh/jour
Standard    : < (Puissance_W / 1000) × 6 kWh/jour
À optimiser : au-delà
```

### Tableau des seuils par puissance

| Puissance | 🟢 Excellent | 🟡 Standard | 🟠 À optimiser |
|-----------|--------------|-------------|----------------|
| 500W      | < 2.0 kWh    | < 3.0 kWh   | > 3.0 kWh      |
| 750W      | < 3.0 kWh    | < 4.5 kWh   | > 4.5 kWh      |
| 1000W     | < 4.0 kWh    | < 6.0 kWh   | > 6.0 kWh      |
| 1200W     | < 4.8 kWh    | < 7.2 kWh   | > 7.2 kWh      |
| 1500W     | < 6.0 kWh    | < 9.0 kWh   | > 9.0 kWh      |
| 1800W     | < 7.2 kWh    | < 10.8 kWh  | > 10.8 kWh     |
| 2000W     | < 8.0 kWh    | < 12.0 kWh  | > 12.0 kWh     |
| 2500W     | < 10.0 kWh   | < 15.0 kWh  | > 15.0 kWh     |
| 3000W     | < 12.0 kWh   | < 18.0 kWh  | > 18.0 kWh     |

> **Note** : Ces seuils sont calculés automatiquement pour **toute puissance** saisie. Les valeurs ci-dessus correspondent aux puissances de radiateurs les plus courantes.

## 🗺️ Roadmap

### ✅ Réalisé (v1.0.0)

- [x] Coefficient K (W/°C) - déperdition thermique empirique
- [x] Normalisation K/m² et K/m³
- [x] Note d'isolation intelligente (calculée, déduite, ou conservée)
- [x] Gestion des saisons (été, hors-saison, saison de chauffe)
- [x] Isolation excellente déduite automatiquement (peu de chauffe + T° stable)
- [x] Conservation du dernier K valide (hors saison)
- [x] Énergie journalière (estimée et mesurée)
- [x] Support compteur d'énergie externe HA
- [x] Détection chauffe précise via power sensor (event-driven)
- [x] Détection fenêtre ouverte temps réel (event-driven)
- [x] Carte Lovelace intégrée (auto-enregistrée)
- [x] Persistance des données
- [x] Performance énergétique vs moyenne nationale
- [x] Compteur Utility Meter (reset minuit-minuit)
- [x] Options modifiables avec rechargement auto
- [x] Multi-zones (ajouter/supprimer des pièces)
- [x] Architecture event-driven (réactivité instantanée)

### 🔜 v1.1 - Visualisation

- [ ] Graphiques historiques du coefficient K (ApexCharts)
- [ ] Comparaison multi-zones dans une seule carte
- [ ] Évolution des performances dans le temps

### 🔮 v1.2 - Alertes & Notifications

- [ ] Notifications fenêtre ouverte (push, TTS)
- [ ] Alertes mauvaise isolation détectée
- [ ] Rapport hebdomadaire de consommation

### 💡 Idées futures

- [ ] Correction météo (vent, ensoleillement)
- [ ] Module humidité (HR, risque moisissure)
- [ ] Module qualité d'air (CO2)
- [ ] Module confort thermique (PMV/PPD)
- [ ] Export des données (CSV, InfluxDB)
- [ ] Intégration Energy Dashboard native HA
- [ ] Détection automatique des radiateurs
- [ ] Mode "diagnostic isolation" guidé

## 🤝 Contribuer

Les contributions sont les bienvenues ! Ouvrez une issue pour discuter avant de soumettre une PR.

## 📄 Licence

[MIT](LICENSE)
