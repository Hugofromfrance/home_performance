"""Constants for Home Performance integration."""
import json
from pathlib import Path

DOMAIN = "home_performance"


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
VERSION = get_version()

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

# Default values
DEFAULT_POWER_THRESHOLD = 50  # W - Seuil par défaut pour détecter si le chauffage est actif

# Timing
DEFAULT_SCAN_INTERVAL = 60  # seconds
AGGREGATION_PERIOD_HOURS = 24  # Période d'agrégation pour le calcul de K

# Thresholds
MIN_DELTA_T = 5.0  # ΔT minimum pour calcul fiable (°C)
MIN_HEATING_TIME_HOURS = 0.5  # Temps de chauffe minimum sur la période (30 min)
MIN_DATA_HOURS = 12  # Heures minimum de données pour premier calcul
HISTORY_DAYS = 7  # Nombre de jours d'historique pour le calcul stable de K

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
