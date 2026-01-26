"""Railboard integration."""

import logging
from homeassistant.helpers.discovery import load_platform
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

def setup(hass, config):
    """Set up the Railboard integration."""
    _LOGGER.warning("🔥 RAILBOARD SETUP CALLED 🔥")
    load_platform(hass, "sensor", DOMAIN, {}, config)
    return True
