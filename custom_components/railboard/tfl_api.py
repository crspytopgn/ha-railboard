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
        """Return the sorted list of distinct bus route names serving a stop.

        TfL's /StopPoint/{id} always returns an array (StopPointArray), even
        for a single id - not a bare object. The previous version of this
        method assumed a bare object and would raise AttributeError here.
        """
        data = self._get(f"/StopPoint/{stop_id}")
        stops = data if isinstance(data, list) else [data]

        routes = set()
        for stop in stops:
            for line in (stop or {}).get("lines", []) or []:
                name = line.get("name")
                if name:
                    routes.add(name)

        return sorted(routes)

    def get_arrivals(self, stop_id: str, routes: list = None, num_results: int = 5) -> list:
        """Get the next bus arrivals at a stop, optionally filtered to specific routes."""
        predictions = self._get(f"/StopPoint/{stop_id}/Arrivals")
        if not isinstance(predictions, list):
            _LOGGER.warning("Unexpected /Arrivals response shape for %s: %r", stop_id, type(predictions))
            predictions = []

        # Temporary debug aid: confirm whether TfL is genuinely returning zero
        # predictions (e.g. rate-limited without an app_key, wrong stop_id) versus
        # this client failing to parse a non-empty response. Enable with:
        #   logger:
        #     logs:
        #       custom_components.railboard: debug
        _LOGGER.debug(
            "Raw /Arrivals for %s: %d prediction(s)%s",
            stop_id,
            len(predictions),
            f", sample: {predictions[0]}" if predictions else "",
        )

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
                        "line_id": prediction.get("lineId", line_name.strip().lower()),
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

    def get_line_status(self, line_ids: list) -> list:
        """Return current disruptions for the given bus line ids (empty if all running normally).

        line_ids are TfL line ids (for buses this is the route number, lower-cased,
        e.g. "358", "n3"), not the human-readable route name.
        """
        if not line_ids:
            return []

        ids = ",".join(sorted({line_id for line_id in line_ids if line_id}))
        if not ids:
            return []

        data = self._get(f"/Line/{ids}/Status")
        if not isinstance(data, list):
            _LOGGER.warning("Unexpected /Line/Status response shape for %s: %r", ids, type(data))
            data = []

        disruptions = []
        for line in data:
            line_name = line.get("name", line.get("id", "Unknown"))
            for status in line.get("lineStatuses", []):
                description = status.get("statusSeverityDescription", "Unknown")
                if description.lower() == "good service":
                    continue
                disruptions.append(
                    {
                        "line": line_name,
                        "status": description,
                        "reason": status.get("reason", ""),
                    }
                )

        return disruptions
