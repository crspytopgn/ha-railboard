"""Railboard API client: Realtime Trains for comprehensive UK rail data."""
import json
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

    def get_service_detail(self, service_uid: str, run_date: str = None):
        """Get the full calling-point-by-calling-point detail for one specific service.

        This is a separate, heavier request than get_departures/get_arrivals (RTT only
        exposes per-stop realtime detail via this per-service endpoint), so callers
        should use it on demand rather than for every row of a departure board.

        run_date is an optional "YYYY-MM-DD" string; defaults to today.
        """
        if not run_date:
            run_date = datetime.now().strftime("%Y-%m-%d")
        year, month, day = run_date.split("-")

        url = f"{self.BASE_URL}/service/{service_uid}/{year}/{month}/{day}"
        _LOGGER.debug("Calling RTT API: %s", url)

        try:
            resp = requests.get(url, auth=self.auth, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as err:
            raise RailboardApiError(
                f"Failed to fetch service detail for {service_uid}: {err}"
            ) from err

        calling_points = []
        for location in data.get("locations", []):
            calling_points.append(
                {
                    "name": location.get("description", "Unknown"),
                    "crs": location.get("crs", ""),
                    "platform": location.get("platform", "") or "TBC",
                    "is_cancelled": location.get("isCancelled", False),
                    "scheduled_arrival": self._format_time(location.get("gbttBookedArrival", "")),
                    "expected_arrival": self._format_time(
                        location.get("realtimeArrival") or location.get("gbttBookedArrival", "")
                    ),
                    "scheduled_departure": self._format_time(location.get("gbttBookedDeparture", "")),
                    "expected_departure": self._format_time(
                        location.get("realtimeDeparture") or location.get("gbttBookedDeparture", "")
                    ),
                }
            )

        return {
            "service_uid": service_uid,
            "run_date": run_date,
            "operator": data.get("atocName", "Unknown"),
            "is_cancelled": data.get("isCancelled", False),
            "calling_points": calling_points,
        }

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

        if kind == "departure" and services:
            # Temporary debug aid: dump the raw shape of subsequentCallingPoints from
            # one real service so it can be confirmed against what _get_calling_points
            # assumes. Enable with:
            #   logger:
            #     logs:
            #       custom_components.railboard: debug
            _LOGGER.debug(
                "Raw subsequentCallingPoints for %s (service %s): %s",
                station_code,
                services[0].get("serviceUid", "unknown"),
                json.dumps(services[0].get("locationDetail", {}).get("subsequentCallingPoints"), indent=2),
            )

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

        cancel_reason = service.get("cancelReasonLongText") or service.get("cancelReasonShortText") or ""
        delay_reason = service.get("delayReasonLongText") or service.get("delayReasonShortText") or ""

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
            "cancel_reason": cancel_reason if is_cancelled else "",
            "delay_reason": delay_reason if is_delayed else "",
        }

        if kind == "departure":
            calling_points = self._get_calling_points(service)

            result["destination"] = point_name
            result["service_uid"] = service.get("serviceUid", "")
            result["calling_at"] = [point["name"] for point in calling_points]
            result["arrival_time"] = self._destination_arrival(calling_points, point_name)
            result["duration_minutes"] = self._calculate_duration(result["expected"], result["arrival_time"])
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

    def _get_calling_points(self, service: dict) -> list:
        """Extract each subsequent calling point, with its own expected arrival time.

        RTT nests these under one or more "association" entries (used when a service
        splits/joins along its route), each holding the calling points for that portion
        of the journey under a "callingPoint" list - so each entry here is NOT itself a
        calling point. A flatter shape is tolerated too in case that assumption is wrong
        for some service types.
        """
        calling_points = []

        for entry in service.get("locationDetail", {}).get("subsequentCallingPoints", []):
            points = entry.get("callingPoint") or entry.get("callingPoints") or [entry]
            for point in points:
                name = point.get("description", "")
                if not name:
                    continue

                scheduled_arrival = point.get("gbttBookedArrival") or point.get("realtimeArrival") or ""
                expected_arrival = point.get("realtimeArrival") or scheduled_arrival

                calling_points.append(
                    {
                        "name": name,
                        "crs": point.get("crs", ""),
                        "expected_arrival": self._format_time(expected_arrival),
                    }
                )

        return calling_points

    @staticmethod
    def _destination_arrival(calling_points: list, destination_name: str) -> str:
        """Return the expected arrival time (HH:MM) at the destination, if known."""
        if not calling_points:
            return ""

        needle = (destination_name or "").strip().lower()
        for point in calling_points:
            if point["name"].strip().lower() == needle:
                return point["expected_arrival"]

        # No exact name match (e.g. differing punctuation) - the last calling
        # point is still very likely the destination itself.
        return calling_points[-1]["expected_arrival"]

    @staticmethod
    def _calculate_duration(departure_time: str, arrival_time: str):
        """Return whole minutes from a formatted HH:MM departure to a formatted HH:MM arrival."""
        if not departure_time or not arrival_time or ":" not in departure_time or ":" not in arrival_time:
            return None

        try:
            dep_hour, dep_minute = (int(part) for part in departure_time.split(":"))
            arr_hour, arr_minute = (int(part) for part in arrival_time.split(":"))
        except ValueError:
            return None

        duration = (arr_hour * 60 + arr_minute) - (dep_hour * 60 + dep_minute)
        if duration < 0:
            # Arrival rolled over past midnight relative to departure.
            duration += 24 * 60
        return duration
