"""Constants for Thermal Learning integration."""

DOMAIN = "thermal_learning"

# Configuration keys
CONF_INDOOR_TEMP_SENSOR = "indoor_temp_sensor"
CONF_OUTDOOR_TEMP_SENSOR = "outdoor_temp_sensor"
CONF_HEATING_ENTITY = "heating_entity"
CONF_POWER_SENSOR = "power_sensor"
CONF_ZONE_NAME = "zone_name"
CONF_SURFACE = "surface"
CONF_VOLUME = "volume"

# Defaults
DEFAULT_SCAN_INTERVAL = 60  # seconds
MIN_LEARNING_DAYS = 7
MIN_SAMPLES_FOR_CONFIDENCE = 100

# Sensor types
SENSOR_THERMAL_LOSS = "thermal_loss_coefficient"
SENSOR_THERMAL_INERTIA = "thermal_inertia"
SENSOR_COOLING_RATE = "cooling_rate"
SENSOR_TIME_TO_TARGET = "time_to_target"
SENSOR_INSULATION_SCORE = "insulation_score"

BINARY_SENSOR_WINDOW_OPEN = "window_open_detected"
BINARY_SENSOR_ANOMALY = "thermal_anomaly"
BINARY_SENSOR_LEARNING_COMPLETE = "learning_complete"