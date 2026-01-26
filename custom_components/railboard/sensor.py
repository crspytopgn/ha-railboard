"""Railboard departure board sensor for Home Assistant."""
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
import logging

from .api import RealtimeTrainsClient

_LOGGER = logging.getLogger(__name__)

# Configuration schema
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required("station_code"): cv.string,
    vol.Optional("rtt_username"): cv.string,
    vol.Optional("station_name"): cv.string,
    vol.Optional("show_arrivals", default=False): cv.boolean,
    vol.Optional("max_results", default=15): cv.positive_int,
    vol.Optional("show_platforms", default=True): cv.boolean,
    vol.Optional("show_status", default=True): cv.boolean,
    vol.Optional("show_calling_points", default=True): cv.boolean,
    vol.Optional("show_operator_badge", default=True): cv.boolean,
})


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Railboard sensor platform."""
    _LOGGER.info("Setting up Railboard sensor platform")
    
    api_key = config.get(CONF_API_KEY)
    username = config.get("rtt_username", f"rttapi_{config.get('station_code').lower()}")
    station_code = config.get("station_code")
    station_name = config.get("station_name", station_code)
    show_arrivals = config.get("show_arrivals")
    max_results = config.get("max_results")
    
    # Display options
    show_platforms = config.get("show_platforms")
    show_status = config.get("show_status")
    show_calling_points = config.get("show_calling_points")
    show_operator_badge = config.get("show_operator_badge")
    
    # Create RTT client
    client = RealtimeTrainsClient(username, api_key)
    
    # Create sensors
    sensors = [
        RailboardDeparturesSensor(
            client, 
            station_code,
            station_name,
            max_results,
            show_platforms,
            show_status,
            show_calling_points,
            show_operator_badge
        )
    ]
    
    if show_arrivals:
        sensors.append(
            RailboardArrivalsSensor(
                client, 
                station_code, 
                station_name,
                max_results
            )
        )
    
    async_add_entities(sensors, True)
    _LOGGER.info(f"Railboard sensors added for {station_name} ({station_code})")


class RailboardDeparturesSensor(Entity):
    """Departures sensor using Realtime Trains API"""
    
    def __init__(self, client, station_code, station_name, max_results, show_platforms, show_status, show_calling_points, show_operator_badge):
        """Initialise the sensor."""
        self._client = client
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
        return self._attr_name

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return "mdi:train-variant"

    @property
    def unit_of_measurement(self):
        return "departures"

    @property
    def extra_state_attributes(self):
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
        return True


class RailboardArrivalsSensor(Entity):
    """Arrivals sensor using Realtime Trains API"""
    
    def __init__(self, client, station_code, station_name, max_results):
        self._client = client
        self._station_code = station_code
        self._station_name = station_name
        self._max_results = max_results
        
        self._attr_name = f"Railboard Arrivals {station_name}"
        self._attr_unique_id = f"railboard_arrivals_{station_code.lower()}"
        self._state = None
        self._attr_extra_state_attributes = {}
        
        _LOGGER.info(f"Initialised arrivals sensor for {station_name} ({station_code})")

    @property
    def name(self):
        return self._attr_name

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return "mdi:train-variant"

    @property
    def unit_of_measurement(self):
        return "arrivals"

    @property
    def extra_state_attributes(self):
        return self._attr_extra_state_attributes

    def update(self):
        """Fetch arrivals."""
        _LOGGER.debug(f"Updating arrivals for {self._station_code}")
        
        try:
            arrivals = self._client.get_arrivals(self._station_code, self._max_results)
            
            nr_arrivals = [a for a in arrivals if a.get("network") == "National Rail"]
            lo_arrivals = [a for a in arrivals if a.get("network") == "London Overground"]
            
            self._state = len(arrivals)
            self._attr_extra_state_attributes = {
                "arrivals": arrivals,
                "station_code": self._station_code,
                "station_name": self._station_name,
                "total_count": len(arrivals),
                "nr_count": len(nr_arrivals),
                "overground_count": len(lo_arrivals),
                "national_rail": nr_arrivals,
                "london_overground": lo_arrivals,
            }
            
            _LOGGER.info(f"Updated {self._station_name} arrivals: {len(arrivals)} total ({len(nr_arrivals)} NR, {len(lo_arrivals)} LO)")
            
        except Exception as e:
            _LOGGER.error(f"Error updating arrivals for {self._station_code}: {e}", exc_info=True)
            self._state = None
            self._attr_extra_state_attributes = {"error": str(e)}

    @property
    def should_poll(self):
        return True
