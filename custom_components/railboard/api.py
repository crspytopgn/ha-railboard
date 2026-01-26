"""Railboard API clients: Using Realtime Trains for comprehensive data"""
import logging
import requests
from datetime import datetime

_LOGGER = logging.getLogger(__name__)


class RealtimeTrainsClient:
    """Unified client for all rail services via Realtime Trains API"""
    BASE_URL = "https://api.rtt.io/api/v1/json"
    
    def __init__(self, username: str, password: str):
        """Initialize with RTT credentials (username can be email, password is API key)"""
        self.auth = (username, password)
        _LOGGER.info("RealtimeTrainsClient initialized")
    
    def get_departures(self, station_code: str, num_results: int = 15):
        """Get departures from any UK station (including Overground)"""
        _LOGGER.info(f"Fetching departures for {station_code}")
        
        try:
            url = f"{self.BASE_URL}/search/{station_code}"
            _LOGGER.debug(f"Calling RTT API: {url}")
            
            resp = requests.get(url, auth=self.auth, timeout=10)
            resp.raise_for_status()
            
            data = resp.json()
            _LOGGER.debug(f"RTT response location: {data.get('location', {}).get('name')}")
            
            services = data.get("services", [])
            _LOGGER.info(f"RTT returned {len(services)} services")
            
            departures = []
            
            for service in services[:num_results]:
                try:
                    location_detail = service.get("locationDetail", {})
                    
                    # Get destination info
                    destinations = location_detail.get("destination", [])
                    if not destinations:
                        continue
                    
                    destination_name = destinations[0].get("description", "Unknown")
                    
                    # Get times
                    scheduled = location_detail.get("gbttBookedDeparture") or location_detail.get("realtimeDeparture", "")
                    expected = location_detail.get("realtimeDeparture") or scheduled
                    
                    # Determine if delayed/cancelled
                    is_cancelled = service.get("isCancelled", False)
                    is_delayed = False
                    delay_minutes = 0
                    
                    if scheduled and expected and scheduled != expected:
                        is_delayed = True
                        # Calculate delay if possible
                        try:
                            sched_time = datetime.strptime(scheduled, "%H%M")
                            exp_time = datetime.strptime(expected, "%H%M")
                            delay_minutes = int((exp_time - sched_time).total_seconds() / 60)
                        except:
                            pass
                    
                    # Determine operator/network
                    operator = service.get("atocName", "Unknown")
                    operator_code = service.get("atocCode", "")
                    
                    # Check if it's London Overground
                    is_overground = operator_code == "LO" or "Overground" in operator
                    
                    # Get platform
                    platform = location_detail.get("platform", "")
                    if not platform:
                        platform = location_detail.get("platformConfirmed", False) and "TBC" or ""
                    
                    # Build departure object
                    departure = {
                        "network": "London Overground" if is_overground else "National Rail",
                        "destination": destination_name,
                        "scheduled": self._format_time(scheduled),
                        "expected": self._format_time(expected),
                        "platform": platform or "TBC",
                        "operator": operator,
                        "status": self._determine_status(is_cancelled, is_delayed, delay_minutes),
                        "is_cancelled": is_cancelled,
                        "is_delayed": is_delayed,
                        "delay_minutes": delay_minutes,
                        "service_uid": service.get("serviceUid", ""),
                        "calling_at": self._get_calling_points(service),
                    }
                    
                    departures.append(departure)
                    _LOGGER.debug(f"Parsed departure to {destination_name} at {expected}")
                    
                except Exception as e:
                    _LOGGER.warning(f"Failed to parse service: {e}", exc_info=True)
                    continue
            
            _LOGGER.info(f"Successfully parsed {len(departures)} departures")
            return departures
            
        except requests.exceptions.RequestException as e:
            _LOGGER.error(f"RTT API request failed: {e}", exc_info=True)
            return []
        except Exception as e:
            _LOGGER.error(f"RTT API error: {e}", exc_info=True)
            return []
    
    def get_arrivals(self, station_code: str, num_results: int = 15):
        """Get arrivals at any UK station"""
        _LOGGER.info(f"Fetching arrivals for {station_code}")
        
        try:
            url = f"{self.BASE_URL}/search/{station_code}/arrivals"
            _LOGGER.debug(f"Calling RTT API: {url}")
            
            resp = requests.get(url, auth=self.auth, timeout=10)
            resp.raise_for_status()
            
            data = resp.json()
            services = data.get("services", [])
            _LOGGER.info(f"RTT returned {len(services)} arrival services")
            
            arrivals = []
            
            for service in services[:num_results]:
                try:
                    location_detail = service.get("locationDetail", {})
                    
                    # Get origin info
                    origins = location_detail.get("origin", [])
                    if not origins:
                        continue
                    
                    origin_name = origins[0].get("description", "Unknown")
                    
                    # Get times
                    scheduled = location_detail.get("gbttBookedArrival") or location_detail.get("realtimeArrival", "")
                    expected = location_detail.get("realtimeArrival") or scheduled
                    
                    is_cancelled = service.get("isCancelled", False)
                    operator = service.get("atocName", "Unknown")
                    operator_code = service.get("atocCode", "")
                    is_overground = operator_code == "LO" or "Overground" in operator
                    
                    platform = location_detail.get("platform", "") or "TBC"
                    
                    arrival = {
                        "network": "London Overground" if is_overground else "National Rail",
                        "origin": origin_name,
                        "scheduled": self._format_time(scheduled),
                        "expected": self._format_time(expected),
                        "platform": platform,
                        "operator": operator,
                        "status": "Cancelled" if is_cancelled else "On time",
                        "is_cancelled": is_cancelled,
                    }
                    
                    arrivals.append(arrival)
                    
                except Exception as e:
                    _LOGGER.warning(f"Failed to parse arrival: {e}")
                    continue
            
            _LOGGER.info(f"Successfully parsed {len(arrivals)} arrivals")
            return arrivals
            
        except Exception as e:
            _LOGGER.error(f"RTT arrivals API error: {e}", exc_info=True)
            return []
    
    def _format_time(self, time_str: str) -> str:
        """Format HHMM to HH:MM"""
        if not time_str or len(time_str) != 4:
            return time_str
        return f"{time_str[:2]}:{time_str[2:]}"
    
    def _determine_status(self, is_cancelled: bool, is_delayed: bool, delay_minutes: int) -> str:
        """Determine human-readable status"""
        if is_cancelled:
            return "Cancelled"
        if is_delayed:
            if delay_minutes > 0:
                return f"Delayed {delay_minutes} min"
            return "Delayed"
        return "On time"
    
    def _get_calling_points(self, service: dict) -> list:
        """Extract calling points from service"""
        try:
            subsequent = service.get("locationDetail", {}).get("subsequentCallingPoints", [])
            return [point.get("description", "") for point in subsequent if point.get("description")]
        except:
            return []
