"""Railboard API client: Realtime Trains for comprehensive UK rail data."""
import logging
from datetime import datetime

import requests

_LOGGER = logging.getLogger(__name__)


class RailboardApiError(Exception):
    """Raised when the Realtime Trains API cannot be reached or returns an error."""


class RealtimeTrainsClient:
    """Unified client for all rail services via the Realtime Trains API."""

    BASE_URL = "https://api.rtt.io/api/v1/json"

    def __init__(self, username: str, password: str):
        """Initialize with RTT credentials (username can be email, password is API key)."""
        self.auth = (username, password)

    def get_departures(self, station_code: str, num_results: int = 15):
        """Get departures from any UK station."""
        url = f"{self.BASE_URL}/search/{station_code}"
        return self._get_services(url, station_code, num_results, "departure")

    def get_arrivals(self, station_code: str, num_results: int = 15):
        """Get arrivals at any UK station."""
        url = f"{self.BASE_URL}/search/{station_code}/arrivals"
        return self._get_services(url, station_code, num_results, "arrival")

    def _get_services(self, url: str, station_code: str, num_results: int, kind: str):
        """Fetch and parse a list of services (departures or arrivals)."""
        _LOGGER.debug("Calling RTT API: %s", url)

        try:
            resp = requests.get(url, auth=self.auth, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as err:
            raise RailboardApiError(
                f"Failed to fetch {kind}s for {station_code}: {err}"
            ) from err

        services = data.get("services") or []
        results = []

        for service in services[:num_results]:
            try:
                parsed = self._parse_service(service, kind)
            except Exception as err:
                _LOGGER.warning("Failed to parse %s service: %s", kind, err)
                continue
            if parsed is not None:
                results.append(parsed)

        _LOGGER.debug("Parsed %d %s(s) for %s", len(results), kind, station_code)
        return results

    def _parse_service(self, service: dict, kind: str):
        """Parse a single RTT service into a departure or arrival dict."""
        location_detail = service.get("locationDetail", {})

        if kind == "departure":
            points = location_detail.get("destination", [])
            scheduled = location_detail.get("gbttBookedDeparture") or ""
            realtime = location_detail.get("realtimeDeparture") or ""
        else:
            points = location_detail.get("origin", [])
            scheduled = location_detail.get("gbttBookedArrival") or ""
            realtime = location_detail.get("realtimeArrival") or ""

        if not points:
            return None

        point_name = points[0].get("description", "Unknown")

        scheduled = scheduled or realtime
        expected = realtime or scheduled
        if not scheduled:
            # No usable timing data for this service at all - skip it.
            return None

        is_cancelled = service.get("isCancelled", False)
        delay_minutes = self._calculate_delay(scheduled, expected)
        is_delayed = delay_minutes > 0

        operator = service.get("atocName", "Unknown")
        operator_code = service.get("atocCode", "")

        result = {
            "network": self._classify_network(operator, operator_code),
            "scheduled": self._format_time(scheduled),
            "expected": self._format_time(expected),
            "platform": location_detail.get("platform", "") or "TBC",
            "operator": operator,
            "is_cancelled": is_cancelled,
            "is_delayed": is_delayed,
            "delay_minutes": delay_minutes,
            "status": self._determine_status(is_cancelled, is_delayed, delay_minutes),
        }

        if kind == "departure":
            result["destination"] = point_name
            result["service_uid"] = service.get("serviceUid", "")
            result["calling_at"] = self._get_calling_points(service)
        else:
            result["origin"] = point_name

        return result

    @staticmethod
    def _classify_network(operator: str, operator_code: str) -> str:
        """Classify a service as London Overground or National Rail."""
        if operator_code == "LO" or "Overground" in operator:
            return "London Overground"
        return "National Rail"

    @staticmethod
    def _calculate_delay(scheduled: str, expected: str) -> int:
        """Return the delay in minutes, correctly handling delays that cross midnight."""
        if not scheduled or not expected or scheduled == expected:
            return 0

        try:
            sched_time = datetime.strptime(scheduled, "%H%M")
            exp_time = datetime.strptime(expected, "%H%M")
        except ValueError:
            return 0

        delay = int((exp_time - sched_time).total_seconds() / 60)
        if delay < -720:
            # Expected time rolled over past midnight relative to scheduled.
            delay += 24 * 60
        return delay

    @staticmethod
    def _format_time(time_str: str) -> str:
        """Format HHMM to HH:MM."""
        if not time_str or len(time_str) != 4:
            return time_str
        return f"{time_str[:2]}:{time_str[2:]}"

    @staticmethod
    def _determine_status(is_cancelled: bool, is_delayed: bool, delay_minutes: int) -> str:
        """Determine human-readable status."""
        if is_cancelled:
            return "Cancelled"
        if is_delayed:
            return f"Delayed {delay_minutes} min"
        return "On time"

    @staticmethod
    def _get_calling_points(service: dict) -> list:
        """Extract calling points from a departure service."""
        subsequent = service.get("locationDetail", {}).get("subsequentCallingPoints", [])
        return [point.get("description", "") for point in subsequent if point.get("description")]
