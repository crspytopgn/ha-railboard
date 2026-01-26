"""Railboard API clients: Python 3.11-safe."""

import logging
import requests

_LOGGER = logging.getLogger("railboard.api")


# -------------------------------
# National Rail Darwin client
# -------------------------------
class DarwinClient:
    def __init__(self, token: str):
        self.token = token
        self.client = None  # Will initialize lazily

    def get_departures(self, crs: str, num_rows: int = 5):
        if self.client is None:
            try:
                from zeep import Client
                from zeep.transports import Transport

                session = requests.Session()
                session.headers.update({"Authorization": f"Token {self.token}"})
                transport = Transport(session=session)
                self.client = Client(
                    wsdl="https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl/ldb3.wsdl",
                    transport=transport,
                )
            except ImportError as e:
                _LOGGER.error("Zeep import failed: %s", e)
                return []

        try:
            response = self.client.service.GetDepartureBoard(numRows=num_rows, crs=crs)
            services = getattr(response.trainServices, "service", [])
            departures = []
            for train in services:
                departures.append({
                    "network": "National Rail",
                    "destination": train.destination.location[0].locationName,
                    "scheduled": train.std,
                    "expected": getattr(train, "etd", train.std),
                    "status": getattr(train, "serviceType", "Unknown")
                })
            return departures
        except Exception as e:
            _LOGGER.error("Darwin API error: %s", e)
            return []


# -------------------------------
# TfL client for London Overground
# -------------------------------
class TfLClient:
    BASE_URL = "https://api.tfl.gov.uk/StopPoint/{}/Arrivals"

    def get_departures(self, naptan_id: str):
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
                        "scheduled": train.get("scheduledDeparture"),
                        "expected": train.get("expectedArrival"),
                        "status": train.get("modeName", "Unknown")
                    })
            return departures
        except Exception as e:
            _LOGGER.error("TfL API error: %s", e)
            return []
