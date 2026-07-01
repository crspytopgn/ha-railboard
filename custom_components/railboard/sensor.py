"""Railboard sensor platform."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_BUS_STOP_ID,
    CONF_BUS_STOP_NAME,
    CONF_SHOW_ARRIVALS,
    CONF_SHOW_CALLING_POINTS,
    CONF_SHOW_FIRST_LAST_TRAIN,
    CONF_SHOW_NEXT_TRAIN,
    CONF_SHOW_OPERATOR_BADGE,
    CONF_SHOW_PLATFORMS,
    CONF_SHOW_PUNCTUALITY_SENSOR,
    CONF_SHOW_STATUS,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    CONF_TRACKED_DESTINATION,
    CONF_TRACKED_TIME,
    CONF_WALKING_TIME,
    DEFAULT_SHOW_ARRIVALS,
    DEFAULT_SHOW_CALLING_POINTS,
    DEFAULT_SHOW_FIRST_LAST_TRAIN,
    DEFAULT_SHOW_NEXT_TRAIN,
    DEFAULT_SHOW_OPERATOR_BADGE,
    DEFAULT_SHOW_PLATFORMS,
    DEFAULT_SHOW_PUNCTUALITY_SENSOR,
    DEFAULT_SHOW_STATUS,
    DEFAULT_TRACKED_DESTINATION,
    DEFAULT_TRACKED_TIME,
    DEFAULT_WALKING_TIME,
    DOMAIN,
    KIND_BUS,
    KIND_JOURNEY,
    KIND_RAIL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Railboard sensor based on a config entry."""
    _LOGGER.info("Setting up Railboard sensors from config entry")

    entry_data = hass.data[DOMAIN][entry.entry_id]
    kind = entry_data.get("kind")

    if kind == KIND_JOURNEY:
        name = entry_data.get("name", "Journey")
        legs = entry_data.get("legs", [])
        async_add_entities([RailboardJourneySensor(hass, entry.entry_id, name, legs)])
        _LOGGER.info(f"Railboard journey sensor added for {name}")
        return

    coordinator = entry_data["coordinator"]

    if kind == KIND_BUS:
        stop_id = entry.data[CONF_BUS_STOP_ID]
        stop_name = entry.data.get(CONF_BUS_STOP_NAME, stop_id)
        async_add_entities([RailboardBusStopSensor(coordinator, stop_id, stop_name)])
        _LOGGER.info(f"Railboard bus sensor added for {stop_name} ({stop_id})")
        return

    station_code = entry.data[CONF_STATION_CODE]
    station_name = entry.data.get(CONF_STATION_NAME, station_code)

    # Get options with defaults
    options = entry.options
    show_arrivals = options.get(CONF_SHOW_ARRIVALS, DEFAULT_SHOW_ARRIVALS)
    show_next_train = options.get(CONF_SHOW_NEXT_TRAIN, DEFAULT_SHOW_NEXT_TRAIN)
    show_platforms = options.get(CONF_SHOW_PLATFORMS, DEFAULT_SHOW_PLATFORMS)
    show_status = options.get(CONF_SHOW_STATUS, DEFAULT_SHOW_STATUS)
    show_calling_points = options.get(CONF_SHOW_CALLING_POINTS, DEFAULT_SHOW_CALLING_POINTS)
    show_operator_badge = options.get(CONF_SHOW_OPERATOR_BADGE, DEFAULT_SHOW_OPERATOR_BADGE)
    show_punctuality = options.get(CONF_SHOW_PUNCTUALITY_SENSOR, DEFAULT_SHOW_PUNCTUALITY_SENSOR)
    show_first_last_train = options.get(CONF_SHOW_FIRST_LAST_TRAIN, DEFAULT_SHOW_FIRST_LAST_TRAIN)
    tracked_time = options.get(CONF_TRACKED_TIME, DEFAULT_TRACKED_TIME)
    tracked_destination = options.get(CONF_TRACKED_DESTINATION, DEFAULT_TRACKED_DESTINATION)

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

    if show_next_train:
        sensors.append(RailboardNextTrainSensor(coordinator, station_code, station_name))

    if show_punctuality:
        sensors.append(RailboardPunctualitySensor(coordinator, station_code, station_name))

    if tracked_time:
        sensors.append(
            RailboardTrackedServiceSensor(coordinator, station_code, station_name, tracked_time, tracked_destination)
        )

    if show_first_last_train:
        sensors.append(RailboardFirstTrainSensor(coordinator, station_code, station_name))
        sensors.append(RailboardLastTrainSensor(coordinator, station_code, station_name))

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


