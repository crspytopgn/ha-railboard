from homeassistant.helpers.entity import Entity
import logging
from .api import DarwinClient, TfLClient

_LOGGER = logging.getLogger("railboard.sensor")

# -------------------------------
# Crystal Palace values
# -------------------------------
DARWIN_API_KEY = "0619b08e-efec-4123-ba4a-e519a0564f86"
NR_CRS_CODE = "CYP"                 # National Rail CRS for Crystal Palace
OVERGROUND_NAPTAN_ID = "940GZZLUCPL"  # TfL Naptan ID for Crystal Palace

darwin = DarwinClient(token=DARWIN_API_KEY)
tfl = TfLClient()


def setup_platform(hass, config, add_entities, discovery_info=None):
    _LOGGER.warning("⚡ Railboard sensor setup_platform called ⚡")
    add_entities([RailboardDeparturesSensor()])


class RailboardDeparturesSensor(Entity):
    """Combined National Rail + London Overground departures sensor."""

    def __init__(self):
        self._attr_name = "Railboard Departures"
        self._state = None
        self._attr_extra_state_attributes = {}

    @property
    def state(self):
        return self._state

    def update(self):
        try:
