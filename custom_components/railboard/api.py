"""API client for Railboard: National Rail + London Overground."""

import logging
from zeep import Client
from zeep.transports import Transport
import requests

_LOGGER = logging.getLogger(__name__)

from .const import DARWIN_WSDL

# -------------------------------
# National Rail (Darwin) Client
# -------------------------------
class DarwinClient:
    def __init__(self, token: str):
        self.token = token
        session = requests.Session()
        session.headers.update({"Authorization": f"Token {self.token}"})
        transport = Transport(session=session)
        self.client = Client(wsdl=DARWIN_WSDL, transport=transport)

    def get_departures(self, crs: str):
        """Return next departures from Darwin API."""
        try:
            response = self.client.service.GetDepartureBoard(
                numRows=5,
                crs=crs
            )
            departures = []
            for train in getattr(response.trainServices, "service", []):
                departures.append({
                    "network": "National Rail",
                    "destination": train.destination.location[0].locationName,
                    "scheduled": train.std,
                    "expected": getattr(train, "etd", train.std),
                    "status": getattr(train, "serviceType", "Unknown")
                })
            return departures
        except Exception as e:
            _LOGGER.error("Railboard Darwin API error: %s", e)
            return []

# -------------------------------
# London Overground (TfL) Client
# -------------------------------
class TfLClient:
    BASE_URL = "https://api.tfl.gov.uk/StopPoint/{}/Arrivals"

    def get_departures(self, naptan_id: str):
        """Return next Overground departures for a TfL station."""
        try:
            url = self.BASE_URL.format(naptan_id)
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            departures = []
            for train in data:
                if train.get("lineName") == "London Overground":
                    departures.append({
                        "network": "London Overground",
                        "destination": train.get("destinationName"),
                        "scheduled": train.get("scheduledDeparture"),  # may need mapping
                        "expected": train.get("expectedArrival"),
                        "status": train.get("modeName", "Unknown")
                    })
            return departures
        except Exception as e:
            _LOGGER.error("Railboard TfL API error: %s", e)
            return []
