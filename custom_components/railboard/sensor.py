"""Railboard sensor platform."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_SHOW_ARRIVALS,
    CONF_SHOW_CALLING_POINTS,
    CONF_SHOW_OPERATOR_BADGE,
    CONF_SHOW_PLATFORMS,
    CONF_SHOW_STATUS,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    DEFAULT_SHOW_ARRIVALS,
    DEFAULT_SHOW_CALLING_POINTS,
    DEFAULT_SHOW_OPERATOR_BADGE,
    DEFAULT_SHOW_PLATFORMS,
    DEFAULT_SHOW_STATUS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Railboard sensor based on a config entry."""
    _LOGGER.info("Setting up Railboard sensors from config entry")

    coordinator = hass.data[DOMAIN][entry.entry_id]

    station_code = entry.data[CONF_STATION_CODE]
    station_name = entry.data.get(CONF_STATION_NAME, station_code)

    # Get options with defaults
    options = entry.options
    show_arrivals = options.get(CONF_SHOW_ARRIVALS, DEFAULT_SHOW_ARRIVALS)
    show_platforms = options.get(CONF_SHOW_PLATFORMS, DEFAULT_SHOW_PLATFORMS)
    show_status = options.get(CONF_SHOW_STATUS, DEFAULT_SHOW_STATUS)
    show_calling_points = options.get(CONF_SHOW_CALLING_POINTS, DEFAULT_SHOW_CALLING_POINTS)
    show_operator_badge = options.get(CONF_SHOW_OPERATOR_BADGE, DEFAULT_SHOW_OPERATOR_BADGE)

    # Create sensors
    sensors = [
        RailboardDeparturesSensor(
            coordinator,
            station_code,
            station_name,
            show_platforms,
            show_status,
            show_calling_points,
            show_operator_badge,
        )
    ]

    if show_arrivals:
        sensors.append(RailboardArrivalsSensor(coordinator, station_code, station_name))

    async_add_entities(sensors)
    _LOGGER.info(f"Railboard sensors added for {station_name} ({station_code})")


class RailboardDeparturesSensor(CoordinatorEntity):
    """Departures sensor using Realtime Trains API."""

    _attr_icon = "mdi:train-variant"
    _attr_unit_of_measurement = "departures"
    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        station_code,
        station_name,
        show_platforms,
        show_status,
        show_calling_points,
        show_operator_badge,
    ):
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._station_code = station_code
        self._station_name = station_name
        self._show_platforms = show_platforms
        self._show_status = show_status
        self._show_calling_points = show_calling_points
        self._show_operator_badge = show_operator_badge

        self._attr_name = f"Railboard Departures {station_name}"
        self._attr_unique_id = f"railboard_departures_{station_code.lower()}"

    @property
    def state(self):
        """Return the number of departures."""
        return len(self._departures)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        departures = self._departures
        nr_departures = [d for d in departures if d.get("network") == "National Rail"]
        lo_departures = [d for d in departures if d.get("network") == "London Overground"]

        return {
            "departures": departures,
            "station_code": self._station_code,
            "station_name": self._station_name,
            "total_count": len(departures),
            "nr_count": len(nr_departures),
            "overground_count": len(lo_departures),
            "national_rail": nr_departures,
            "london_overground": lo_departures,
            # Display options
            "show_platforms": self._show_platforms,
            "show_status": self._show_status,
            "show_calling_points": self._show_calling_points,
            "show_operator_badge": self._show_operator_badge,
        }

    @property
    def _departures(self):
        return (self.coordinator.data or {}).get("departures", [])


class RailboardArrivalsSensor(CoordinatorEntity):
    """Arrivals sensor using Realtime Trains API."""

    _attr_icon = "mdi:train-variant"
    _attr_unit_of_measurement = "arrivals"
    _attr_should_poll = False

    def __init__(self, coordinator, station_code, station_name):
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._station_code = station_code
        self._station_name = station_name

        self._attr_name = f"Railboard Arrivals {station_name}"
        self._attr_unique_id = f"railboard_arrivals_{station_code.lower()}"

    @property
    def state(self):
        """Return the number of arrivals."""
        return len(self._arrivals)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        arrivals = self._arrivals
        nr_arrivals = [a for a in arrivals if a.get("network") == "National Rail"]
        lo_arrivals = [a for a in arrivals if a.get("network") == "London Overground"]

        return {
            "arrivals": arrivals,
            "station_code": self._station_code,
            "station_name": self._station_name,
            "total_count": len(arrivals),
            "nr_count": len(nr_arrivals),
            "overground_count": len(lo_arrivals),
            "national_rail": nr_arrivals,
            "london_overground": lo_arrivals,
        }

    @property
    def _arrivals(self):
        return (self.coordinator.data or {}).get("arrivals", [])
