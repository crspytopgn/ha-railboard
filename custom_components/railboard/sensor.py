from homeassistant.helpers.entity import Entity
import logging
from .api import DarwinClient

_LOGGER = logging.getLogger(__name__)
darwin = DarwinClient()

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
        departures = darwin.get_departures("KGX")
        self._state = len(departures)
        self._attr_extra_state_attributes = {f"{i+1}": dep for i, dep in enumerate(departures)}
