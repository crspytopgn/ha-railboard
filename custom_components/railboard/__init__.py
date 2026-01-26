"""Railboard integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import load_platform
from .const import DOMAIN


def setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Railboard integration."""
    hass.data[DOMAIN] = {}
    load_platform(hass, "sensor", DOMAIN, {}, config)
    return True
