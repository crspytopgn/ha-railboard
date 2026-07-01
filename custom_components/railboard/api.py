"""Railboard API client: Realtime Trains "next-generation" (v2) API.

Uses the gb-nr namespace of https://data.rtt.io, authenticated with a long-life
refresh token (from https://api-portal.rtt.io) exchanged for short-life access
tokens - see /api/get_access_token in
https://realtimetrains.github.io/api-specification/.
"""
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

_LOGGER = logging.getLogger(__name__)

_LONDON_TZ = ZoneInfo("Europe/London")


class RailboardApiError(Exception):
    """Raised when the Realtime Trains API cannot be reached or returns an error."""


class RealtimeTrainsClient:
    """Client for the Realtime Trains next-generation API (gb-nr namespace)."""

    BASE_URL = "https://data.rtt.io"

    def __init__(self, refresh_token: str):
        """Initialize with a long-life refresh token from https://api-portal.rtt.io."""
        self.refresh_token = refresh_token
        self._access_token = None
        self._access_token_expiry = None
        self._detailed_supported = True

    def get_board(self, station_code: str, num_results: int = 15, filter_to: str = None) -> dict:
        """Fetch departures and arrivals at a station from a single query.

        Both lists come from one API call: every service at the station carries
        its own arrival and/or departure activity, so there's no need for two
        separate requests the way the classic Pull API required.

        filter_to, if given, is a station code (short or long) - only services
        that subsequently call there are returned, using the API's own native
        filtering rather than string-matching a destination name client-side.
        """
        services = self._get_location_services(station_code, filter_to)

        departures = []
        arrivals = []

        for item in services:
            try:
                departure = self._parse_service(item, "departure")
            except Exception as err:
                _LOGGER.warning("Failed to parse departure service: %s", err)
                departure = None
            if departure is not None:
                departures.append(departure)

            try:
                arrival = self._parse_service(item, "arrival")
            except Exception as err:
                _LOGGER.warning("Failed to parse arrival service: %s", err)
                arrival = None
            if arrival is not None:
                arrivals.append(arrival)

        return {
            "departures": departures[:num_results],
            "arrivals": arrivals[:num_results],
        }

    def get_service_detail(self, service_uid: str, run_date: str = None) -> dict:
        """Get the full calling-point-by-calling-point detail for one specific service.

        This is a separate, heavier request than get_board (RTT only exposes
        per-stop realtime detail via this per-service endpoint), so callers
        should use it on demand rather than for every row of a departure board.

        service_uid is the value from a departure/arrival's "service_uid" field
        (e.g. "gb-nr:L01525:2025-10-26" or "L01525:2025-10-26"). run_date, if
        given, is a "YYYY-MM-DD" string overriding the date embedded in service_uid.
        """
        identity, departure_date = self._split_service_uid(service_uid)
        if run_date:
            departure_date = run_date

        data = self._get(
            "/gb-nr/service",
            {"identity": identity, "departureDate": departure_date, "detailed": "true"},
        )
        service = data.get("service", {}) or {}
        schedule_metadata = service.get("scheduleMetadata", {}) or {}
        operator = schedule_metadata.get("operator", {}) or {}

        calling_points = []
        is_cancelled = False

        for location in service.get("locations", []):
            location_info = location.get("location", {}) or {}
            temporal = location.get("temporalData", {}) or {}
            arrival = temporal.get("arrival") or {}
            departure = temporal.get("departure") or {}
            platform_data = (location.get("locationMetadata") or {}).get("platform") or {}

            if arrival.get("isCancelled") or departure.get("isCancelled"):
                is_cancelled = True

            short_codes = location_info.get("shortCodes") or []

            calling_points.append(
                {
                    "name": location_info.get("description", "Unknown"),
                    "crs": short_codes[0] if short_codes else "",
                    "platform": platform_data.get("actual") or platform_data.get("planned") or "TBC",
                    "is_cancelled": bool(arrival.get("isCancelled") or departure.get("isCancelled")),
                    "scheduled_arrival": self._format_local(self._parse_datetime(arrival.get("scheduleAdvertised"))),
                    "expected_arrival": self._format_local(self._latest_time(arrival)),
                    "scheduled_departure": self._format_local(
                        self._parse_datetime(departure.get("scheduleAdvertised"))
                    ),
                    "expected_departure": self._format_local(self._latest_time(departure)),
                }
            )

        return {
            "service_uid": service_uid,
            "run_date": departure_date,
            "operator": operator.get("name", "Unknown"),
            "is_cancelled": is_cancelled,
            "calling_points": calling_points,
        }

    def _get_location_services(self, station_code: str, filter_to: str = None) -> list:
        """Fetch the raw list of services at a station in the current time window."""
        params = {"code": station_code, "timeWindow": 120}
        if filter_to:
            params["filterTo"] = filter_to

        if self._detailed_supported:
            try:
                data = self._get("/gb-nr/location", {**params, "detailed": "true"})
                return data.get("services") or []
            except RailboardApiError:
                # Detailed mode (needed for stpIndicator) may not be entitled on this
                # token - fall back permanently for the rest of this client's lifetime
                # rather than doubling every future request trying it again.
                _LOGGER.debug("Detailed mode unavailable for this token; falling back to standard mode")
                self._detailed_supported = False

        data = self._get("/gb-nr/location", params)
        return data.get("services") or []

    def _parse_service(self, item: dict, kind: str):
        """Parse one service's line-up entry into a departure or arrival dict.

        kind is "departure" or "arrival", matching the API's own temporalData
        sub-keys - a service only appears in the departures list if it has a
        departure activity at this station, and likewise for arrivals.
        """
        temporal = item.get("temporalData", {}) or {}
        activity = temporal.get(kind) or {}
        if not activity:
            return None

        scheduled_dt = self._parse_datetime(activity.get("scheduleAdvertised") or activity.get("scheduleInternal"))
        if scheduled_dt is None:
            # No usable timing data for this activity at all - skip it.
            return None

        expected_dt = self._latest_time(activity) or scheduled_dt

        is_cancelled = activity.get("isCancelled", False)
        delay_minutes = activity.get("realtimeAdvertisedLateness") or 0
        is_delayed = bool(delay_minutes and delay_minutes > 0)

        schedule_metadata = item.get("scheduleMetadata", {}) or {}
        operator = schedule_metadata.get("operator", {}) or {}
        operator_name = operator.get("name", "Unknown")
        operator_code = operator.get("code", "")

        reasons = item.get("reasons") or []
        cancel_reason = next(
            (r.get("longText") or r.get("shortText", "") for r in reasons if r.get("type") == "CANCEL"), ""
        )
        delay_reason = next(
            (r.get("longText") or r.get("shortText", "") for r in reasons if r.get("type") == "DELAY"), ""
        )

        location_metadata = item.get("locationMetadata") or {}
        platform_data = location_metadata.get("platform") or {}
        platform = platform_data.get("actual") or platform_data.get("planned") or "TBC"

        stp_indicator = schedule_metadata.get("stpIndicator")

        result = {
            "network": self._classify_network(operator_name, operator_code),
            "scheduled": self._format_local(scheduled_dt),
            "expected": self._format_local(expected_dt),
            "platform": platform,
            "operator": operator_name,
            "is_cancelled": is_cancelled,
            "is_delayed": is_delayed,
            "delay_minutes": delay_minutes,
            "status": self._determine_status(is_cancelled, is_delayed, delay_minutes),
            "cancel_reason": cancel_reason if is_cancelled else "",
            "delay_reason": delay_reason if is_delayed else "",
            "vehicle_count": location_metadata.get("numberOfVehicles"),
            "is_request_stop": bool(location_metadata.get("isRequestStop", False)),
            # schedule_type/is_schedule_variation are only populated if this token
            # is entitled to "detailed" mode (see _get_location_services); WTT means
            # the normal working timetable, anything else is a short-term variation.
            "schedule_type": stp_indicator,
            "is_schedule_variation": bool(stp_indicator and stp_indicator != "WTT"),
            "runs_as_required": bool(schedule_metadata.get("runsAsRequired", False)),
        }

        if kind == "departure":
            destination_pairs = item.get("destination") or []
            destination = destination_pairs[0] if destination_pairs else {}
            destination_location = destination.get("location", {}) or {}
            destination_temporal = destination.get("temporalData", {}) or {}
            arrival_dt = self._latest_time(destination_temporal) or self._parse_datetime(
                destination_temporal.get("scheduleAdvertised")
            )

            result["destination"] = destination_location.get("description", "Unknown")
            result["service_uid"] = schedule_metadata.get("uniqueIdentity", "")
            # RTT's compact board query doesn't include intermediate calling points -
            # use the railboard.get_service_detail action for the full stop-by-stop list.
            result["calling_at"] = []
            result["arrival_time"] = self._format_local(arrival_dt)
            result["duration_minutes"] = (
                int((arrival_dt - expected_dt).total_seconds() // 60) if arrival_dt else None
            )
        else:
            origin_pairs = item.get("origin") or []
            origin_location = (origin_pairs[0].get("location", {}) if origin_pairs else {}) or {}
            result["origin"] = origin_location.get("description", "Unknown")

        return result

    def _ensure_access_token(self):
        """Exchange the refresh token for a short-life access token, refreshing as needed."""
        now = datetime.now(timezone.utc)
        if self._access_token and self._access_token_expiry and now < self._access_token_expiry - timedelta(
            seconds=60
        ):
            return

        try:
            resp = requests.get(
                f"{self.BASE_URL}/api/get_access_token",
                headers={"Authorization": f"Bearer {self.refresh_token}"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as err:
            raise RailboardApiError(f"Failed to obtain an access token: {err}") from err

        self._access_token = data.get("token")
        self._access_token_expiry = self._parse_datetime(data.get("validUntil")) or (now + timedelta(minutes=5))

    def _get(self, path: str, params: dict = None) -> dict:
        """Make an authenticated GET request against the API."""
        self._ensure_access_token()

        url = f"{self.BASE_URL}{path}"
        _LOGGER.debug("Calling RTT API: %s %s", url, params)

        try:
            resp = requests.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {self._access_token}"},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as err:
            raise RailboardApiError(f"Failed to call {path}: {err}") from err

    @staticmethod
    def _split_service_uid(service_uid: str):
        """Split a service_uid ("gb-nr:L01525:2025-10-26" or "L01525:2025-10-26") into (identity, date)."""
        parts = service_uid.split(":")
        if len(parts) == 3:
            _, identity, departure_date = parts
        elif len(parts) == 2:
            identity, departure_date = parts
        else:
            raise RailboardApiError(f"Unrecognised service identifier: {service_uid}")
        return identity, departure_date

    @staticmethod
    def _latest_time(activity: dict):
        """Return the most up-to-date known time for an IndividualTemporalData block."""
        if not activity:
            return None
        for key in ("realtimeActual", "realtimeForecast", "realtimeEstimate"):
            parsed = RealtimeTrainsClient._parse_datetime(activity.get(key))
            if parsed is not None:
                return parsed
        return None

    @staticmethod
    def _parse_datetime(value: str):
        """Parse a StandardisedDateTime (ISO 8601, e.g. "2025-10-25T13:45:00Z") string."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _format_local(dt) -> str:
        """Format a timezone-aware datetime as local (Europe/London) HH:MM."""
        if dt is None:
            return ""
        return dt.astimezone(_LONDON_TZ).strftime("%H:%M")

    @staticmethod
    def _classify_network(operator_name: str, operator_code: str) -> str:
        """Classify a service as London Overground or National Rail."""
        if operator_code == "LO" or "Overground" in operator_name:
            return "London Overground"
        return "National Rail"

    @staticmethod
    def _determine_status(is_cancelled: bool, is_delayed: bool, delay_minutes: int) -> str:
        """Determine human-readable status."""
        if is_cancelled:
            return "Cancelled"
        if is_delayed:
            return f"Delayed {delay_minutes} min"
        return "On time"
