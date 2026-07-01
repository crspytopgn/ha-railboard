"""TfL Unified API client for bus stop arrivals."""
import logging

import requests

_LOGGER = logging.getLogger(__name__)


class TflApiError(Exception):
    """Raised when the TfL API cannot be reached or returns an error."""


class TflBusClient:
    """Client for TfL's bus StopPoint search/detail/arrivals endpoints."""

    BASE_URL = "https://api.tfl.gov.uk"

    def __init__(self, app_key: str = None):
        """Initialize with an optional TfL API subscription key (raises rate limits)."""
        self.app_key = app_key or None

    def _params(self, extra: dict = None) -> dict:
        params = dict(extra or {})
        if self.app_key:
            params["app_key"] = self.app_key
        return params

    def _get(self, path: str, params: dict = None) -> object:
        url = f"{self.BASE_URL}{path}"
        _LOGGER.debug("Calling TfL API: %s", url)
        try:
            resp = requests.get(url, params=self._params(params), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as err:
            raise TflApiError(f"Failed to call {path}: {err}") from err

    def search_stops(self, query: str) -> list:
        """Search for bus stops by name or postcode. Returns [{id, name}, ...]."""
        data = self._get(f"/StopPoint/Search/{query}", {"modes": "bus"})
        return [
            {"id": match.get("id"), "name": match.get("name") or match.get("id")}
            for match in data.get("matches", [])
            if match.get("id")
        ]

    def get_stop_routes(self, stop_id: str) -> list:
        """Return the sorted list of distinct bus route names serving a stop."""
        data = self._get(f"/StopPoint/{stop_id}")
        routes = {line.get("name") for line in data.get("lines", []) if line.get("name")}
        return sorted(routes)

    def get_arrivals(self, stop_id: str, routes: list = None, num_results: int = 5) -> list:
        """Get the next bus arrivals at a stop, optionally filtered to specific routes."""
        predictions = self._get(f"/StopPoint/{stop_id}/Arrivals")

        routes_filter = {route.strip().lower() for route in routes} if routes else None

        arrivals = []
        for prediction in predictions:
            try:
                line_name = prediction.get("lineName", "Unknown")
                if routes_filter and line_name.strip().lower() not in routes_filter:
                    continue

                time_to_station = prediction.get("timeToStation", 0)
                arrivals.append(
                    {
                        "line": line_name,
                        "destination": prediction.get("destinationName", "Unknown"),
                        "towards": prediction.get("towards", ""),
                        "platform": prediction.get("platformName", ""),
                        "minutes": max(0, round(time_to_station / 60)),
                        "time_to_station": time_to_station,
                        "expected_arrival": prediction.get("expectedArrival", ""),
                        "vehicle_id": prediction.get("vehicleId", ""),
                    }
                )
            except Exception as err:
                _LOGGER.warning("Failed to parse bus prediction: %s", err)
                continue

        arrivals.sort(key=lambda arrival: arrival["time_to_station"])
        return arrivals[:num_results]
