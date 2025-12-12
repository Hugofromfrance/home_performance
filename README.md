# Thermal Learning

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/Hugofromfrance/thermal_learning.svg)](https://github.com/Hugofromfrance/thermal_learning/releases)

A Home Assistant integration that learns the thermal characteristics of your home.

## ⚠️ Work in Progress

This integration is currently in early development (MVP). Use at your own risk.

## Features (MVP)

- **Thermal loss coefficient (G)**: Measures heat loss per degree of temperature difference
- **Thermal inertia (τ)**: How long your room takes to heat up
- **Time to target**: Estimated time to reach your setpoint
- **Window open detection**: Detects rapid temperature drops
- **Learning status**: Indicates when the model has enough data

## Requirements

- Home Assistant 2024.1.0 or newer
- Temperature sensor (indoor)
- Temperature sensor (outdoor)
- Climate entity OR switch controlling your heating

## Installation

### HACS (Recommended)

1. Open HACS
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add `https://github.com/Hugofromfrance/thermal_learning` with category "Integration"
6. Click "Install"
7. Restart Home Assistant

### Manual

1. Copy `custom_components/thermal_learning` to your `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Thermal Learning"
4. Follow the configuration steps

## Roadmap

- [ ] MVP: Basic learning (G, τ, time_to_target)
- [ ] Multi-zone support
- [ ] Weather integration (wind, sun correction)
- [ ] Preheat scheduling service
- [ ] Insulation score with benchmarks
- [ ] Scenario simulation

## Contributing

Contributions are welcome! Please open an issue first to discuss what you would like to change.

## License

[MIT](LICENSE)