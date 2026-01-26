from homeassistant.helpers.entity import Entity
import logging
from .api import DarwinClient, TfLClient

_LOGGER = logging.getLogger(__name__)

# -------------------------------
# Initialize clients with your API key and station codes
# -------------------------------
darwin = DarwinClient(token="0619b08e-efec-4123-ba4a-e519a0564f86")
tfl = TfLClient()

# National Rail CRS code for Crystal Palace
NR_CRS_CODE = "CYP"

# TfL Naptan ID for Crystal Palace (Overground)
# You can check TfL API for exact Naptan ID; example placeholder:
OVERGROUND_NAPTAN_ID = "940GZZLUCPL"  # Crystal Palace rail Overground/TfL station

def setup_platform(hass, config, add_entities, discovery_info=None):
    _LOGGER.warning("⚡ Railboard sensor setup_platform called ⚡")
    add_entities([RailboardDeparturesSensor()])

class RailboardDeparturesSensor(Entity):
    def __init__(self):
        self._attr_name = "Railboard Departures"
        self._state = None
        self._attr_extra_state_attributes = {}

    @property
    def state(self):
        return self._state

    def update(self):
        # Fetch National Rail departures
        nr_departures = darwin.get_departures(NR_CRS_CODE)
        # Fetch London Overground departures
        lo_departures = tfl.get_departures(OVERGROUND_NAPTAN_ID)

        all_departures = nr_departures + lo_departures

        # Set number of departures as the state
        self._state = len(all_departures)
        # Add departures as attributes for HA
        self._attr_extra_state_attributes = {
            f"{i+1}": dep for i, dep in enumerate(all_departures)
        }
