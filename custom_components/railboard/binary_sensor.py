"""Railboard binary sensor platform."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_BUS_STOP_ID,
    CONF_BUS_STOP_NAME,
    CONF_SHOW_DISRUPTION_SENSOR,
    CONF_SHOW_NEXT_TRAIN,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    CONF_WALKING_TIME,
    DEFAULT_SHOW_DISRUPTION_SENSOR,
    DEFAULT_SHOW_NEXT_TRAIN,
    DEFAULT_WALKING_TIME,
    DOMAIN,
    KIND_BUS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Railboard binary sensors based on a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    options = entry.options

    if entry_data.get("kind") == KIND_BUS:
        stop_id = entry.data[CONF_BUS_STOP_ID]
        stop_name = entry.data.get(CONF_BUS_STOP_NAME, stop_id)
        entities = []

        if options.get(CONF_SHOW_DISRUPTION_SENSOR, DEFAULT_SHOW_DISRUPTION_SENSOR):
            entities.append(RailboardBusDisruptionSensor(coordinator, stop_id, stop_name))

        walking_time = options.get(CONF_WALKING_TIME, DEFAULT_WALKING_TIME)
        entities.append(RailboardBusLeaveNowSensor(coordinator, stop_id, stop_name, walking_time))

        async_add_entities(entities)
        return

    station_code = entry.data[CONF_STATION_CODE]
    station_name = entry.data.get(CONF_STATION_NAME, station_code)

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


class RailboardBusDisruptionSensor(CoordinatorEntity):
    """Binary sensor that is on when any followed bus route has a reported disruption."""

    _attr_icon = "mdi:alert"
    _attr_should_poll = False

    def __init__(self, coordinator, stop_id, stop_name):
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._stop_id = stop_id
        self._stop_name = stop_name

        self._attr_name = f"Railboard Bus Disruption {stop_name}"
        self._attr_unique_id = f"railboard_bus_disruption_{stop_id.lower()}"

    @property
    def _disrupted(self):
        return (self.coordinator.data or {}).get("disrupted", [])

    @property
    def is_on(self):
        """Return True if any followed route currently has a reported disruption."""
        return len(self._disrupted) > 0

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        disrupted = self._disrupted
        return {
            "stop_id": self._stop_id,
            "stop_name": self._stop_name,
            "disrupted_count": len(disrupted),
            "disrupted_lines": disrupted,
        }


class RailboardBusLeaveNowSensor(CoordinatorEntity):
    """Binary sensor that turns on once it's time to leave to catch the next bus."""

    _attr_icon = "mdi:shoe-print"
    _attr_should_poll = False

    def __init__(self, coordinator, stop_id, stop_name, walking_time):
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._stop_id = stop_id
        self._stop_name = stop_name
        self._walking_time = walking_time

        self._attr_name = f"Railboard Bus Leave Now {stop_name}"
        self._attr_unique_id = f"railboard_bus_leave_now_{stop_id.lower()}"

    @property
    def _next_bus(self):
        arrivals = (self.coordinator.data or {}).get("arrivals", [])
        return arrivals[0] if arrivals else None

    @property
    def is_on(self):
        """Return True once the next bus is due within the walking time."""
        next_bus = self._next_bus
        if next_bus is None:
            return False
        return next_bus["minutes"] <= self._walking_time

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        next_bus = self._next_bus or {}
        return {
            "stop_id": self._stop_id,
            "stop_name": self._stop_name,
            "walking_time": self._walking_time,
            "minutes_until_arrival": next_bus.get("minutes"),
        }
