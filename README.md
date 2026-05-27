# sonnenBatterie (v2 API) – Home Assistant Integration

Home Assistant custom integration for **sonnenBatterie** systems that expose the
modern token-based **`/api/v2`** interface (the one documented under
*Dashboard → Software Integration*).

> [!NOTE]
> This integration talks **only** to the v2 API. It exists because newer
> sonnenBatterie firmware no longer serves the legacy v1 endpoints
> (`/api/system_data`, …) that older integrations rely on — those return
> HTTP 500 on current firmware.

## Requirements

- Home Assistant **2025.5.0** or newer
- A sonnenBatterie reachable on your LAN with the **local API read access** enabled
- An **Auth-Token** (Battery Dashboard → *Software Integration*)
- For control features: **write access** enabled on the battery

## Installation

### Via HACS (custom repository)

1. HACS → ⋮ (top right) → **Custom repositories**
2. Repository: `https://github.com/Leonhard-Schwarz/ha_sonnenbatterie_v2`
   Category: **Integration**
3. Add, then search for **sonnenBatterie (v2 API)** and **Download**
4. **Restart Home Assistant**

### Manual

Copy `custom_components/sonnenbatterie_v2/` into your `<config>/custom_components/`
folder and restart Home Assistant.

## Setup

Settings → **Devices & Services** → **Add Integration** → *sonnenBatterie (v2 API)*

| Field | Description |
| --- | --- |
| IP address | e.g. `192.168.178.48` |
| Auth-Token | from *Dashboard → Software Integration* |
| Update interval | seconds (default 30) |

## Features

**Monitoring** (sensors): consumption, production, grid in/out, battery
charge/discharge, state of charge (user & real), remaining capacity, system &
operating mode, grid frequency, AC/battery voltage, backup buffer, battery care,
inverter temperature & PV values, battery cycles, module count, inverter max
power, plus per-phase power-meter sensors (incl. kWh counters for the Energy
Dashboard). Advanced/diagnostic sensors are disabled by default.

**Control** (requires write access on the battery): operating mode (select),
forced charge / forced discharge (sliders), battery reserve (slider) and reset
buttons. *Time-of-Use schedule and standby are not implemented yet.*

## Example dashboard

A ready-to-use Lovelace dashboard (Sections layout) is included as
`lovelace-dashboard-sections.yaml`. Entity IDs are derived from your configured
IP address — adjust the `sensor.sonnenbatterie_<…>` IDs to match your install.

## Status

Early release (v0.2.0). Built and tested against a v2-only sonnenBatterie.
Monitoring and basic control are implemented; Time-of-Use and standby are planned.

## Credits

Inspired by [weltmeyer/ha_sonnenbatterie](https://github.com/weltmeyer/ha_sonnenbatterie).
Built fresh against the documented v2 API.
