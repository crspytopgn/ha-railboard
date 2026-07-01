"""Railboard binary sensor platform."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_SHOW_DISRUPTION_SENSOR,
    CONF_SHOW_NEXT_TRAIN,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    CONF_WALKING_TIME,
    DEFAULT_SHOW_DISRUPTION_SENSOR,
    DEFAULT_SHOW_NEXT_TRAIN,
    DEFAULT_WALKING_TIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Railboard binary sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    station_code = entry.data[CONF_STATION_CODE]
    station_name = entry.data.get(CONF_STATION_NAME, station_code)
    options = entry.options

    entities = []

    if options.get(CONF_SHOW_DISRUPTION_SENSOR, DEFAULT_SHOW_DISRUPTION_SENSOR):
        entities.append(RailboardDisruptionSensor(coordinator, station_code, station_name))

    if options.get(CONF_SHOW_NEXT_TRAIN, DEFAULT_SHOW_NEXT_TRAIN):
        walking_time = options.get(CONF_WALKING_TIME, DEFAULT_WALKING_TIME)
        entities.append(RailboardLeaveNowSensor(coordinator, station_code, station_name, walking_time))

    async_add_entities(entities)


class RailboardDisruptionSensor(CoordinatorEntity):
    """Binary sensor that is on when any upcoming departure is delayed or cancelled."""

    _attr_icon = "mdi:alert"
    _attr_should_poll = False

    def __init__(self, coordinator, station_code, station_name):
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._station_code = station_code
        self._station_name = station_name

        self._attr_name = f"Railboard Disruption {station_name}"
        self._attr_unique_id = f"railboard_disruption_{station_code.lower()}"

    @property
    def _disrupted(self):
        return (self.coordinator.data or {}).get("disrupted", [])

    @property
    def is_on(self):
        """Return True if any departure is currently delayed or cancelled."""
        return len(self._disrupted) > 0

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        disrupted = self._disrupted
        return {
            "station_code": self._station_code,
            "station_name": self._station_name,
            "disrupted_count": len(disrupted),
            "disrupted_services": disrupted,
        }


class RailboardLeaveNowSensor(CoordinatorEntity):
    """Binary sensor that turns on once it's time to leave to catch the next train."""

    _attr_icon = "mdi:shoe-print"
    _attr_should_poll = False

    def __init__(self, coordinator, station_code, station_name, walking_time):
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._station_code = station_code
        self._station_name = station_name
        self._walking_time = walking_time

        self._attr_name = f"Railboard Leave Now {station_name}"
        self._attr_unique_id = f"railboard_leave_now_{station_code.lower()}"

    @property
    def _next_train(self):
        return (self.coordinator.data or {}).get("next_train")

    @property
    def is_on(self):
        """Return True once the next catchable train is due within the walking time."""
        next_train = self._next_train
        if next_train is None:
            return False
        minutes = next_train.get("minutes_until_departure")
        if minutes is None:
            return False
        return minutes <= self._walking_time

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        next_train = self._next_train or {}
        return {
            "station_code": self._station_code,
            "station_name": self._station_name,
            "walking_time": self._walking_time,
            "minutes_until_departure": next_train.get("minutes_until_departure"),
        }
