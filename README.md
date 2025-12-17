# Home Performance

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/Hugofromfrance/home_performance.svg)](https://github.com/Hugofromfrance/home_performance/releases)

A Home Assistant integration to analyze and monitor the thermal performance of your home.

## 🤔 Why Home Performance?

You use electric heating and wonder:
- **"Is my room well insulated?"** → Measured K coefficient
- **"How much do I actually consume?"** → Daily energy
- **"Did I forget to close a window?"** → Automatic detection
- **"Which room costs the most?"** → Multi-zone comparison

**Home Performance** answers these questions by analyzing your **real** heating data, without theoretical calculations.

### 💡 Use Cases

| Situation | What Home Performance provides |
|-----------|-------------------------------|
| Buying/Renting | Verify actual thermal performance (vs theoretical EPC) |
| Insulation work | Measure improvement before/after |
| Bill optimization | Identify energy-hungry rooms |
| Diagnostics | Detect open windows, thermal bridges |
| Comparison | Compare your rooms to each other (K/m²) |

## ✨ Main Features

- 🏠 **Multi-zone** - Manage all your rooms from a single integration
- 🎴 **Built-in Lovelace card** - Modern design, ready to use
- 📊 **Measured energy counter** - Power sensor integration (Utility Meter)
- 💾 **Data persistence** - Saved after restart
- 🎯 **Energy performance** - Comparison to national average
- ⚡ **Event-driven architecture** - Instant detection (heating, windows)
- 🪟 **Open window detection** - Real-time alert on temperature drop

## 🔌 Hardware Compatibility

**The integration is 100% hardware agnostic!** It works with anything that exposes standard Home Assistant entities.

### Minimum Requirements

| Need | Compatible examples |
|------|---------------------|
| Indoor temp sensor | Aqara, Sonoff SNZB-02, Xiaomi, Netatmo, Ecobee, Shelly H&T, ESPHome... |
| Outdoor temp sensor | Local weather station, Weather services, Netatmo Outdoor... |
| Heating entity | Any `climate.*`, `switch.*` or `input_boolean.*` |

### Optional (recommended)

| Sensor | Examples | Benefit |
|--------|----------|---------|
| Instant power | Shelly Plug S, TP-Link, Tuya, Sonoff POW, NodOn | Precise heating time |
| Energy counter | HA Utility Meter, native counter | Measured vs estimated energy |

### Supported Heating Types

| Type | Compatible? | Notes |
|------|-------------|-------|
| Radiator + smart plug | ✅ | Ideal with power measurement |
| Radiator + pilot wire | ✅ | NodOn, Qubino, etc. |
| Convector with thermostat | ✅ | Via switch or climate |
| Heat pump / AC | ✅ | Via climate entity |
| Electric underfloor heating | ✅ | With power sensor |
| Central gas/oil heating | ⚠️ | Possible but less precise (no individual power measurement) |

## 🎯 Concept

This integration calculates the **thermal loss coefficient K** of each room using a simple physical approach:

```
K (W/°C) = Energy supplied / (ΔT × duration)
         = (Heater_power × heating_time) / (Avg_ΔT × 24h)
```

**Concrete example**: A 1000W heater running 6h out of 24h to maintain 19°C when it's 5°C outside:
- Energy = 1000W × 6h = 6 kWh
- ΔT = 14°C
- **K = 6000 / (14 × 24) ≈ 18 W/°C**

→ This room loses 18W per degree of difference with the outside.

### Empirical vs Theoretical Approach

This integration uses **empirical measurement** of thermal performance, unlike theoretical methods:

| | Theoretical approach (EPC, building codes...) | Empirical approach (Home Performance) |
|--|-----------------------------------------------|---------------------------------------|
| **Method** | Calculation based on material characteristics (U, R coefficients) | Observation of real heating data |
| **Data** | Manufacturer specs, standards, assumptions | Energy consumed, measured temperatures |
| **Includes** | What is documented | **Everything**: thermal bridges, infiltrations, installation defects... |
| **Accuracy** | Theoretical (may differ from reality) | Reflects actual in-situ performance |

> **Example**: A window certified Uw=1.1 W/(m²·K) may actually have degraded performance if poorly installed or with worn seals. Empirical measurement captures these imperfections.

#### Difference with U/Uw/Ug Coefficients

**U** coefficients (formerly "K" in standards) measure the thermal transmission of a **specific wall** (window, wall) in W/(m²·K). They are measured in laboratories and allow product comparison.

Home Performance's **K coefficient** measures the **global heat loss** of an entire room in W/°C. It's equivalent to the **G** (or GV) coefficient used in building thermal engineering, but measured empirically rather than calculated.

## 📊 Created Sensors (per zone)

### Thermal Coefficients

| Sensor | Description |
|--------|-------------|
| **K Coefficient** | Thermal loss (W/°C) - lower is better |
| **K per m²** | Normalized by surface - comparable between rooms |
| **K per m³** | Normalized by volume - better if different heights |
| **Insulation Rating** | Smart: calculated, inferred, or conserved depending on season |

### 🎯 Smart Insulation Rating

The insulation rating automatically adapts to all situations:

| Situation | Display | Description |
|-----------|---------|-------------|
| K calculated | **A to G** | Rating based on K/m³ coefficient |
| Low heating + stable T° | **🏆 Excellent (inferred)** | Excellent insulation automatically inferred |
| Summer mode (T° out > T° in) | **☀️ Summer mode** | Measurement impossible + last K conserved |
| Off-season (ΔT < 5°C) | **🌤️ Off-season** | Insufficient ΔT + last K conserved |
| Data collection | **Waiting** | < 12h of data |

#### Automatically Inferred Insulation 🏆

If after **24h** of observation:
- ΔT is significant (≥ 5°C)
- The heater has run very little (< 30 min)
- Indoor temperature remained **stable** (variation < 2°C)

→ The integration automatically infers that insulation is **excellent**!

> **Logic**: If the room maintains its temperature without heating while it's cold outside, heat loss is very low.

#### Last Valid K Conservation

In summer or off-season, the integration **keeps the last calculated K coefficient** and displays it with the appropriate season message. You thus keep a useful reference all year round.

### Daily Energy

| Sensor | Description |
|--------|-------------|
| **Energy 24h (estimated)** | kWh on 24h sliding window (declared power × time ON) |
| **Energy day (measured)** | Real daily kWh counter (if power sensor or external counter configured) |

> **Note**: Measured energy takes priority over estimated in the card. The `source` attribute indicates the origin: `external` (HA counter) or `integrated` (calculation from power sensor).

### Performance & Comfort

| Sensor | Description |
|--------|-------------|
| **Energy performance** | Comparison to national average (excellent/standard/needs optimization) |
| **Heating time (24h)** | Operating duration (format: `Xh Ymin`) |
| **Heating ratio** | % of time heating is active |
| **Avg ΔT (24h)** | Average indoor/outdoor difference |

The `source` attribute on Time/Ratio indicates: `measured` (via power sensor > 50W) or `estimated` (via switch state).

### Status

| Sensor | Description |
|--------|-------------|
| **Data hours** | Duration of collected data (format: `Xh Ymin`) |
| **Remaining analysis time** | Time before data is ready |
| **Analysis progress** | Completion percentage (0-100%) |
| **Data ready** | Binary sensor indicating if analysis is available |
| **Open window** | Detection by rapid temperature drop |

## 🏠 Multi-zones

Easily manage all your rooms!

### Adding Zones

1. **Settings → Devices & services**
2. Click **"+ Add integration"**
3. Search for **"Home Performance"**
4. Configure the new zone

Each zone appears as a separate entry, all grouped under "Home Performance":

```
Home Performance - Flavien's Room
Home Performance - Living Room
Home Performance - Office
```

### Managing a Zone

In the integrations list, click **Options** (⚙️) of the zone to modify:
- Change settings (power, surface, sensors...)
- Delete the zone

Each zone has its **own sensors** and **own Lovelace card**.

## 🎴 Built-in Lovelace Card

The integration includes a **ready-to-use modern custom card**!

### Card Installation

**The Lovelace resource is automatically registered** when installing the integration (HA default storage mode).

Simply add one card per zone in your dashboard:

```yaml
type: custom:home-performance-card
zone: Living Room
title: Living Room Performance
```

```yaml
type: custom:home-performance-card
zone: Bedroom
title: Bedroom Performance
```

<details>
<summary>📝 YAML mode (if resource is not auto-detected)</summary>

If you use a YAML mode dashboard, manually add the resource:
- **Settings → Dashboards → ⋮ → Resources**
- URL: `/home_performance/home-performance-card.js`
- Type: `JavaScript Module`

</details>

### Card Options

| Option | Default | Description |
|--------|---------|-------------|
| `zone` | *required* | Exact name of your zone |
| `title` | "Thermal Performance" | Displayed title |
| `demo` | false | Demo mode with fake data |

### Card Features

- 📊 **Visual scores** - Insulation and Performance with colors
- 🌡️ **Temperatures** - Indoor/Outdoor in real-time
- 📈 **Detailed metrics** - K coefficient, Energy, Heating time
- ⏳ **Progress** - Progress bar during initial analysis
- 🎨 **Adaptive design** - Adapts to light/dark theme

## 📋 Prerequisites

- Home Assistant 2024.4.0 or newer
- Indoor temperature sensor (per zone)
- Outdoor temperature sensor (shareable between zones)
- Climate OR switch entity controlling heating (per zone)

## ⚙️ Configuration

### Required Parameters (per zone)

| Parameter | Description |
|-----------|-------------|
| Zone name | Room name (e.g.: Living Room) |
| Indoor temp sensor | sensor.xxx_temperature |
| Outdoor temp sensor | sensor.xxx_outdoor (shareable between zones) |
| Heating entity | climate.xxx or switch.xxx |
| Heater power | Declared power in Watts |

### Optional Parameters

| Parameter | Description |
|-----------|-------------|
| Surface | m² (for K/m²) |
| Volume | m³ (for K/m³ and insulation rating) |
| Power sensor | sensor.xxx_power in Watts (for energy + precise heat detection) |
| External energy counter | sensor.xxx_energy (your own HA Utility Meter) |

> **Notes**:
> - If you provide an external energy counter AND a power sensor, the external counter is used as priority for energy.
> - The power sensor also enables **precise heat detection** (power > 50W), ideal for heaters with internal thermostat or pilot wire.
> - Options are **modifiable afterwards** and the integration reloads automatically.

## 💾 Data Persistence

Data is **automatically saved** and restored after a Home Assistant restart:

- ✅ Thermal history (up to 48h)
- ✅ Calculated K coefficient
- ✅ Energy counters
- ✅ No need to wait 12h again after each restart!

**Storage**: `/config/.storage/home_performance.{zone}`

**Save frequency**: Every 5 minutes + at HA shutdown

## 📦 Installation

### HACS (Recommended)

1. Open HACS
2. Click on "Integrations"
3. Menu ⋮ → "Custom repositories"
4. Add `https://github.com/Hugofromfrance/home_performance` (category: Integration)
5. Install "Home Performance"
6. Restart Home Assistant

### Manual

1. Copy `custom_components/home_performance` to your `config/custom_components/` folder
2. Restart Home Assistant

## 🚀 Usage

### First Configuration

1. Go to **Settings → Devices & services**
2. Click **"Add integration"**
3. Search for **"Home Performance"**
4. Configure your first zone

### Adding Rooms

1. Go to **Settings → Devices & services**
2. Click **"+ Add integration"**
3. Search for **"Home Performance"**
4. Configure the new zone

**Note**: Calculations start after **12h** of collected data and require a minimum ΔT of 5°C to be reliable.

## 🎨 Dashboard Examples

Additional examples are available in [`examples/dashboard_card.yaml`](examples/dashboard_card.yaml):

| Option | Dependencies | Description |
|--------|--------------|-------------|
| **Custom card** | None | Modern built-in card ⭐ |
| **Option 1** | None | Native HA cards |
| **Option 2** | Mushroom Cards | Modern and clean look |
| **Bonus** | ApexCharts | 7-day history graph |

### Installing Dependencies (optional)

For advanced options, install via HACS:
- [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom)
- [stack-in-card](https://github.com/custom-cards/stack-in-card)
- [ApexCharts Card](https://github.com/RomRider/apexcharts-card)

## 📈 Energy Performance

The performance sensor compares your consumption to the French national average:

| Level | Meaning |
|-------|---------|
| 🟢 **Excellent** | -40% vs national average |
| 🟡 **Standard** | Within average |
| 🟠 **Needs optimization** | Above average |

### Calculation Formula

Thresholds are dynamically calculated based on heater power:

```
Excellent      : < (Power_W / 1000) × 4 kWh/day
Standard       : < (Power_W / 1000) × 6 kWh/day
Needs optimization : beyond
```

### Thresholds by Power

| Power | 🟢 Excellent | 🟡 Standard | 🟠 Needs optimization |
|-------|--------------|-------------|----------------------|
| 500W  | < 2.0 kWh    | < 3.0 kWh   | > 3.0 kWh            |
| 750W  | < 3.0 kWh    | < 4.5 kWh   | > 4.5 kWh            |
| 1000W | < 4.0 kWh    | < 6.0 kWh   | > 6.0 kWh            |
| 1200W | < 4.8 kWh    | < 7.2 kWh   | > 7.2 kWh            |
| 1500W | < 6.0 kWh    | < 9.0 kWh   | > 9.0 kWh            |
| 1800W | < 7.2 kWh    | < 10.8 kWh  | > 10.8 kWh           |
| 2000W | < 8.0 kWh    | < 12.0 kWh  | > 12.0 kWh           |
| 2500W | < 10.0 kWh   | < 15.0 kWh  | > 15.0 kWh           |
| 3000W | < 12.0 kWh   | < 18.0 kWh  | > 18.0 kWh           |

> **Note**: These thresholds are automatically calculated for **any power** entered. The values above correspond to the most common heater powers.

## 🗺️ Roadmap

### ✅ Completed (v1.0.0)

- [x] K Coefficient (W/°C) - empirical thermal loss
- [x] K/m² and K/m³ normalization
- [x] Smart insulation rating (calculated, inferred, or conserved)
- [x] Season management (summer, off-season, heating season)
- [x] Automatically inferred excellent insulation (low heating + stable T°)
- [x] Last valid K conservation (off-season)
- [x] Daily energy (estimated and measured)
- [x] External HA energy counter support
- [x] Precise heat detection via power sensor (event-driven)
- [x] Real-time open window detection (event-driven)
- [x] Built-in Lovelace card (auto-registered)
- [x] Data persistence
- [x] Energy performance vs national average
- [x] Utility Meter counter (midnight-to-midnight reset)
- [x] Modifiable options with auto-reload
- [x] Multi-zones (add/remove rooms)
- [x] Event-driven architecture (instant reactivity)

### 🔜 v1.1 - Visualization

- [ ] K coefficient historical graphs (ApexCharts)
- [ ] Multi-zone comparison in a single card
- [ ] Performance evolution over time

### 🔮 v1.2 - Alerts & Notifications

- [ ] Open window notifications (push, TTS)
- [ ] Poor insulation detected alerts
- [ ] Weekly consumption report

### 💡 Future Ideas

- [ ] Weather correction (wind, sunlight)
- [ ] Humidity module (RH, mold risk)
- [ ] Air quality module (CO2)
- [ ] Thermal comfort module (PMV/PPD)
- [ ] Data export (CSV, InfluxDB)
- [ ] Native HA Energy Dashboard integration
- [ ] Automatic heater detection
- [ ] Guided "insulation diagnostic" mode

## 🤝 Contributing

Contributions are welcome! Open an issue to discuss before submitting a PR.

## 📄 License

[MIT](LICENSE)
