"""Railboard integration."""

from homeassistant.core import HomeAssistant
from .const import DOMAIN


def setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Railboard integration."""
    hass.data[DOMAIN] = {}
    return True
