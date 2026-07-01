"""Constants for the Railboard integration."""
from datetime import timedelta

DOMAIN = "railboard"

SCAN_INTERVAL = timedelta(minutes=2)

# Configuration
CONF_STATION_CODE = "station_code"
CONF_STATION_NAME = "station_name"
CONF_RTT_USERNAME = "rtt_username"
CONF_SHOW_ARRIVALS = "show_arrivals"
CONF_MAX_RESULTS = "max_results"
CONF_SHOW_PLATFORMS = "show_platforms"
CONF_SHOW_STATUS = "show_status"
CONF_SHOW_CALLING_POINTS = "show_calling_points"
CONF_SHOW_OPERATOR_BADGE = "show_operator_badge"
CONF_SHOW_NEXT_TRAIN = "show_next_train"
CONF_SHOW_DISRUPTION_SENSOR = "show_disruption_sensor"
CONF_WALKING_TIME = "walking_time"
CONF_FILTER_DESTINATION = "filter_destination"

# Defaults
DEFAULT_MAX_RESULTS = 15
DEFAULT_SHOW_ARRIVALS = False
DEFAULT_SHOW_PLATFORMS = True
DEFAULT_SHOW_STATUS = True
DEFAULT_SHOW_CALLING_POINTS = True
DEFAULT_SHOW_OPERATOR_BADGE = True
DEFAULT_SHOW_NEXT_TRAIN = True
DEFAULT_SHOW_DISRUPTION_SENSOR = True
DEFAULT_WALKING_TIME = 0
DEFAULT_FILTER_DESTINATION = ""

# Services
SERVICE_GET_SERVICE_DETAIL = "get_service_detail"
ATTR_SERVICE_UID = "service_uid"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_RUN_DATE = "date"
