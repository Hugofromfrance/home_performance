"""Constants for Home Performance integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

DOMAIN: Final[str] = "home_performance"


def get_version() -> str:
    """Get version from manifest.json (single source of truth)."""
    manifest_path = Path(__file__).parent / "manifest.json"
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
            return manifest.get("version", "unknown")
    except (FileNotFoundError, json.JSONDecodeError):
        return "unknown"


# Version from manifest.json
VERSION: Final[str] = get_version()

# URL de base pour les ressources frontend
URL_BASE: Final[str] = "/home-performance"

# Liste des modules JavaScript à enregistrer
JSMODULES: Final[list[dict[str, str]]] = [
    {
        "name": "Home Performance Card",
        "filename": "home-performance-card.js",
        "version": VERSION,
    },
]

# Configuration keys
CONF_INDOOR_TEMP_SENSOR = "indoor_temp_sensor"
CONF_OUTDOOR_TEMP_SENSOR = "outdoor_temp_sensor"
CONF_HEATING_ENTITY = "heating_entity"
CONF_HEATER_POWER = "heater_power"  # Puissance déclarée du radiateur en W
CONF_POWER_SENSOR = "power_sensor"  # Capteur de puissance instantanée (optionnel)
CONF_ENERGY_SENSOR = "energy_sensor"  # Compteur d'énergie journalier externe (optionnel)
CONF_ZONE_NAME = "zone_name"
CONF_SURFACE = "surface"  # m²
CONF_VOLUME = "volume"  # m³
CONF_POWER_THRESHOLD = "power_threshold"  # Seuil de puissance pour détection chauffe (W)
CONF_WINDOW_SENSOR = "window_sensor"  # Capteur d'ouverture de fenêtre (optionnel)
CONF_HEAT_SOURCE_TYPE = "heat_source_type"  # Type de source de chaleur

# Heat source types
HEAT_SOURCE_ELECTRIC = "electric"
HEAT_SOURCE_HEATPUMP = "heatpump"
HEAT_SOURCE_GAS = "gas"
HEAT_SOURCE_DISTRICT = "district"

# Heat sources that require an energy sensor (cannot estimate from power)
HEAT_SOURCES_REQUIRING_ENERGY = [HEAT_SOURCE_HEATPUMP, HEAT_SOURCE_GAS, HEAT_SOURCE_DISTRICT]

# Weather settings
CONF_WEATHER_ENTITY = "weather_entity"  # Entité météo pour vent (partagée)
CONF_ROOM_ORIENTATION = "room_orientation"  # Orientation principale de la pièce (N, NE, E, SE, S, SO, O, NO)

# Room orientations
ORIENTATIONS = ["n", "ne", "e", "se", "s", "sw", "w", "nw"]

# Notification settings
CONF_WINDOW_NOTIFICATION_ENABLED = "window_notification_enabled"
CONF_NOTIFY_DEVICE = "notify_device"
CONF_NOTIFICATION_DELAY = "notification_delay"

# Default values
DEFAULT_NOTIFICATION_DELAY = 2  # minutes
DEFAULT_HEAT_SOURCE_TYPE = HEAT_SOURCE_ELECTRIC
DEFAULT_POWER_THRESHOLD = 50  # W - Seuil par défaut pour détecter si le chauffage est actif

# Timing
DEFAULT_SCAN_INTERVAL = 60  # seconds
AGGREGATION_PERIOD_HOURS = 24  # Période d'agrégation pour le calcul de K

# Thresholds
MIN_DELTA_T = 5.0  # ΔT minimum pour calcul fiable (°C)
MIN_HEATING_TIME_HOURS = 0.5  # Temps de chauffe minimum sur la période (30 min)
MIN_DATA_HOURS = 12  # Heures minimum de données pour premier calcul
HISTORY_DAYS = 7  # Nombre de jours pour le calcul stable de K_7d
LONG_TERM_HISTORY_DAYS = 365 * 5  # 5 ans d'historique long terme (1825 jours)

# Sensor types - Thermal
SENSOR_K_COEFFICIENT = "k_coefficient"  # W/°C
SENSOR_K_PER_M2 = "k_per_m2"  # W/(°C·m²)
SENSOR_K_PER_M3 = "k_per_m3"  # W/(°C·m³)
SENSOR_DAILY_ENERGY = "daily_energy"  # kWh
SENSOR_HEATING_TIME = "heating_time"  # heures de chauffe sur 24h
SENSOR_AVG_DELTA_T = "avg_delta_t"  # ΔT moyen

# Binary sensors
BINARY_SENSOR_WINDOW_OPEN = "window_open_detected"
BINARY_SENSOR_DATA_READY = "data_ready"

# Standardized entity_id suffixes (English, for new installations)
# Existing users keep their current entity_id via Entity Registry
SENSOR_ENTITY_SUFFIXES = {
    "k_coefficient": "k_coefficient",
    "k_per_m2": "k_per_m2",
    "k_per_m3": "k_per_m3",
    "daily_energy": "daily_estimated_energy",
    "heating_time": "heating_time_24h",
    "heating_ratio": "heating_ratio_24h",
    "energy_performance": "energy_performance",
    "avg_delta_t": "avg_delta_t_24h",
    "data_hours": "data_hours",
    "analysis_remaining": "analysis_remaining",
    "analysis_progress": "analysis_progress",
    "insulation_rating": "insulation_rating",
    "measured_energy_daily": "measured_energy_daily",
}

BINARY_SENSOR_ENTITY_SUFFIXES = {
    "window_open": "window_open",
    "heating_active": "heating_active",
    "data_ready": "data_ready",
}
