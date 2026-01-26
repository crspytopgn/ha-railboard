# Railboard - UK Train Departures for Home Assistant

A beautiful, real-time UK train departure and arrival board integration for Home Assistant.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/crspytopgn/ha-railboard.svg)](https://github.com/crspytopgn/ha-railboard/releases)
[![License](https://img.shields.io/github/license/crspytopgn/ha-railboard.svg)](LICENSE)

## Features

✅ Real-time departure and arrival information for **any UK railway station**  
✅ Support for **National Rail** and **Transport for London** services  
✅ Accurate delay information and cancellations  
✅ Platform numbers and calling points  
✅ Colour-coded by train operating company  
✅ Fully customizable display options  
✅ Uses Realtime Trains API for reliable data  

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

### Prerequisites

You need a **free Realtime Trains API account**:

1. Go to https://www.realtimetrains.co.uk/about/developer/
2. Sign up for a free account
3. Note your **username** and **password** (API key)

### Add to configuration.yaml

```yaml
sensor:
  - platform: railboard
    api_key: "your_realtime_trains_password"
    rtt_username: "your_realtime_trains_username"
    station_code: "PAD"  # 3-letter CRS code
    station_name: "London Paddington"  # Optional
