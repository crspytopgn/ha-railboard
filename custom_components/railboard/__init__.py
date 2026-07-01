"""The Railboard integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RealtimeTrainsClient
from .const import (
    CONF_MAX_RESULTS,
    CONF_RTT_USERNAME,
    CONF_SHOW_ARRIVALS,
    CONF_STATION_CODE,
    DEFAULT_MAX_RESULTS,
    DEFAULT_SHOW_ARRIVALS,
    DOMAIN,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Railboard component from YAML (deprecated)."""
    _LOGGER.info("Railboard integration loaded")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Railboard from a config entry."""
    station_code = entry.data[CONF_STATION_CODE]
    station_name = entry.data.get("station_name", station_code)
    api_key = entry.data["api_key"]
    rtt_username = entry.data.get(CONF_RTT_USERNAME, f"rttapi_{station_code.lower()}")

    _LOGGER.info("Setting up Railboard for %s", station_name)

    client = RealtimeTrainsClient(rtt_username, api_key)

    async def _async_update_data():
        """Fetch the latest departures (and arrivals, if enabled) for this entry."""
        show_arrivals = entry.options.get(CONF_SHOW_ARRIVALS, DEFAULT_SHOW_ARRIVALS)
        max_results = entry.options.get(CONF_MAX_RESULTS, DEFAULT_MAX_RESULTS)

        def _fetch():
            data = {"departures": client.get_departures(station_code, max_results)}
            if show_arrivals:
                data["arrivals"] = client.get_arrivals(station_code, max_results)
            return data

        try:
            return await hass.async_add_executor_job(_fetch)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Realtime Trains API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"railboard_{station_code}",
        update_method=_async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward the setup to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Setup options update listener
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    _LOGGER.info("Unloading Railboard for %s", entry.data.get("station_name", entry.data.get("station_code")))

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
