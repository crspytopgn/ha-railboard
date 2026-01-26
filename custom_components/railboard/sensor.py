from homeassistant.helpers.entity import Entity
from .api import DarwinClient

darwin = DarwinClient()

def setup_platform(hass, config, add_entities, discovery_info=None):
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
        # This is called by HA to refresh the sensor
        departures = darwin.get_departures("KGX")  # example CRS
        self._state = len(departures)  # number of departures
        self._attr_extra_state_attributes = {
            f"{i+1}": dep for i, dep in enumerate(departures)
        }
