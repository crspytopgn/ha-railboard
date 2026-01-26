"""Darwin API client for Railboard."""

from zeep import Client
from .const import WSDL_URL

class DarwinClient:
    def __init__(self):
        self.client = Client(WSDL_URL)

    def get_departures(self, crs):
        """
        crs = 3-letter station code, e.g. 'KGX' for King’s Cross
        Returns a list of departures with train details.
        """
        try:
            # For now, return dummy structure until we do real auth
            return [
                {"destination": "London", "scheduled": "12:30", "status": "On time"},
                {"destination": "Cambridge", "scheduled": "12:45", "status": "Delayed"},
            ]
        except Exception as e:
            return []
