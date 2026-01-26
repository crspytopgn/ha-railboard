from homeassistant.helpers.entity import Entity
import logging
from .api import DarwinClient, TfLClient

_LOGGER = logging.getLogger("railboard.sensor")

# -------------------------------
# Crystal Palace station
# -------------------------------
DARWIN_API_KEY = "0619b08e-efec-4123-ba4a-e519a0564f86"
NR_CRS_CODE = "CYP"                   # National Rail CRS
OVERGROUND_NAPTAN_ID = "940GZZLUCPL"  # TfL Naptan ID

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
        """Fetch departures from both networks and update HA sensor."""
        try:
            # National Rail
            nr_departures = darwin.get_departures(NR_CRS_CODE)
            # London Overground
            lo_departures = tfl.get_departures(OVERGROUND_NAPTAN_ID)

            all_departures = nr_departures + lo_departures
            # sort by scheduled time
            all_departures.sort(key=lambda x: x["scheduled"])

            # update sensor state
            self._state = len(all_departures)
            # update attributes
            self._attr_extra_state_attributes = {
                f"{i+1}": dep for i, dep in enumerate(all_departures)
            }

        except Exception as e:
            _LOGGER.error("Error updating Railboard sensor: %s", e)
            self._state = None
            self._attr_extra_state_attributes = {}
