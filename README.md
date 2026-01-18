# Home Performance

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/Hugofromfrance/home_performance.svg)](https://github.com/Hugofromfrance/home_performance/releases)
[![Tests](https://github.com/Hugofromfrance/home_performance/actions/workflows/tests.yml/badge.svg)](https://github.com/Hugofromfrance/home_performance/actions/workflows/tests.yml)
[![Liberapay](https://img.shields.io/liberapay/goal/Hugofromfrance.svg?logo=liberapay)](https://liberapay.com/Hugofromfrance/donate)

A Home Assistant integration to analyze and monitor the thermal performance of your home.

---

## 📑 Table of Contents

- [Why Home Performance?](#-why-home-performance)
- [Main Features](#-main-features)
- [Installation](#-installation)
- [Hardware Compatibility](#-hardware-compatibility)
- [Concept](#-concept)
- [Created Sensors](#-created-sensors-per-zone)
- [Multi-zones](#-multi-zones)
- [Lovelace Card](#-built-in-lovelace-card)
- [Clearing Card Cache](#clearing-the-card-cache)
- [Temperature Units](#️-temperature-units-celsiusfahrenheit)
- [Prerequisites](#-prerequisites)
- [Configuration](#️-configuration)
- [Data Persistence](#-data-persistence)
- [Usage](#-usage)
- [Dashboard Examples](#-dashboard-examples)
- [Energy Performance](#-energy-performance)
- [Roadmap](#️-roadmap)
- [Support](#-support)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🤔 Why Home Performance?

You have a heating system and wonder:
- **"Is my room well insulated?"** → Measured K coefficient
- **"How much do I actually consume?"** → Daily energy
- **"Did I forget to close a window?"** → Automatic detection
- **"Which room costs the most?"** → Multi-zone comparison

**Home Performance** answers these questions by analyzing your **real** heating data, without theoretical calculations. Works with electric heaters, heat pumps, gas boilers, and gas furnaces!

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

<img width="509" height="702" alt="image" src="https://github.com/user-attachments/assets/34ddaf7b-b39b-40ac-bd04-09be47520204" />

## 📦 Installation

### HACS (Recommended)

1. Open HACS
2. Click on "Integrations"
3. Search for **"Home Performance"**
4. Click "Download"
5. Restart Home Assistant

### Manual

1. Copy `custom_components/home_performance` to your `config/custom_components/` folder
2. Restart Home Assistant

## 🔌 Hardware Compatibility

**The integration is 100% hardware agnostic!** It works with anything that exposes standard Home Assistant entities.

### Minimum Requirements

| Need | Compatible examples |
|------|---------------------|
| Indoor temp sensor | Aqara, Sonoff SNZB-02, Xiaomi, Netatmo, Ecobee, Shelly H&T, ESPHome... |
| Outdoor temp sensor | Local weather station, Weather services, Netatmo Outdoor... |
| Heating entity | Any `climate.*`, `switch.*`, `input_boolean.*` or `binary_sensor.*` |

### Optional (recommended)

| Sensor | Examples | Benefit |
|--------|----------|---------|
| Instant power | Shelly Plug S, TP-Link, Tuya, Sonoff POW, NodOn | Precise heating time |
| Energy counter | HA Utility Meter, native counter | Measured vs estimated energy |

### Supported Heat Source Types

The integration supports **4 heat source types**:

| Heat Source | `heater_power` | `energy_sensor` | Best for |
|-------------|----------------|-----------------|----------|
| **Electric** (default) | Required | Optional | Radiators, convectors, underfloor heating |
| **Heat pump** | Optional | Optional | PAC, air-to-air, air-to-water |
| **Gas Boiler** | Optional | Optional | European-style gas boilers (water heating), central heating |
| **Gas Furnace** | Optional | Optional | US-style gas furnaces (forced air heating) |

### ⚡ Energy Source Priority

The K coefficient calculation uses energy data from the most accurate available source:

| Priority | Source | Accuracy | Use case |
|----------|--------|----------|----------|
| 1️⃣ | `energy_sensor` | ⭐⭐⭐ Best | Smart energy meter (kWh) - actual consumption |
| 2️⃣ | `power_sensor` | ⭐⭐ Good | Real-time power (W) integrated over time |
| 3️⃣ | `heater_power` | ⭐ Basic | Declared power × heating time (estimation) |

> **💡 Tips**:
> - For **best accuracy**, use an energy meter (smart plug with energy tracking, smart gas meter, etc.)
> - For **gas/heat pump without smart meter**, you can use [PowerCalc](https://github.com/bramstroker/homeassistant-powercalc) to create an energy sensor from a power estimate
> - If you only have `heater_power`, the integration will still work but with estimated energy

### Heating System Compatibility

| Type | Compatible? | Notes |
|------|-------------|-------|
| Radiator + smart plug | ✅ | Electric - ideal with power measurement |
| Radiator + pilot wire | ✅ | Electric - NodOn, Qubino, etc. |
| Convector with thermostat | ✅ | Electric - via switch or climate |
| Heat pump / AC | ✅ | Heat pump - energy sensor recommended |
| Electric underfloor heating | ✅ | Electric - with power sensor |
| Gas boiler (Europe) | ✅ | Gas Boiler - energy sensor recommended |
| Gas furnace (US) | ✅ | Gas Furnace - energy sensor recommended |

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

#### K Stability Across Weather Conditions

The K coefficient is a **physical constant** of your room's insulation. It measures heat loss **per degree of temperature difference**, so it should remain stable regardless of outdoor temperature.

| Weather | ΔT | Daily Energy | K Coefficient |
|---------|-----|--------------|---------------|
| Mild (10°C outside, 20°C inside) | 10°C | 5 kWh | **5.0 W/°C** |
| Cold (-2°C outside, 20°C inside) | 22°C | 11 kWh | **5.0 W/°C** |

➡️ You'll consume more energy when it's cold, but **your insulation rating should stay the same**.

**Why might K slightly vary in practice?**

| Factor | Impact |
|--------|--------|
| **Thermal bridges** | More apparent in extreme cold |
| **Air infiltrations** | Increase with wind (often stronger in winter) |
| **Material behavior** | Some insulation loses efficiency at very low temperatures |
| **Condensation** | Moisture can temporarily degrade insulation |

> **Tip**: If you notice a significant drop in your insulation rating during cold spells, it may reveal thermal bridges, air leaks around windows/doors, or sealing issues. This is the value of empirical measurement!

## 📊 Created Sensors (per zone)

### Thermal Coefficients

| Sensor | Description |
|--------|-------------|
| **K Coefficient** | Thermal loss (W/°C) - lower is better |
| **K per m²** | Normalized by surface - comparable between rooms |
| **K per m³** | Normalized by volume - better if different heights |
| **Insulation Rating** | Smart: calculated, inferred, or conserved depending on season |

### 🎯 Smart Insulation Rating

The insulation rating is calculated over a **7-day rolling window** for stability. This prevents rating changes at midnight and smooths out anomalous days (open window, guests, etc.).

The rating automatically adapts to all situations:

| Situation | Display | Description |
|-----------|---------|-------------|
| K calculated | **A to G** | Rating based on K/m³ coefficient |
| Low heating + stable T° | **🏆 Excellent (inferred)** | Excellent insulation automatically inferred |
| Summer mode (T° out > T° in) | **☀️ Summer mode** | Measurement impossible + last K conserved |
| Shoulder season (ΔT < 5°C) | **🌤️ Shoulder season** | Insufficient ΔT + last K conserved |
| Data collection | **Waiting** | < 12h of data |

#### Automatically Inferred Insulation 🏆

If after **24h** of observation:
- ΔT is significant (≥ 5°C)
- The heater has run very little (< 30 min)
- Indoor temperature remained **stable** (variation < 2°C)

→ The integration automatically infers that insulation is **excellent**!

> **Logic**: If the room maintains its temperature without heating while it's cold outside, heat loss is very low.

#### Last Valid K Conservation

In summer or shoulder season, the integration **keeps the last calculated K coefficient** and displays it with the appropriate season message. You thus keep a useful reference all year round.

#### 🔄 Reset After Insulation Work

Completed renovation work? Changed windows? You can **reset the 7-day history** to start fresh measurements:

```yaml
# Developer Tools > Services
service: home_performance.reset_history
data:
  zone_name: "Living Room"
```

**What the reset does:**
- ✅ Clears the 7-day history
- ✅ K coefficient recalculates from new data
- ❌ Does NOT delete current day's data (no 12h wait)
- ❌ Does NOT lose last valid K (kept as reference)

#### Complete Data Reset

For a **complete reset** (after major changes like new heating equipment, insulation renovation, or to clear all anomalous data):

```yaml
# Developer Tools > Services
service: home_performance.reset_all
data:
  zone_name: "Living Room"
```

**What the complete reset does:**
- ✅ Clears ALL data (history, coefficients, energy counters)
- ✅ Resets to initial state (like a fresh install)
- ⚠️ Requires 12h of new data collection

**Timeline after reset:**

| Delay | What you see |
|-------|--------------|
| ~24h | K reflects new insulation conditions |
| ~7 days | Stable K based entirely on post-work data |

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
| **Avg ΔT (24h)** | Average indoor/outdoor difference (rolling 24h window) |

The `source` attribute on Time/Ratio indicates: `measured` (via power sensor > configured threshold) or `estimated` (via switch state).

### Status

| Sensor | Description |
|--------|-------------|
| **Data hours** | Duration of collected data (format: `Xh Ymin`) |
| **Remaining analysis time** | Time before data is ready |
| **Analysis progress** | Completion percentage (0-100%) |
| **Data ready** | Binary sensor indicating if analysis is available |
| **Heating active** | Binary sensor indicating if heating is currently running |
| **Open window** | Detection by rapid temperature drop or physical sensor |

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

The integration includes a **ready-to-use modern custom card** with multiple layout options!

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
- URL: `/home-performance/home-performance-card.js`
- Type: `JavaScript Module`

</details>

### ⚠️ Upgrading from v1.3.x or earlier

Starting with v1.4.0, the card resource URL has changed and is now **automatically managed**.

| Mode | Action Required |
|------|-----------------|
| **Storage mode** (default) | ✅ **None** - Old resource is automatically removed and new one registered |
| **YAML mode** | ⚠️ Update URL from `/home_performance/...` to `/home-performance/...` (underscore → hyphen) |

**What happens automatically:**
- Old manually-added resources (`/home_performance/home-performance-card.js`) are detected and removed
- New resource is registered with version parameter (`/home-performance/home-performance-card.js?v=X.X.X`)
- Version mismatch detection notifies you when frontend/backend versions differ

### Card Layouts

Choose the layout that fits your dashboard style:

| Layout | Description | Best for |
|--------|-------------|----------|
| `full` | Complete card with all metrics (default) | Main dashboard, detailed view |
| `badge` | Compact vertical badge with score | Grid of rooms, quick overview |
| `pill` | Horizontal strip with key info | Sidebar, compact lists |
| `multi` | All zones in one card with compare view | Multi-room overview, ranking |

#### Full Layout (default)
```yaml
type: custom:home-performance-card
zone: Living Room
layout: full
```
The complete card showing insulation rating, performance, temperatures, and detailed metrics.

<img width="449" alt="Full layout - light theme" src="https://github.com/user-attachments/assets/5e90f237-6375-4bca-ac8d-2f27ded35b6c" />

<img width="449" alt="Full layout - dark theme" src="https://github.com/user-attachments/assets/ceea3e85-8187-4913-907e-211db6273ad6" />

#### Badge Layout
```yaml
type: custom:home-performance-card
zone: Bedroom
layout: badge
```
A compact vertical card showing the score letter (A+ to D), zone name, and K coefficient. Perfect for creating a grid of all your rooms.

<img width="470" alt="Badge layout" src="https://github.com/user-attachments/assets/a03b1af9-9540-45cf-b3bc-070cf796a5ab" />

#### Pill Layout
```yaml
type: custom:home-performance-card
zone: Office
layout: pill
```
A slim horizontal bar showing score, zone name, K coefficient, and ΔT. Ideal for sidebars or compact dashboards.

<img width="483" alt="Pill layout" src="https://github.com/user-attachments/assets/3de72907-1882-47dc-9b7a-e512867cfaef" />

#### Multi-Zone Layout (NEW)
```yaml
type: custom:home-performance-card
layout: multi
default_view: list
show_sparklines: true
```
A comprehensive card that displays **all your zones in one place**. No need to specify a zone - it auto-detects all configured zones.

**Features:**
- 📋 **List View** - All zones with expandable details (click to expand)
- 🏆 **Compare View** - Ranking by K/m³ performance with percentage difference
- 🔄 **Toggle** - Switch between List and Compare views
- 📊 **Sparklines** - Mini trend graphs for each zone
- 🎯 **Average Score** - Overall home performance at a glance

**Multi-Zone Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `default_view` | "list" | Initial view: `list` or `compare` |
| `show_sparklines` | true | Show/hide mini trend graphs |

### Card Options

| Option | Default | Description |
|--------|---------|-------------|
| `zone` | *required** | Exact name of your zone |
| `title` | "Thermal Performance" | Displayed title (full layout only) |
| `layout` | "full" | Card style: `full`, `badge`, `pill`, or `multi` |
| `show_graph` | true | Show/hide the historical K graph |
| `demo` | false | Demo mode with fake data |
| `default_view` | "list" | Multi-zone only: initial view (`list` or `compare`) |
| `show_sparklines` | true | Multi-zone only: show mini trend graphs |

*\* Not required for `layout: multi` (auto-detects all zones)*

### Card Features

- 📊 **Visual scores** - Insulation rating from A+ to D with colors
- 📈 **Historical K graph** - 7-day history with bar chart (full) or sparkline (badge/pill)
- 🌡️ **Temperatures** - Indoor/Outdoor in real-time
- 📉 **Detailed metrics** - K coefficient, Energy, Heating time
- 💨 **Wind data** - Current wind speed, direction and room exposure (full/badge/multi layouts)
- ⏳ **Progress** - Progress bar during initial analysis
- 🎨 **Adaptive design** - Adapts to light/dark theme
- 🎛️ **Visual editor** - Choose layout directly in the UI

### Clearing the Card Cache

After updating the integration, your browser may still display the old card version due to caching.

#### Automatic Version Mismatch Detection 🆕

The card now **automatically detects version mismatches** between the frontend card and the backend integration. If a mismatch is detected, a notification will appear with a **"Reload"** button that clears the cache and refreshes the page.

> **Note**: The resource URL now includes an automatic version parameter (`?v=X.X.X`) that updates with each integration update.

#### Manual Cache Clearing

If you need to manually clear the cache:

**Method 1: Hard Refresh (Quick)**
- **Windows/Linux**: `Ctrl + Shift + R` or `Ctrl + F5`
- **Mac**: `Cmd + Shift + R`

**Method 2: Clear Browser Cache**
1. Open Developer Tools (`F12`)
2. Right-click the refresh button → "Empty Cache and Hard Reload"

**Method 3: Mobile Companion App**
- Go to app settings → Clear cache, or force-stop the app

#### Verify Card Version
Open the browser console (`F12` → Console tab) and look for:
```
HOME-PERFORMANCE v1.3.0
```

If you see an older version, the cache hasn't been cleared yet.

### Historical K Graph

The card displays a **7-day history** of your K coefficient score:

| Layout | Graph type | Description |
|--------|------------|-------------|
| `full` | Bar chart | Colored bars showing score evolution (height = K value, color = rating) |
| `badge` | Sparkline | Minimal trend line |
| `pill` | Sparkline | Minimal trend line |

**Features:**
- 🎨 **Color-coded** - Each bar/point colored by its insulation rating (A+ green → D red)
- 📅 **Daily K_7j** - Shows the rolling 7-day average you had each day (not daily fluctuations)
- 🔮 **Estimated days** - Days without sufficient data show estimated values (semi-transparent)

**Disable the graph:**
```yaml
type: custom:home-performance-card
zone: Living Room
layout: pill
show_graph: false
```

## 🌡️ Temperature Units (Celsius/Fahrenheit)

The integration **automatically supports both Celsius and Fahrenheit** based on your Home Assistant unit system configuration.

### How It Works

| Component | Unit used |
|-----------|-----------|
| **Internal calculations** | Always Celsius (standardized) |
| **K coefficient** | Always W/°C (scientific standard) |
| **Temperature display** | Your HA system preference (°C or °F) |

### Why K stays in W/°C?

The K coefficient measures thermal loss in **Watts per degree Celsius**. This is the international scientific standard, ensuring:
- Consistent comparison between users worldwide
- Compatibility with building industry standards
- No confusion with rating thresholds

> **Note**: If your temperature sensors report in Fahrenheit, the integration automatically converts them to Celsius for calculations, then converts back to Fahrenheit for display.

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
| Heat source type | Electric, Heat pump, Gas Boiler, or Gas Furnace |
| Heater power | Declared power in Watts (required for Electric, optional for others) |

### Optional Parameters

| Parameter | Description |
|-----------|-------------|
| Surface | m² (for K/m²) |
| Volume | m³ (for K/m³ and insulation rating) |
| Power sensor | sensor.xxx_power in Watts (for energy + precise heat detection) |
| Power threshold | Detection threshold in Watts (default: 50W) |
| Energy sensor | sensor.xxx_energy (optional - most accurate for K calculation) |
| Efficiency factor | Converts consumed energy to thermal output (see below) |
| Window/Door sensor | binary_sensor.xxx (physical contact sensor for open detection) |
| Weather entity | weather.xxx (for wind data display - shared between zones) |
| Room orientation | N, NE, E, SE, S, SW, W, NW (for wind exposure calculation) |

### Efficiency Factor

The efficiency factor converts consumed energy (electricity, gas) to actual thermal output:

| Heat Source | Default | Typical Range | Description |
|-------------|---------|---------------|-------------|
| Electric | 1.0 | 1.0 | 100% efficient (all electricity → heat) |
| Heat pump | 3.0 | 2.5 - 4.5 | COP (1 kWh electric → 3 kWh heat) |
| Gas boiler | 0.90 | 0.85 - 0.95 | Condensing boilers are most efficient |
| Gas furnace | 0.85 | 0.78 - 0.90 | US-style forced air systems |

> **💡 Tips**:
> - For **heat pumps**, use your unit's actual COP (Coefficient of Performance) if known
> - For **gas systems**, check your equipment's AFUE rating and convert to decimal (e.g., 92% AFUE = 0.92)

### Configuration by Heat Source Type

#### Electric (default)
```
Heat source type: Electric
Heater power: 1500  (required - your heater's rated power in Watts)
Energy sensor: (optional - for measured vs estimated energy)
```

#### Heat Pump
```
Heat source type: Heat pump
Heater power: 17600  (optional - declared power for estimation fallback)
Energy sensor: sensor.heatpump_energy  (optional but recommended for accuracy)
```

#### Gas Boiler (European)
```
Heat source type: Gas Boiler
Heater power: 17600  (optional - declared power in Watts)
Energy sensor: sensor.gas_energy  (optional but recommended for accuracy)
Efficiency factor: 0.90  (default, condensing boilers typically 0.85-0.95)
```

#### Gas Furnace (US)
```
Heat source type: Gas Furnace
Heater power: 17600  (optional - declared power in Watts, e.g., 60,000 BTU/h = 17,600W)
Energy sensor: sensor.furnace_energy  (optional but recommended for accuracy)
Efficiency factor: 0.85  (default, typical US furnace 0.78-0.90)
```

> **Notes**:
> - For non-electric sources, the K coefficient is calculated directly from the measured energy.
> - If `heater_power` is not provided, performance thresholds are derived from observed energy/time ratio.
> - If you provide an external energy counter AND a power sensor, the external counter is used as priority for energy.
> - The power sensor also enables **precise heat detection** (power > threshold), ideal for heaters with internal thermostat or pilot wire. The threshold is configurable (default: 50W).
> - The **Window/Door sensor** allows using a physical contact sensor (window, door, opening) for accurate open detection instead of relying on temperature-based detection. If the sensor is unavailable, it falls back to temperature detection automatically.
> - The **Weather entity** enables wind data display on cards. Combined with room orientation, it calculates wind exposure (exposed/sheltered) to help understand K coefficient variations.
> - Options are **modifiable afterwards** and the integration reloads automatically.

### 📱 Window Open Notifications

Get a push notification when a window is detected open while heating is running.

| Option | Description | Default |
|--------|-------------|---------|
| Enable alerts | Turn on/off push notifications | Off |
| Mobile device | Select your phone from mobile_app devices | - |
| Delay | Minutes to wait before alerting | 2 min |

**Setup**: Settings → Integrations → Home Performance → Configure (⚙️)

The notification is translated (EN/FR/IT) based on your Home Assistant language.

> **Blueprint alternative**: A [Blueprint](blueprints/automation/home_performance/window_open_notification.yaml) is also available for advanced customization (custom messages, TTS, multiple devices...).

## 💾 Data Persistence

Data is **automatically saved** and restored after a Home Assistant restart:

- ✅ Real-time thermal data (up to 48h)
- ✅ **Long-term daily history (up to 5 years)** 📊
- ✅ Calculated K coefficient
- ✅ Energy counters
- ✅ No need to wait 12h again after each restart!

**Storage**: `/config/.storage/home_performance.{zone}`

**Save frequency**: Every 5 minutes + at HA shutdown

### Long-term History

The integration stores **daily aggregated data for up to 5 years** per zone:

| Data stored | Retention |
|-------------|-----------|
| Real-time data points | 48 hours |
| Daily summaries (K, energy, heating time, temps) | **5 years (1825 days)** |
| K_7d calculation | Always uses last 7 days |

**Storage size**: ~73 KB per zone per year (very lightweight)

This long-term history will enable future features like:
- 📈 Monthly/yearly performance graphs
- 🔄 Season-to-season comparison (Winter 2024 vs 2023)
- ⚠️ Insulation degradation detection over time

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

Thresholds are dynamically calculated based on heater power (or derived power for non-electric sources):

```
Excellent      : < (Power_W / 1000) × 4 kWh/day
Standard       : < (Power_W / 1000) × 6 kWh/day
Needs optimization : beyond
```

> **For non-electric sources**: If `heater_power` is not configured, the system derives an average power from observed `energy / heating_hours`. This allows performance evaluation even for heat pumps, gas boilers, or gas furnaces.

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

### ✅ Completed

- [x] K Coefficient (W/°C) - empirical thermal loss
- [x] K/m² and K/m³ normalization
- [x] Smart insulation rating (calculated, inferred, or conserved)
- [x] 7-day rolling history for stable insulation rating
- [x] Manual reset service (`home_performance.reset_history`)
- [x] Season management (summer, shoulder season, heating season)
- [x] Automatically inferred excellent insulation (low heating + stable T°)
- [x] Last valid K conservation (shoulder season)
- [x] Daily energy (estimated and measured)
- [x] External HA energy counter support
- [x] Precise heat detection via power sensor (event-driven)
- [x] Real-time open window detection (event-driven)
- [x] Built-in Lovelace card (auto-registered with version management) 🆕
- [x] Multiple card layouts (full, badge, pill) 🎄
- [x] Celsius/Fahrenheit automatic support
- [x] Data persistence
- [x] Energy performance vs national average
- [x] Utility Meter counter (midnight-to-midnight reset)
- [x] Modifiable options with auto-reload
- [x] Multi-zones (add/remove rooms)
- [x] Event-driven architecture (instant reactivity)
- [x] **Historical K graph** - 7-day bar chart (full) and sparkline (badge/pill) 📊
- [x] **Configurable graph display** (`show_graph` option)
- [x] **Efficiency factor** for heat pumps (COP) and gas systems
- [x] **Physical window/door sensor** support
- [x] **Multi-zone card** - All zones in one card with List/Compare views
- [x] **Long-term history** - 5 years of daily data storage
- [x] **Wind data display** - Weather entity integration with wind exposure
- [x] **Multiple heat source types** (electric, heat pump, gas boiler, gas furnace) 🔥

### 🔜 Next - Alerts & Notifications

- [x] Open window notifications (push) ✅
- [ ] Open window notifications (TTS)
- [ ] Poor insulation detected alerts
- [ ] Weekly consumption report

### 🔮 Planned - Long-term Analytics

- [ ] Monthly/yearly performance graphs (using 5-year history)
- [ ] Season-to-season comparison
- [ ] Insulation degradation detection

### 💡 Future Ideas

- [ ] BTU/h input support for US furnaces
- [ ] Weather correction (wind, sunlight)
- [ ] Humidity module (RH, mold risk)
- [ ] Air quality module (CO2)
- [ ] Thermal comfort module (PMV/PPD)
- [ ] Data export (CSV, InfluxDB)
- [ ] Native HA Energy Dashboard integration
- [ ] Automatic heater detection
- [ ] Guided "insulation diagnostic" mode

## ☕ Support

If this project helps you save energy or understand your home better, consider supporting its development:

[![Donate using Liberapay](https://liberapay.com/assets/widgets/donate.svg)](https://liberapay.com/Hugofromfrance/donate)

## 🤝 Contributing

Contributions are welcome! Please read the [Contributing Guide](CONTRIBUTING.md) before submitting a PR.

## 📄 License

[MIT](LICENSE)
