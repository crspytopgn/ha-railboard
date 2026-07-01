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
    CONF_BUS_ALL_ROUTES,
    CONF_BUS_ROUTES,
    CONF_BUS_STOP_ID,
    CONF_BUS_STOP_NAME,
    CONF_FILTER_DESTINATION,
    CONF_JOURNEY_LEGS,
    CONF_JOURNEY_NAME,
    CONF_KIND,
    CONF_MAX_BUS_RESULTS,
    CONF_MAX_RESULTS,
    CONF_RTT_REFRESH_TOKEN,
    CONF_SHOW_ARRIVALS,
    CONF_SHOW_FIRST_LAST_TRAIN,
    CONF_SHOW_NEXT_TRAIN,
    CONF_STATION_CODE,
    CONF_TFL_APP_KEY,
    CONF_TRACKED_DESTINATION,
    CONF_TRACKED_TIME,
    CONF_WALKING_TIME,
    DEFAULT_FILTER_DESTINATION,
    DEFAULT_MAX_BUS_RESULTS,
    DEFAULT_MAX_RESULTS,
    DEFAULT_SHOW_ARRIVALS,
    DEFAULT_SHOW_FIRST_LAST_TRAIN,
    DEFAULT_SHOW_NEXT_TRAIN,
    DEFAULT_TRACKED_DESTINATION,
    DEFAULT_TRACKED_TIME,
    DEFAULT_WALKING_TIME,
    DOMAIN,
    KIND_BUS,
    KIND_JOURNEY,
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


def _select_next_train(departures: list, walking_time: int, now: datetime):
    """Return the earliest departure that's still catchable.

    Destination filtering (if configured) is expected to already have been
    applied server-side via the API's own filterTo parameter - see
    _async_setup_rail_entry - so departures here don't need re-filtering.
    """
    for departure in departures:
        minutes = _minutes_until(departure.get("expected"), now)
        if minutes is None or minutes < walking_time:
            continue

        next_train = dict(departure)
        next_train["minutes_until_departure"] = minutes
        return next_train

    return None


def _select_tracked_service(departures: list, tracked_time: str, tracked_destination: str, now: datetime):
    """Return the departure matching a specific scheduled time (and optional destination).

    Unlike next_train, this pins to one specific recurring service (e.g. "the
    08:03 to Victoria") rather than the earliest catchable one, so a regular
    commuter can follow the same train's live status day to day. If the
    tracked service is cancelled, "fallback_service" is set to the next
    matching departure after it, so there's still something useful to act on.
    """
    needle = (tracked_destination or "").strip().lower()
    candidates = [
        d for d in departures if not needle or needle in d.get("destination", "").lower()
    ]

    tracked = None
    tracked_index = None
    for index, departure in enumerate(candidates):
        if departure.get("scheduled") == tracked_time:
            tracked = dict(departure)
            tracked_index = index
            break

    if tracked is None:
        return None

    tracked["minutes_until_departure"] = _minutes_until(tracked.get("expected"), now)

    tracked["fallback_service"] = None
    if tracked.get("is_cancelled") and tracked_index + 1 < len(candidates):
        fallback = dict(candidates[tracked_index + 1])
        fallback["minutes_until_departure"] = _minutes_until(fallback.get("expected"), now)
        tracked["fallback_service"] = fallback

    return tracked


