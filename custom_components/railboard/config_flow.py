"""Config flow for Railboard integration."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.core import callback

from .api import RealtimeTrainsClient
from .const import (
    CONF_BUS_ROUTES,
    CONF_BUS_STOP_ID,
    CONF_BUS_STOP_NAME,
    CONF_FILTER_DESTINATION,
    CONF_KIND,
    CONF_MAX_BUS_RESULTS,
    CONF_SHOW_DISRUPTION_SENSOR,
    CONF_SHOW_NEXT_TRAIN,
    CONF_TFL_APP_KEY,
    CONF_WALKING_TIME,
    DEFAULT_FILTER_DESTINATION,
    DEFAULT_MAX_BUS_RESULTS,
    DEFAULT_SHOW_DISRUPTION_SENSOR,
    DEFAULT_SHOW_NEXT_TRAIN,
    DEFAULT_WALKING_TIME,
    DOMAIN,
    KIND_BUS,
    KIND_RAIL,
)
from .tfl_api import TflApiError, TflBusClient

_LOGGER = logging.getLogger(__name__)


class RailboardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Railboard."""

    VERSION = 1

    def __init__(self):
        """Initialise transient state used while setting up a bus stop."""
        self._bus_app_key = None
        self._bus_matches = []
        self._bus_stop_id = None
        self._bus_stop_name = None
        self._bus_available_routes = []

    async def async_step_user(self, user_input=None):
        """Let the user choose whether to add a rail station or a bus stop."""
        return self.async_show_menu(menu_options=["rail", "bus"])

    async def async_step_rail(self, user_input=None):
        """Handle setting up a rail station."""
        errors = {}

        if user_input is not None:
            # Validate the API credentials
            try:
                # Test the API connection
                client = RealtimeTrainsClient(
                    user_input.get("rtt_username", f"rttapi_{user_input['station_code'].lower()}"),
                    user_input["api_key"]
                )

                # Try to fetch departures to validate credentials
                await self.hass.async_add_executor_job(
                    client.get_departures,
                    user_input["station_code"],
                    1
                )

                # Create a unique ID based on station code
                await self.async_set_unique_id(f"railboard_{user_input['station_code'].lower()}")
                self._abort_if_unique_id_configured()

                # If validation succeeds, create the entry
                data = dict(user_input)
                data[CONF_KIND] = KIND_RAIL
                return self.async_create_entry(
                    title=user_input.get("station_name", user_input["station_code"]),
                    data=data,
                )

            except Exception as e:
                _LOGGER.error(f"Error validating Railboard config: {e}")
                errors["base"] = "cannot_connect"

        # Show the configuration form
        data_schema = vol.Schema({
            vol.Required("station_code"): str,
            vol.Optional("station_name"): str,
            vol.Required("api_key"): str,
            vol.Optional("rtt_username"): str,
        })

        return self.async_show_form(
            step_id="rail",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "station_code_url": "https://www.nationalrail.co.uk/stations/",
                "api_url": "https://www.realtimetrains.co.uk/about/developer/",
            }
        )

    async def async_step_bus(self, user_input=None):
        """Ask for an optional TfL API key and a bus stop search query."""
        errors = {}

        if user_input is not None:
            self._bus_app_key = user_input.get("tfl_app_key") or None
            client = TflBusClient(self._bus_app_key)

            try:
                matches = await self.hass.async_add_executor_job(client.search_stops, user_input["query"])
            except TflApiError as err:
                _LOGGER.error("Error searching TfL stops: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if not matches:
                    errors["base"] = "no_stops_found"
                else:
                    self._bus_matches = matches
                    return await self.async_step_bus_select()

        return self.async_show_form(
            step_id="bus",
            data_schema=vol.Schema({
                vol.Required("query"): str,
                vol.Optional("tfl_app_key"): str,
            }),
            errors=errors,
        )

    async def async_step_bus_select(self, user_input=None):
        """Let the user pick their bus stop from the search results."""
        errors = {}
        options = {match["id"]: f"{match['name']} ({match['id']})" for match in self._bus_matches}

        if user_input is not None:
            self._bus_stop_id = user_input["stop_id"]
            self._bus_stop_name = self._bus_matches_name(self._bus_stop_id)

            client = TflBusClient(self._bus_app_key)
            try:
                self._bus_available_routes = await self.hass.async_add_executor_job(
                    client.get_stop_routes, self._bus_stop_id
                )
            except TflApiError as err:
                _LOGGER.error("Error fetching routes for stop: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_bus_routes()

        return self.async_show_form(
            step_id="bus_select",
            data_schema=vol.Schema({vol.Required("stop_id"): vol.In(options)}),
            errors=errors,
        )

    async def async_step_bus_routes(self, user_input=None):
        """Let the user pick which bus routes at the stop to follow (empty = all)."""
        if user_input is not None:
            await self.async_set_unique_id(f"railboard_bus_{self._bus_stop_id.lower()}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Bus: {self._bus_stop_name}",
                data={
                    CONF_KIND: KIND_BUS,
                    CONF_BUS_STOP_ID: self._bus_stop_id,
                    CONF_BUS_STOP_NAME: self._bus_stop_name,
                    CONF_BUS_ROUTES: user_input.get(CONF_BUS_ROUTES, []),
                    CONF_TFL_APP_KEY: self._bus_app_key,
                },
            )

        return self.async_show_form(
            step_id="bus_routes",
            data_schema=vol.Schema({
                vol.Optional(CONF_BUS_ROUTES, default=[]): cv.multi_select(
                    {route: route for route in self._bus_available_routes}
                ),
            }),
            description_placeholders={"stop_name": self._bus_stop_name},
        )

    def _bus_matches_name(self, stop_id: str) -> str:
        for match in self._bus_matches:
            if match["id"] == stop_id:
                return match["name"]
        return stop_id

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return RailboardOptionsFlowHandler(config_entry)


class RailboardOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Railboard options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if self.config_entry.data.get(CONF_KIND, KIND_RAIL) == KIND_BUS:
            return await self._async_step_bus_options(user_input)
        return await self._async_step_rail_options(user_input)

    async def _async_step_rail_options(self, user_input=None):
        """Manage options for a rail station entry."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    "show_arrivals",
                    default=self.config_entry.options.get("show_arrivals", False)
                ): bool,
                vol.Optional(
                    "max_results",
                    default=self.config_entry.options.get("max_results", 15)
                ): vol.All(int, vol.Range(min=1, max=50)),
                vol.Optional(
                    "show_platforms",
                    default=self.config_entry.options.get("show_platforms", True)
                ): bool,
                vol.Optional(
                    "show_status",
                    default=self.config_entry.options.get("show_status", True)
                ): bool,
                vol.Optional(
                    "show_calling_points",
                    default=self.config_entry.options.get("show_calling_points", True)
                ): bool,
                vol.Optional(
                    "show_operator_badge",
                    default=self.config_entry.options.get("show_operator_badge", True)
                ): bool,
                vol.Optional(
                    CONF_SHOW_NEXT_TRAIN,
                    default=self.config_entry.options.get(CONF_SHOW_NEXT_TRAIN, DEFAULT_SHOW_NEXT_TRAIN)
                ): bool,
                vol.Optional(
                    CONF_SHOW_DISRUPTION_SENSOR,
                    default=self.config_entry.options.get(
                        CONF_SHOW_DISRUPTION_SENSOR, DEFAULT_SHOW_DISRUPTION_SENSOR
                    )
                ): bool,
                vol.Optional(
                    CONF_WALKING_TIME,
                    default=self.config_entry.options.get(CONF_WALKING_TIME, DEFAULT_WALKING_TIME)
                ): vol.All(int, vol.Range(min=0, max=60)),
                vol.Optional(
                    CONF_FILTER_DESTINATION,
                    default=self.config_entry.options.get(CONF_FILTER_DESTINATION, DEFAULT_FILTER_DESTINATION)
                ): str,
            })
        )

    async def _async_step_bus_options(self, user_input=None):
        """Manage options for a bus stop entry."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_MAX_BUS_RESULTS,
                    default=self.config_entry.options.get(CONF_MAX_BUS_RESULTS, DEFAULT_MAX_BUS_RESULTS)
                ): vol.All(int, vol.Range(min=1, max=20)),
            })
        )
