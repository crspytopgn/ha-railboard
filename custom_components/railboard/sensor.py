"""Sensor platform for Railboard."""

from homeassistant.helpers.entity import Entity


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Railboard sensor."""
    add_entities([RailboardDummySensor()])


class RailboardDummySensor(Entity):
    """A dummy sensor to test Railboard integration."""

    def __init__(self):
        self._attr_name = "Railboard Test Sensor"
        self._state = "OK"

    @property
    def state(self):
        return self._state