class RailboardNextTrainSensor(CoordinatorEntity):
    """Sensor for the next catchable departure (respects walking time / destination filter)."""

    _attr_icon = "mdi:train-clock"
    _attr_unit_of_measurement = "min"
    _attr_should_poll = False

    def __init__(self, coordinator, station_code, station_name):
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._station_code = station_code
        self._station_name = station_name

        self._attr_name = f"Railboard Next Train {station_name}"
        self._attr_unique_id = f"railboard_next_train_{station_code.lower()}"

    @property
    def _next_train(self):
        return (self.coordinator.data or {}).get("next_train")

    @property
    def state(self):
        """Return the number of minutes until the next catchable train departs."""
        next_train = self._next_train
        if next_train is None:
            return None
        return next_train.get("minutes_until_departure")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {
            "station_code": self._station_code,
            "station_name": self._station_name,
        }
        next_train = self._next_train
        if next_train is not None:
            attrs.update(next_train)
        return attrs


class RailboardPunctualitySensor(CoordinatorEntity):
    """Sensor tracking a rolling on-time percentage for the station's departures today."""

    _attr_icon = "mdi:chart-line"
    _attr_unit_of_measurement = "%"
    _attr_should_poll = False

    def __init__(self, coordinator, station_code, station_name):
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._station_code = station_code
        self._station_name = station_name

        self._attr_name = f"Railboard Punctuality {station_name}"
        self._attr_unique_id = f"railboard_punctuality_{station_code.lower()}"

    @property
    def _stats(self):
        return (self.coordinator.data or {}).get("punctuality", {})

    @property
    def state(self):
        """Return today's rolling on-time percentage."""
        return self._stats.get("on_time_percent")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "station_code": self._station_code,
            "station_name": self._station_name,
            **self._stats,
        }


class RailboardTrackedServiceSensor(CoordinatorEntity):
    """Sensor following one specific scheduled service (by time and destination) across polls."""

    _attr_icon = "mdi:train-car"
    _attr_should_poll = False

    def __init__(self, coordinator, station_code, station_name, tracked_time, tracked_destination):
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._station_code = station_code
        self._station_name = station_name
        self._tracked_time = tracked_time
        self._tracked_destination = tracked_destination

        self._attr_name = f"Railboard Tracked Service {station_name}"
        self._attr_unique_id = f"railboard_tracked_{station_code.lower()}"

    @property
    def _tracked(self):
        return (self.coordinator.data or {}).get("tracked_service")

    @property
    def state(self):
        """Return the tracked service's current status (On time/Delayed X min/Cancelled)."""
        tracked = self._tracked
        return tracked.get("status") if tracked else None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {
            "station_code": self._station_code,
            "station_name": self._station_name,
            "tracked_time": self._tracked_time,
            "tracked_destination": self._tracked_destination,
        }
        tracked = self._tracked
        if tracked is not None:
            attrs.update(tracked)
        return attrs


class RailboardFirstTrainSensor(CoordinatorEntity):
    """Sensor for the first scheduled departure of the day."""

    _attr_icon = "mdi:weather-sunset-up"
    _attr_should_poll = False

    def __init__(self, coordinator, station_code, station_name):
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._station_code = station_code
        self._station_name = station_name

        self._attr_name = f"Railboard First Train {station_name}"
        self._attr_unique_id = f"railboard_first_train_{station_code.lower()}"

    @property
    def _train(self):
        return (self.coordinator.data or {}).get("first_last_train", {}).get("first_train")

    @property
    def state(self):
        """Return the scheduled departure time (HH:MM) of the first train."""
        train = self._train
        return train.get("scheduled") if train else None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {"station_code": self._station_code, "station_name": self._station_name}
        train = self._train
        if train is not None:
            attrs.update(train)
        return attrs


class RailboardLastTrainSensor(CoordinatorEntity):
    """Sensor for the last scheduled departure of the day."""

    _attr_icon = "mdi:weather-night"
    _attr_should_poll = False

    def __init__(self, coordinator, station_code, station_name):
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._station_code = station_code
        self._station_name = station_name

        self._attr_name = f"Railboard Last Train {station_name}"
        self._attr_unique_id = f"railboard_last_train_{station_code.lower()}"

    @property
    def _train(self):
        return (self.coordinator.data or {}).get("first_last_train", {}).get("last_train")

    @property
    def state(self):
        """Return the scheduled departure time (HH:MM) of the last train."""
        train = self._train
        return train.get("scheduled") if train else None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {"station_code": self._station_code, "station_name": self._station_name}
        train = self._train
        if train is not None:
            attrs.update(train)
        return attrs


