# Railboard Card & Integration

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/crspytopgn/ha-railboard-dashboard.svg)](https://github.com/crspytopgn/ha-railboard-dashboard/releases)
[![License](https://img.shields.io/github/license/crspytopgn/ha-railboard-dashboard.svg)](LICENSE)

A beautiful, real-time UK train departure board for Home Assistant, powered by the [Railboard integration](https://github.com/crspytopgn/ha-railboard).

---

## Features

✨ **Beautiful Design** – Modern interface inspired by real UK departure boards  
🚂 **Real-Time Data** – Shows live departures from your Railboard sensors  
🎨 **Colour-Coded Operators** – Each train operator displayed in brand colours  
⚙️ **Fully Customizable** – Configure via visual UI or YAML  
📱 **Responsive** – Works well on tablets and small screens  
🌙 **Theme Support** – Automatically adapts to your Home Assistant theme  
⏱ **Walking Time Filter** – Only shows departures after a user-defined walking time  
📝 **Platform & Status Display** – Optionally show platforms, delays, cancellations, calling points  

---

## Prerequisites

You must have the **Railboard integration** installed first:

🔗 [Install Railboard Integration](https://github.com/crspytopgn/ha-railboard)

This card displays data from Railboard sensors — it won’t work without them.

You also need a free **Realtime Trains API account**:

1. Go to [Realtime Trains Developer](https://www.realtimetrains.co.uk/about/developer/)
2. Sign up for a free account
3. Note your username and password (API key)

---

## Installation

### HACS (Recommended)

1. Open **HACS** in Home Assistant  
2. Go to **Frontend**  
3. Click the **three dots** menu (top right) → **Custom repositories**  
4. Add repository URL: `https://github.com/crspytopgn/ha-railboard-dashboard`  
5. Category: **Lovelace** → Click **Add**  
6. Search for **Railboard Card** → Click **Download**  
7. **Restart Home Assistant**  
8. **Hard refresh your browser** (Ctrl+F5 / Cmd+Shift+R)  

### Manual Installation

1. Download `railboard-card.js` from [latest release](https://github.com/crspytopgn/ha-railboard-dashboard/releases)  
2. Copy to `/config/www/community/railboard-card/railboard-card.js`  
3. Add resource in **Configuration → Lovelace Dashboards → Resources**:  
   - URL: `/hacsfiles/railboard-card/railboard-card.js`  
   - Type: **JavaScript Module**  
4. **Restart Home Assistant**  
5. **Hard refresh browser**  

---

## Configuration

### Railboard Integration Example (`configuration.yaml`)

```yaml
sensor:
  - platform: railboard
    api_key: "YOUR_REALTIME_TRAINS_PASSWORD"
    rtt_username: "YOUR_REALTIME_TRAINS_USERNAME"
    station_code: "PAD"  # 3-letter CRS code
    station_name: "London Paddington"  # Optional
Railboard Card Example (Visual Editor)
Edit your dashboard → + Add Card → Search Railboard Card
Configure:
Choose your Railboard sensor
Optional title
Toggle display options: platforms, status, calling points, operator badge
Max departures
Walking time (minutes)
Railboard Card YAML Example
type: custom:railboard-card
entity: sensor.railboard_departures_crystal_palace
title: Crystal Palace
show_platforms: true
show_status: true
show_calling_points: true
show_operator_badge: true
max_departures: 10
walking_time: 5  # in minutes, filters departures sooner than this
Display Options
Platforms – Shows the departure platform
Status – Shows ON TIME, +Xm (delay), or CANCELLED
Calling Points – Shows first 3 calling points and +N if more
Operator Badge – Displays train operator abbreviation in brand colour
Walking Time Filter – Excludes departures sooner than configured minutes
Tips for Small Screens
Card is responsive but long station names may truncate.
To improve readability:
Reduce max departures
Use shorter titles
Adjust dashboard card width
Use smaller text size via custom CSS if needed
Notes
Operator colours now don’t indicate on-time status; status background shows timing.
Supports all UK National Rail stations and many TfL services.
Works with Home Assistant themes automatically.