class _PunctualityTracker:
    """Accumulates a rolling on-time/delay tally for a station's departures.

    Every poll, the current visible departures window is snapshotted by
    service_uid. When a service_uid drops out of that window (i.e. it has now
    departed), its last known status is folded into the running totals for the
    day. This gives a real "how has today gone" stat from data already being
    fetched anyway, without any extra API calls. The tally resets at the start
    of each local day.
    """

    def __init__(self):
        self._day = None
        self._in_flight = {}
        self._on_time = 0
        self._delayed = 0
        self._cancelled = 0
        self._total_delay_minutes = 0

    def update(self, departures: list, today: str) -> dict:
        if today != self._day:
            self._day = today
            self._in_flight = {}
            self._on_time = 0
            self._delayed = 0
            self._cancelled = 0
            self._total_delay_minutes = 0

        current_uids = set()
        for departure in departures:
            uid = departure.get("service_uid")
            if not uid:
                continue
            current_uids.add(uid)
            self._in_flight[uid] = (departure.get("is_cancelled", False), departure.get("delay_minutes") or 0)

        for uid in set(self._in_flight) - current_uids:
            is_cancelled, delay_minutes = self._in_flight.pop(uid)
            if is_cancelled:
                self._cancelled += 1
            elif delay_minutes > 0:
                self._delayed += 1
                self._total_delay_minutes += delay_minutes
            else:
                self._on_time += 1

        return self.stats

    @property
    def stats(self) -> dict:
        total = self._on_time + self._delayed + self._cancelled
        return {
            "total_observed": total,
            "on_time_count": self._on_time,
            "delayed_count": self._delayed,
            "cancelled_count": self._cancelled,
            "on_time_percent": round((self._on_time / total) * 100, 1) if total else None,
            "average_delay_minutes": (
                round(self._total_delay_minutes / self._delayed, 1) if self._delayed else 0
            ),
        }


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Railboard component from YAML (deprecated)."""
    _LOGGER.info("Railboard integration loaded")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Railboard from a config entry (a rail station, a TfL bus stop, or a journey)."""
    kind = entry.data.get(CONF_KIND, KIND_RAIL)
    if kind == KIND_BUS:
        await _async_setup_bus_entry(hass, entry)
    elif kind == KIND_JOURNEY:
        await _async_setup_journey_entry(hass, entry)
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
    refresh_token = entry.data[CONF_RTT_REFRESH_TOKEN]

    _LOGGER.info("Setting up Railboard for %s", station_name)

    client = RealtimeTrainsClient(refresh_token)
    punctuality = _PunctualityTracker()
    first_last_cache = {"day": None, "data": None}

    async def _async_update_data():
        """Fetch the latest departures/arrivals (one call covers both) for this entry."""
        show_next_train = entry.options.get(CONF_SHOW_NEXT_TRAIN, DEFAULT_SHOW_NEXT_TRAIN)
        max_results = entry.options.get(CONF_MAX_RESULTS, DEFAULT_MAX_RESULTS)
        walking_time = entry.options.get(CONF_WALKING_TIME, DEFAULT_WALKING_TIME)
        filter_destination = entry.options.get(CONF_FILTER_DESTINATION, DEFAULT_FILTER_DESTINATION)
        tracked_time = entry.options.get(CONF_TRACKED_TIME, DEFAULT_TRACKED_TIME)
        tracked_destination = entry.options.get(CONF_TRACKED_DESTINATION, DEFAULT_TRACKED_DESTINATION)
        show_first_last_train = entry.options.get(CONF_SHOW_FIRST_LAST_TRAIN, DEFAULT_SHOW_FIRST_LAST_TRAIN)
        now = dt_util.now()
        today = now.strftime("%Y-%m-%d")

        def _fetch():
            board = client.get_board(station_code, max_results)
            departures = board["departures"]
            data = {"departures": departures}

            if entry.options.get(CONF_SHOW_ARRIVALS, DEFAULT_SHOW_ARRIVALS):
                data["arrivals"] = board["arrivals"]

            if show_next_train:
                # Ask the API to filter server-side when a destination is configured
                # (catches genuine "via" stations, not just an exact destination-name
                # match) rather than string-matching client-side.
                next_train_candidates = departures
                if filter_destination:
                    filtered_board = client.get_board(station_code, max_results, filter_to=filter_destination)
                    next_train_candidates = filtered_board["departures"]
                data["next_train"] = _select_next_train(next_train_candidates, walking_time, now)

            if tracked_time:
                data["tracked_service"] = _select_tracked_service(
                    departures, tracked_time, tracked_destination, now
                )

            data["disrupted"] = [
                d for d in departures if d.get("is_cancelled") or d.get("is_delayed")
            ]

            data["punctuality"] = punctuality.update(departures, today)

            if show_first_last_train:
                # First/last train rarely changes intra-day - fetch it once per day
                # rather than on every poll.
                if first_last_cache["day"] != today:
                    first_last_cache["day"] = today
                    first_last_cache["data"] = client.get_first_last_train(station_code)
                data["first_last_train"] = first_last_cache["data"]

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
    all_routes = entry.data.get(CONF_BUS_ALL_ROUTES) or routes
    app_key = entry.data.get(CONF_TFL_APP_KEY) or None

    _LOGGER.info("Setting up Railboard bus stop %s", stop_name)

    client = TflBusClient(app_key)

    # Followed routes if the user picked specific ones, otherwise every route
    # known to serve the stop - either way, checked directly by line id rather
    # than derived from live arrivals, so a fully-suspended route is still
    # reported even if it has no arrivals showing at all.
    disruption_line_ids = sorted({route.strip().lower() for route in (routes or all_routes) if route})

    async def _async_update_data():
        """Fetch the next bus arrivals (and any disruptions) for this stop."""
        max_results = entry.options.get(CONF_MAX_BUS_RESULTS, DEFAULT_MAX_BUS_RESULTS)

        def _fetch():
            return {
                "arrivals": client.get_arrivals(stop_id, routes, max_results),
                "disrupted": client.get_line_status(disruption_line_ids),
            }

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


async def _async_setup_journey_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a journey entry - combines other already-configured rail/bus entries.

    This has no coordinator of its own and makes no API calls: it just reads
    the already-polled data from the referenced entries' own coordinators at
    render time (see RailboardJourneySensor).
    """
    _LOGGER.info("Setting up Railboard journey %s", entry.data.get(CONF_JOURNEY_NAME, entry.entry_id))

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "kind": KIND_JOURNEY,
        "name": entry.data.get(CONF_JOURNEY_NAME, "Journey"),
        "legs": entry.data.get(CONF_JOURNEY_LEGS, []),
    }


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    _LOGGER.info(
        "Unloading Railboard entry %s",
        entry.data.get("station_name", entry.data.get(CONF_BUS_STOP_NAME, entry.data.get(CONF_JOURNEY_NAME, entry.entry_id))),
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