def _select_catchable_bus(arrivals: list, walking_time: int):
    """Return the earliest bus arrival that's still catchable within the given walking time."""
    for arrival in arrivals:
        if arrival.get("minutes", 0) >= walking_time:
            return arrival
    return None


class RailboardJourneySensor(Entity):
    """Sensor combining the next catchable option across several already-configured legs.

    Unlike the other sensors here, this isn't backed by its own
    DataUpdateCoordinator or API calls - it reads live from each referenced
    leg's own already-polled coordinator data at render time, and subscribes
    to each of those coordinators so it updates whenever any leg refreshes.
    """

    _attr_icon = "mdi:transit-connection-variant"
    _attr_unit_of_measurement = "min"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry_id: str, name: str, leg_entry_ids: list):
        """Initialise the sensor."""
        self.hass = hass
        self._leg_entry_ids = leg_entry_ids
        self._unsub_listeners = []

        self._attr_name = f"Railboard Journey {name}"
        self._attr_unique_id = f"railboard_journey_{entry_id}"

    async def async_added_to_hass(self):
        """Subscribe to each leg's coordinator so this entity updates when any of them refresh."""
        for leg_entry_id in self._leg_entry_ids:
            leg_data = self.hass.data.get(DOMAIN, {}).get(leg_entry_id)
            coordinator = leg_data.get("coordinator") if leg_data else None
            if coordinator is not None:
                self._unsub_listeners.append(coordinator.async_add_listener(self._handle_leg_update))

    async def async_will_remove_from_hass(self):
        """Unsubscribe from all leg coordinators."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners = []

    @callback
    def _handle_leg_update(self):
        self.async_write_ha_state()

    @property
    def _leg_options(self):
        """Return the current best (soonest catchable) option for each configured leg."""
        options = []

        for leg_entry_id in self._leg_entry_ids:
            leg_data = self.hass.data.get(DOMAIN, {}).get(leg_entry_id)
            if leg_data is None:
                continue

            kind = leg_data.get("kind")
            coordinator = leg_data.get("coordinator")
            data = coordinator.data if coordinator else None
            if not data:
                continue

            config_entry = self.hass.config_entries.async_get_entry(leg_entry_id)
            label = config_entry.title if config_entry else leg_entry_id

            if kind == KIND_RAIL:
                next_train = data.get("next_train")
                if next_train:
                    options.append(
                        {
                            "leg": label,
                            "kind": "rail",
                            "minutes": next_train.get("minutes_until_departure"),
                            "destination": next_train.get("destination"),
                            "status": next_train.get("status"),
                            "platform": next_train.get("platform"),
                        }
                    )
            elif kind == KIND_BUS:
                walking_time = (
                    config_entry.options.get(CONF_WALKING_TIME, DEFAULT_WALKING_TIME) if config_entry else 0
                )
                next_bus = _select_catchable_bus(data.get("arrivals", []), walking_time)
                if next_bus:
                    options.append(
                        {
                            "leg": label,
                            "kind": "bus",
                            "minutes": next_bus.get("minutes"),
                            "destination": next_bus.get("destination"),
                            "status": None,
                            "line": next_bus.get("line"),
                        }
                    )

        options.sort(key=lambda option: option["minutes"] if option["minutes"] is not None else float("inf"))
        return options

    @property
    def state(self):
        """Return minutes until the soonest catchable option across all legs."""
        options = self._leg_options
        return options[0]["minutes"] if options else None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        options = self._leg_options
        return {
            "options": options,
            "best_leg": options[0]["leg"] if options else None,
        }


class RailboardBusStopSensor(CoordinatorEntity):
    """Sensor for the next few buses at a followed TfL bus stop."""

    _attr_icon = "mdi:bus"
    _attr_unit_of_measurement = "min"
    _attr_should_poll = False

    def __init__(self, coordinator, stop_id, stop_name):
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._stop_id = stop_id
        self._stop_name = stop_name

        self._attr_name = f"Railboard Bus {stop_name}"
        self._attr_unique_id = f"railboard_bus_{stop_id.lower()}"

    @property
    def _arrivals(self):
        return (self.coordinator.data or {}).get("arrivals", [])

    @property
    def state(self):
        """Return the number of minutes until the very next bus."""
        arrivals = self._arrivals
        if not arrivals:
            return None
        return arrivals[0]["minutes"]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        arrivals = self._arrivals
        return {
            "stop_id": self._stop_id,
            "stop_name": self._stop_name,
            "arrivals": arrivals,
            "next_bus_line": arrivals[0]["line"] if arrivals else None,
            "next_bus_destination": arrivals[0]["destination"] if arrivals else None,
        }
