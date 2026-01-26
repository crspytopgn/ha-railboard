"""The Railboard integration."""
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "railboard"


def setup(hass, config):
    """Set up the Railboard component."""
    _LOGGER.info("Setting up Railboard integration")
    return True
