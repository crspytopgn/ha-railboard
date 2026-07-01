# Railboard - UK Train Departures for Home Assistant

A real-time UK train departure and arrival board integration for Home Assistant.

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
✅ Configurable entirely through the Home Assistant UI
✅ Uses the Realtime Trains API for reliable data

## Prerequisites

You need a **free Realtime Trains API account**:

1. Go to https://www.realtimetrains.co.uk/about/developer/
2. Sign up for a free account
3. Note your **username** and **password** (API key)

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
3. Enter your station code (e.g. `PAD`, `MAN`, `CYP`), an optional display name, and your Realtime Trains credentials

Find station codes at https://www.nationalrail.co.uk/stations/

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
- **Only show trains to this destination (optional)** – matches against the destination name or any calling point (e.g. "Reading" also matches trains that call at Reading en route)

## Sensors

- `sensor.railboard_departures_<station_code>` – departure board data
- `sensor.railboard_arrivals_<station_code>` – arrivals data (only created if "Show arrivals sensor" is enabled)
- `sensor.railboard_next_train_<station_code>` – state is minutes until the next catchable train departs, honouring the walking-time and destination filters (only created if "Show next train sensor" is enabled)
- `binary_sensor.railboard_disruption_<station_code>` – on if any departure at the station is currently delayed or cancelled
- `binary_sensor.railboard_leave_now_<station_code>` – on once the next catchable train is due within your configured walking time; use a state trigger on this entity for a "time to leave" automation

Each departures/arrivals sensor's state is the number of upcoming services. The full list of services — destination/origin, scheduled and expected times, platform, operator, delay/cancellation status (including reason text when RTT provides one), and calling points — is available as attributes for use in dashboards, templates, and automations.

## Service: `railboard.get_service_detail`

For a richer look at one specific train — the live time and platform at every intermediate stop, not just your station — call the `railboard.get_service_detail` service with the `service_uid` from any departure/arrival/next-train sensor's attributes. This is a separate on-demand lookup (a second RTT API call per train) rather than something fetched automatically for every row of the board, so it won't multiply your regular polling traffic.

```yaml
service: railboard.get_service_detail
data:
  service_uid: "{{ state_attr('sensor.railboard_next_train_pad', 'service_uid') }}"
```

The response includes the operator, cancellation status, and a `calling_points` list with each stop's name, CRS code, platform, and scheduled/expected arrival and departure times.
