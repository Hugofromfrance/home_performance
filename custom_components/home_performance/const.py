"""Constants for Home Performance integration."""

DOMAIN = "home_performance"

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

# Timing
DEFAULT_SCAN_INTERVAL = 60  # seconds
AGGREGATION_PERIOD_HOURS = 24  # Période d'agrégation pour le calcul de K

# Thresholds
MIN_DELTA_T = 5.0  # ΔT minimum pour calcul fiable (°C)
MIN_HEATING_TIME_HOURS = 1.0  # Temps de chauffe minimum sur la période
MIN_DATA_HOURS = 12  # Heures minimum de données pour premier calcul

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
