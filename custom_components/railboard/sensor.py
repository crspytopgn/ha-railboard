"""Railboard sensor platform."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import Entity

from .const import (
    DOMAIN,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    CONF_RTT_USERNAME,
    CONF_SHOW_ARRIVALS,
    CONF_MAX_RESULTS,
    CONF_SHOW_PLATFORMS,
    CONF_SHOW_STATUS,
    CONF_SHOW_CALLING_POINTS,
    CONF_SHOW_OPERATOR_BADGE,
    DEFAULT_MAX_RESULTS,
    DEFAULT_SHOW_ARRIVALS,
    DEFAULT_SHOW_PLATFORMS,
    DEFAULT_SHOW_STATUS,
    DEFAULT_SHOW_CALLING_POINTS,
    DEFAULT_SHOW_OPERATOR_BADGE,
)
from .api import RealtimeTrainsClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up Railboard sensor based on a config entry."""
    _LOGGER.info("Setting up Railboard sensors from config entry")
    
    # Get configuration data
    station_code = entry.data[CONF_STATION_CODE]
    station_name = entry.data.get(CONF_STATION_NAME, station_code)
    api_key = entry.data["api_key"]
    rtt_username = entry.data.get(CONF_RTT_USERNAME, f"rttapi_{station_code.lower()}")
    
    # Get options with defaults
    options = entry.options
    show_arrivals = options.get(CONF_SHOW_ARRIVALS, DEFAULT_SHOW_ARRIVALS)
    max_results = options.get(CONF_MAX_RESULTS, DEFAULT_MAX_RESULTS)
    show_platforms = options.get(CONF_SHOW_PLATFORMS, DEFAULT_SHOW_PLATFORMS)
    show_status = options.get(CONF_SHOW_STATUS, DEFAULT_SHOW_STATUS)
    show_calling_points = options.get(CONF_SHOW_CALLING_POINTS, DEFAULT_SHOW_CALLING_POINTS)
    show_operator_badge = options.get(CONF_SHOW_OPERATOR_BADGE, DEFAULT_SHOW_OPERATOR_BADGE)
    
    # Create API client
    client = RealtimeTrainsClient(rtt_username, api_key)
    
    # Create sensors
    sensors = [
        RailboardDeparturesSensor(
            client,
            entry.entry_id,
            station_code,
            station_name,
            max_results,
            show_platforms,
            show_status,
            show_calling_points,
            show_operator_badge,
        )
    ]
    
    if show_arrivals:
        sensors.append(
            RailboardArrivalsSensor(
                client,
                entry.entry_id,
                station_code,
                station_name,
                max_results,
            )
        )
    
    async_add_entities(sensors, True)
    _LOGGER.info(f"Railboard sensors added for {station_name} ({station_code})")


class RailboardDeparturesSensor(Entity):
    """Departures sensor using Realtime Trains API."""
    
    def __init__(
        self,
        client,
        entry_id,
        station_code,
        station_name,
        max_results,
        show_platforms,
        show_status,
        show_calling_points,
        show_operator_badge,
    ):
        """Initialise the sensor."""
        self._client = client
        self._entry_id = entry_id
        self._station_code = station_code
        self._station_name = station_name
        self._max_results = max_results
        self._show_platforms = show_platforms
        self._show_status = show_status
        self._show_calling_points = show_calling_points
        self._show_operator_badge = show_operator_badge
        
        self._attr_name = f"Railboard Departures {station_name}"
        self._attr_unique_id = f"railboard_departures_{station_code.lower()}"
        self._state = None
        self._attr_extra_state_attributes = {}
        
        _LOGGER.info(f"Initialised departures sensor for {station_name} ({station_code})")

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._attr_unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:train-variant"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "departures"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attr_extra_state_attributes

    def update(self):
        """Fetch departures."""
        _LOGGER.debug(f"Updating departures for {self._station_code}")
        
        try:
            departures = self._client.get_departures(self._station_code, self._max_results)
            
            # Separate by network
            nr_departures = [d for d in departures if d.get("network") == "National Rail"]
            lo_departures = [d for d in departures if d.get("network") == "London Overground"]
            
            self._state = len(departures)
            self._attr_extra_state_attributes = {
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
            
            _LOGGER.info(f"Updated {self._station_name}: {len(departures)} total ({len(nr_departures)} NR, {len(lo_departures)} LO)")
            
        except Exception as e:
            _LOGGER.error(f"Error updating departures for {self._station_code}: {e}", exc_info=True)
            self._state = None
            self._attr_extra_state_attributes = {"error": str(e)}

    @property
    def should_poll(self):
        """Enable polling."""
        return True


class RailboardArrivalsSensor(Entity):
    """Arrivals sensor using Realtime Trains API."""
    
    def __init__(self, client, entry_id, station_code, station_name, max_results):
        """Initialise the sensor."""
        self._client = client
        self._entry_id = entry_id
        self._station_code = station_code
        self._station_name = station_name
        self._max_results = max_results
        
        self._attr_name = f"Railboard Arrivals {station_name}"
        self
