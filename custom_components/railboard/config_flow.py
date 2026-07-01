"""Config flow for Railboard integration."""
import logging
import voluptuous as vol
from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .api import RealtimeTrainsClient

_LOGGER = logging.getLogger(__name__)


class RailboardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Railboard."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
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
                return self.async_create_entry(
                    title=user_input.get("station_name", user_input["station_code"]),
                    data=user_input,
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
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "station_code_url": "https://www.nationalrail.co.uk/stations/",
                "api_url": "https://www.realtimetrains.co.uk/about/developer/",
            }
        )

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
            })
        )
