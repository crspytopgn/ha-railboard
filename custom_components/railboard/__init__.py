"""The Railboard integration."""
import logging
from datetime import datetime, timedelta

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RailboardApiError, RealtimeTrainsClient
from .tfl_api import TflBusClient
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_RUN_DATE,
    ATTR_SERVICE_UID,
    BUS_SCAN_INTERVAL,
    CONF_BUS_ROUTES,
    CONF_BUS_STOP_ID,
    CONF_BUS_STOP_NAME,
    CONF_FILTER_DESTINATION,
    CONF_KIND,
    CONF_MAX_BUS_RESULTS,
    CONF_MAX_RESULTS,
    CONF_RTT_USERNAME,
    CONF_SHOW_ARRIVALS,
    CONF_SHOW_NEXT_TRAIN,
    CONF_STATION_CODE,
    CONF_TFL_APP_KEY,
    CONF_WALKING_TIME,
    DEFAULT_FILTER_DESTINATION,
    DEFAULT_MAX_BUS_RESULTS,
    DEFAULT_MAX_RESULTS,
    DEFAULT_SHOW_ARRIVALS,
    DEFAULT_SHOW_NEXT_TRAIN,
    DEFAULT_WALKING_TIME,
    DOMAIN,
    KIND_BUS,
    KIND_RAIL,
    SCAN_INTERVAL,
    SERVICE_GET_SERVICE_DETAIL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor"]

SERVICE_GET_SERVICE_DETAIL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SERVICE_UID): cv.string,
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_RUN_DATE): cv.string,
    }
)


