# Railboard - UK Train & Bus Departures for Home Assistant

A real-time UK train departure/arrival board and TfL bus stop tracker for Home Assistant.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/crspytopgn/ha-railboard.svg)](https://github.com/crspytopgn/ha-railboard/releases)
[![License](https://img.shields.io/github/license/crspytopgn/ha-railboard.svg)](LICENSE)

## Features

✅ Real-time departure and arrival information for **any UK railway station**
✅ Support for **National Rail** and **London Overground** services
✅ Accurate delay information and cancellations, with reason text where available
✅ Platform numbers and calling points
✅ **Next train sensor** with a live minutes-until-departure countdown
✅ **Walking-time filter** – hide departures you can't realistically catch
✅ **Destination filter** – track only trains heading towards (or via) a specific station
✅ **Disruption sensor** – a binary sensor that turns on when anything at the station is delayed or cancelled
✅ **Leave-now sensor** – a binary sensor that turns on once it's time to head to the station
✅ **Service detail lookup** – an on-demand service call for full per-stop calling-point detail on any train
✅ **Tracked-service sensor** – pin to one specific scheduled train (e.g. "the 08:03 to Victoria") and follow its live status day to day
✅ **Punctuality sensor** – a rolling today's on-time percentage/average delay, computed locally from data already being fetched
✅ **Coach count, request-stop, and schedule-variation flags** – exposed on every departure/arrival, no extra calls needed
✅ **Train formation detail** – unit numbers, coach count, and onboard facilities (wifi, first class, etc.) via the service detail lookup, where RTT has the data
✅ **First/last train of the day sensors** – for early-morning and late-night planning
✅ **Journey sensor** – combine two or more already-configured rail stations and/or bus stops into one "which option gets me there soonest" sensor
✅ **TfL bus stop tracking** – search for any bus stop, follow specific routes, and see the next few buses due
✅ Configurable entirely through the Home Assistant UI
✅ Uses the Realtime Trains API and TfL Unified API for reliable data

## Prerequisites

For rail stations, you need a **free Realtime Trains next-generation API refresh token**:

1. Go to https://api-portal.rtt.io
2. Sign up (requires an RTT unified login account)
3. Note the **refresh token** issued to you

Bus stops use TfL's public Unified API and work without any account, though a free API key (from https://api-portal.tfl.gov.uk/) is recommended for higher rate limits.

## Installation

### HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Go to **Integrations**
3. Click the **three dots** menu (top right)
4. Select **"Custom repositories"**
5. Add repository URL: `https://github.com/crspytopgn/ha-railboard`
6. Category: **Integration**
7. Click **Add**
8. Click **+ Explore & Download Repositories**
9. Search for **"Railboard"**
10. Click **Download**
11. **Restart Home Assistant**

### Manual Installation

1. Download the latest release from [releases](https://github.com/crspytopgn/ha-railboard/releases)
2. Extract the `custom_components/railboard` folder
3. Copy it to your Home Assistant `config/custom_components/` directory
4. Restart Home Assistant

## Configuration

Configuration is done entirely through the Home Assistant UI:

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Railboard**
3. Choose **Rail station**, **Bus stop**, or **Journey**

### Rail station

1. Enter your Realtime Trains refresh token and search for the station by name (e.g. "Crystal Palace" or "Paddington")
2. Pick the exact station from the search results, with an optional display-name override

Each station becomes its own config entry, so add the flow again for each station you want to track.

### Bus stop

1. Search for the stop by name or postcode (e.g. "Bromley North" or "SE1 9SG"), with an optional TfL API key
2. Pick the exact stop from the search results
3. Pick which routes at that stop to follow – leave empty to follow every route serving the stop

Each bus stop becomes its own config entry, so add the flow again for each stop you want to track.

### Journey

Combines two or more **already-configured** rail stations and/or bus stops into one sensor showing whichever option is soonest right now — e.g. "walk to Station A or Station B, whichever has a sooner catchable train" or "bus vs train for the same commute." Set up the individual stations/stops first, then add a Journey entry and pick which of them to combine. This makes no extra API calls — it just compares data each leg's own entry is already fetching.

### Options

After adding the integration, click **Configure** on the entry to set:

- **Show arrivals sensor** – adds a second sensor with arrivals data
- **Maximum number of departures** – how many services to fetch (1-50)
- **Show platform numbers**
- **Show ON TIME / DELAYED status**
- **Show calling points** (via...)
- **Show operator badges**
- **Show next train sensor** – adds the next-catchable-train sensor and the "leave now" binary sensor
- **Show disruption binary sensor**
- **Walking time to station (minutes)** – the next train sensor ignores anything departing sooner than this
- **Only show next-train results for trains calling at this station code (optional)** – e.g. `RDG` for Reading. This uses RTT's own server-side filtering, so it correctly matches trains that call at that station en route, not just an exact final destination. Note this takes a station **code**, not a free-text name.
- **Show punctuality sensor**
- **Track a specific scheduled departure time (optional)** – e.g. `08:03`, to add a sensor that follows that specific recurring service
- **...to this destination (optional)** – only needed if more than one service departs at the tracked time, to disambiguate which one to follow
- **Show first/last train of the day sensors** – off by default (fetched once per day when enabled, not on every poll)

Journey entries have no options of their own — recreate the entry if you want to change which legs it combines.

Bus stop entries have their own options:

- **Maximum number of buses to show**
- **Show disruption binary sensor**
- **Walking time to station/stop (minutes)** – used by the bus "leave now" sensor

## Sensors

- `sensor.railboard_departures_<station_code>` – departure board data
- `sensor.railboard_arrivals_<station_code>` – arrivals data (only created if "Show arrivals sensor" is enabled)
- `sensor.railboard_next_train_<station_code>` – state is minutes until the next catchable train departs, honouring the walking-time and destination filters (only created if "Show next train sensor" is enabled)
- `binary_sensor.railboard_disruption_<station_code>` – on if any departure at the station is currently delayed or cancelled
- `binary_sensor.railboard_leave_now_<station_code>` – on once the next catchable train is due within your configured walking time; use a state trigger on this entity for a "time to leave" automation
- `sensor.railboard_punctuality_<station_code>` – state is today's rolling on-time percentage; attributes include `on_time_count`, `delayed_count`, `cancelled_count`, and `average_delay_minutes`. Resets at local midnight. Computed purely from data already being polled, no extra API calls
- `sensor.railboard_tracked_<station_code>` – state is the current status ("On time"/"Delayed X min"/"Cancelled") of the one specific service you're tracking (only created if "Track a specific scheduled departure time" is set). If the tracked service is cancelled, its `fallback_service` attribute holds the next matching departure instead
- `binary_sensor.railboard_tracked_leave_now_<station_code>` – on once the tracked service is due within your configured walking time
- `sensor.railboard_first_train_<station_code>` / `sensor.railboard_last_train_<station_code>` – state is the scheduled HH:MM of the first/last departure of the service day (only created if "Show first/last train of the day sensors" is enabled)
- `sensor.railboard_journey_<id>` – state is minutes until the soonest catchable option across all combined legs; the `options` attribute lists every leg's current best option (which one, minutes, destination/line, status), and `best_leg` names the winning one. Rail legs respect their own walking-time/next-train settings; bus legs are filtered by their own configured walking time too
- `sensor.railboard_bus_<stop_id>` – state is minutes until the next followed bus arrives; the `arrivals` attribute lists the next few buses (line, destination, minutes, platform/stop letter) across your followed routes
- `binary_sensor.railboard_bus_disruption_<stop_id>` – on if any followed route currently has a reported disruption (checked by TfL's line status, so it still catches a fully suspended route even when it has no arrivals showing)
- `binary_sensor.railboard_bus_leave_now_<stop_id>` – on once the next bus is due within your configured walking time

Each departures/arrivals sensor's state is the number of upcoming services. The full list of services — destination/origin, scheduled and expected times, platform, operator, delay/cancellation status (including reason text when RTT provides one) — is available as attributes for use in dashboards, templates, and automations.

Each departure also includes `arrival_time` (expected arrival at the destination, HH:MM) and `duration_minutes` (journey time), both sourced directly from RTT's response for that station - no extra API calls needed. `calling_at` (the names of intermediate stops) is **not** populated automatically: RTT's compact departure-board query doesn't include intermediate stops, only the origin/destination pair, so it's always `[]` in the regular sensor data. For a specific train's full stop-by-stop list, use the `railboard.get_service_detail` action below.

Every departure/arrival also carries `vehicle_count` (number of passenger coaches), `is_request_stop` (train only calls here if requested), `schedule_type` (RTT's STP indicator - `WTT` is the normal working timetable, anything else is a short-term variation), `is_schedule_variation` (derived boolean for the above), and `runs_as_required` (this service only runs if required that day). `schedule_type`/`is_schedule_variation` require RTT's "detailed" mode, which not every token is entitled to - if yours isn't, these will just come back as `null`/`false` rather than erroring.

## Service: `railboard.get_service_detail`

For a richer look at one specific train — the live time and platform at every intermediate stop, not just your station — call the `railboard.get_service_detail` service with the `service_uid` from any departure/arrival/next-train sensor's attributes. This is a separate on-demand lookup (a second RTT API call per train) rather than something fetched automatically for every row of the board, so it won't multiply your regular polling traffic.

```yaml
service: railboard.get_service_detail
data:
  service_uid: "{{ state_attr('sensor.railboard_next_train_pad', 'service_uid') }}"
```

The response includes the operator, cancellation status, a `calling_points` list with each stop's name, CRS code, platform, and scheduled/expected arrival and departure times, and (where RTT has the data) a `formation` object with `leading_class`, `passenger_vehicles`, per-unit `units` (identity/stock type/vehicle count), `facilities` (e.g. wifi, toilet, first), and `has_first_class`. `formation` is `null` when RTT doesn't have allocation data for that service.
