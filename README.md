# Railboard - UK Train Departures for Home Assistant

A real-time UK train departure and arrival board integration for Home Assistant.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/crspytopgn/ha-railboard.svg)](https://github.com/crspytopgn/ha-railboard/releases)
[![License](https://img.shields.io/github/license/crspytopgn/ha-railboard.svg)](LICENSE)

## Features

✅ Real-time departure and arrival information for **any UK railway station**
✅ Support for **National Rail** and **London Overground** services
✅ Accurate delay information and cancellations
✅ Platform numbers and calling points
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

## Sensors

- `sensor.railboard_departures_<station_code>` – departure board data
- `sensor.railboard_arrivals_<station_code>` – arrivals data (only created if "Show arrivals sensor" is enabled)

Each sensor's state is the number of upcoming services. The full list of services — destination/origin, scheduled and expected times, platform, operator, delay/cancellation status, and calling points — is available as attributes for use in dashboards, templates, and automations.