def _minutes_until(expected: str, now: datetime):
    """Return whole minutes from `now` until the next occurrence of an HH:MM time."""
    if not expected or ":" not in expected:
        return None

    try:
        hour, minute = (int(part) for part in expected.split(":"))
    except ValueError:
        return None

    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate < now - timedelta(hours=12):
        # The service's time has already rolled over past midnight relative to `now`.
        candidate += timedelta(days=1)

    return int((candidate - now).total_seconds() // 60)


def _matches_destination(departure: dict, filter_text: str) -> bool:
    """Return True if a departure matches a configured destination filter (or none is set)."""
    needle = (filter_text or "").strip().lower()
    if not needle:
        return True

    if needle in departure.get("destination", "").lower():
        return True

    return any(needle in point.lower() for point in departure.get("calling_at", []))


def _select_next_train(departures: list, walking_time: int, filter_destination: str, now: datetime):
    """Return the earliest departure that's still catchable and matches the destination filter."""
    for departure in departures:
        minutes = _minutes_until(departure.get("expected"), now)
        if minutes is None or minutes < walking_time:
            continue
        if not _matches_destination(departure, filter_destination):
            continue

        next_train = dict(departure)
        next_train["minutes_until_departure"] = minutes
        return next_train

    return None


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Railboard component from YAML (deprecated)."""
    _LOGGER.info("Railboard integration loaded")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Railboard from a config entry (either a rail station or a TfL bus stop)."""
    if entry.data.get(CONF_KIND, KIND_RAIL) == KIND_BUS:
        await _async_setup_bus_entry(hass, entry)
    else:
        await _async_setup_rail_entry(hass, entry)

    # Forward the setup to the sensor platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Setup options update listener
    entry.async_on_unload(entry.add_update_listener(update_listener))

    _async_register_services(hass)

    return True


async def _async_setup_rail_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a rail station config entry."""
    station_code = entry.data[CONF_STATION_CODE]
    station_name = entry.data.get("station_name", station_code)
    api_key = entry.data["api_key"]
    rtt_username = entry.data.get(CONF_RTT_USERNAME, f"rttapi_{station_code.lower()}")

    _LOGGER.info("Setting up Railboard for %s", station_name)

    client = RealtimeTrainsClient(rtt_username, api_key)

    async def _async_update_data():
        """Fetch the latest departures (and arrivals, if enabled) for this entry."""
        show_arrivals = entry.options.get(CONF_SHOW_ARRIVALS, DEFAULT_SHOW_ARRIVALS)
        show_next_train = entry.options.get(CONF_SHOW_NEXT_TRAIN, DEFAULT_SHOW_NEXT_TRAIN)
        max_results = entry.options.get(CONF_MAX_RESULTS, DEFAULT_MAX_RESULTS)
        walking_time = entry.options.get(CONF_WALKING_TIME, DEFAULT_WALKING_TIME)
        filter_destination = entry.options.get(CONF_FILTER_DESTINATION, DEFAULT_FILTER_DESTINATION)

        def _fetch():
            departures = client.get_departures(station_code, max_results)
            data = {"departures": departures}

            if show_arrivals:
                data["arrivals"] = client.get_arrivals(station_code, max_results)

            if show_next_train:
                data["next_train"] = _select_next_train(
                    departures, walking_time, filter_destination, dt_util.now()
                )

            data["disrupted"] = [
                d for d in departures if d.get("is_cancelled") or d.get("is_delayed")
            ]

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
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
        "kind": KIND_RAIL,
    }


async def _async_setup_bus_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a TfL bus stop config entry."""
    stop_id = entry.data[CONF_BUS_STOP_ID]
    stop_name = entry.data.get(CONF_BUS_STOP_NAME, stop_id)
    routes = entry.data.get(CONF_BUS_ROUTES) or []
    app_key = entry.data.get(CONF_TFL_APP_KEY) or None

    _LOGGER.info("Setting up Railboard bus stop %s", stop_name)

    client = TflBusClient(app_key)

    async def _async_update_data():
        """Fetch the next bus arrivals for this stop."""
        max_results = entry.options.get(CONF_MAX_BUS_RESULTS, DEFAULT_MAX_BUS_RESULTS)

        def _fetch():
            return {"arrivals": client.get_arrivals(stop_id, routes, max_results)}

        try:
            return await hass.async_add_executor_job(_fetch)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with TfL API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"railboard_bus_{stop_id}",
        update_method=_async_update_data,
        update_interval=BUS_SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
        "kind": KIND_BUS,
    }


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    _LOGGER.info(
        "Unloading Railboard entry %s",
        entry.data.get("station_name", entry.data.get(CONF_BUS_STOP_NAME, entry.entry_id)),
    )

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_GET_SERVICE_DETAIL)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_services(hass: HomeAssistant):
    """Register the get_service_detail service, once, the first time any entry sets up."""
    if hass.services.has_service(DOMAIN, SERVICE_GET_SERVICE_DETAIL):
        return

    async def _async_handle_get_service_detail(call: ServiceCall) -> dict:
        """Look up the full calling-point detail for one specific rail service, on demand."""
        entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
        domain_data = hass.data.get(DOMAIN, {})
        rail_entries = {
            key: value for key, value in domain_data.items() if value.get("kind") == KIND_RAIL
        }

        if entry_id is not None:
            entry_data = domain_data.get(entry_id)
            if entry_data is None:
                raise ServiceValidationError(f"Unknown Railboard config entry: {entry_id}")
            if entry_data.get("kind") != KIND_RAIL:
                raise ServiceValidationError("get_service_detail only applies to rail station entries")
        elif len(rail_entries) == 1:
            entry_data = next(iter(rail_entries.values()))
        else:
            raise ServiceValidationError(
                "Multiple Railboard rail stations are configured - specify config_entry_id"
            )

        client = entry_data["client"]
        service_uid = call.data[ATTR_SERVICE_UID]
        run_date = call.data.get(ATTR_RUN_DATE)

        try:
            return await hass.async_add_executor_job(client.get_service_detail, service_uid, run_date)
        except RailboardApiError as err:
            raise ServiceValidationError(str(err)) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_SERVICE_DETAIL,
        _async_handle_get_service_detail,
        schema=SERVICE_GET_SERVICE_DETAIL_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
