# Contributing to Home Performance

First off, thank you for considering contributing to Home Performance! 🎉

## 📑 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Coding Guidelines](#coding-guidelines)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Testing](#testing)

---

## Code of Conduct

This project follows a simple rule: **Be respectful and constructive**. We're all here to improve home automation!

---

## How Can I Contribute?

### 🐛 Reporting Bugs

Before creating a bug report, please check existing issues. When creating a report:

1. Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md)
2. Include your HA version and Home Performance version
3. Add relevant logs from **Settings → System → Logs**
4. Describe steps to reproduce

### 💡 Suggesting Features

Feature requests are welcome! Please:

1. Use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md)
2. Explain the use case
3. Check if it aligns with the project's scope (thermal performance analysis)

### 🔧 Code Contributions

Great! Here's how to get started:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test locally with Home Assistant
5. Submit a Pull Request

---

## Development Setup

### Prerequisites

- Python 3.11+
- Home Assistant (for testing)
- Git

### Local Development

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/home_performance.git
cd home_performance

# Create a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dev dependencies
pip install -r requirements_dev.txt
```

### Testing with Home Assistant

The easiest way is to use the included Docker setup:

```bash
# Start HA with your local code mounted
docker-compose -f docker-compose.dev.yml up
```

Or symlink to your HA config:

```bash
ln -s /path/to/home_performance/custom_components/home_performance /path/to/ha/config/custom_components/
```

---

## Project Structure

```
home_performance/
├── custom_components/
│   └── home_performance/
│       ├── __init__.py          # Integration setup
│       ├── config_flow.py       # Configuration UI
│       ├── coordinator.py       # Data update coordinator
│       ├── models.py            # Thermal calculation model
│       ├── sensor.py            # Sensor entities
│       ├── binary_sensor.py     # Binary sensor entities
│       ├── const.py             # Constants
│       ├── manifest.json        # Integration manifest
│       ├── strings.json         # UI strings
│       ├── translations/        # Localization
│       │   ├── en.json
│       │   └── fr.json
│       └── www/
│           └── home-performance-card.js  # Lovelace card
├── examples/                    # Dashboard examples
├── .github/                     # GitHub templates & workflows
├── README.md
├── CONTRIBUTING.md
└── LICENSE
```

---

## Coding Guidelines

### Python

- Follow [PEP 8](https://pep8.org/) style guide
- Use type hints where possible
- Keep functions focused and small
- Add docstrings for public methods

```python
async def calculate_k_coefficient(
    self,
    energy_kwh: float,
    delta_t: float,
    hours: float
) -> float | None:
    """Calculate the K coefficient for thermal loss.
    
    Args:
        energy_kwh: Energy consumed in kWh
        delta_t: Temperature difference (indoor - outdoor)
        hours: Time period in hours
        
    Returns:
        K coefficient in W/°C, or None if calculation not possible
    """
```

### JavaScript (Lovelace Card)

- Use ES6+ features
- Follow the existing code style
- Test in both light and dark themes

### Translations

When adding/modifying strings:
1. Update `strings.json` (English, source of truth)
2. Update `translations/en.json`
3. Update `translations/fr.json` (or add a note for translation needed)

---

## Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type: description

[optional body]
```

### Types

| Type | Description | Version Bump | In Changelog |
|------|-------------|--------------|--------------|
| `feat` | ✨ New feature | Minor (1.0.0 → 1.1.0) | ✅ Yes |
| `fix` | 🐛 Bug fix | Patch (1.0.0 → 1.0.1) | ✅ Yes |
| `perf` | ⚡ Performance improvement | Patch | ✅ Yes |
| `refactor` | ♻️ Code refactoring | Patch | ✅ Yes |
| `docs` | 📚 Documentation only | Patch | ✅ Yes |
| `style` | 💄 Code style (formatting) | Patch | ✅ Yes |
| `test` | ✅ Adding/updating tests | None | ❌ Hidden |
| `chore` | 🔧 Maintenance tasks | None | ❌ Hidden |
| `ci` | 👷 CI/CD changes | None | ❌ Hidden |

### Breaking Changes

For breaking changes, add `!` after the type or include `BREAKING CHANGE:` in the body:

```bash
feat!: change configuration format
# Results in Major bump: 1.0.0 → 2.0.0
```

### Examples

```bash
feat: add humidity sensor support
fix: correct heating time calculation
perf: optimize data refresh cycle
refactor: simplify K coefficient calculation
docs: add installation instructions
style: format code with black
chore: update dependencies
ci: add automated tests workflow
```

---

## Pull Request Process

### Before Submitting

- [ ] Code follows the project style
- [ ] Self-review completed
- [ ] Changes tested locally with HA
- [ ] Documentation updated if needed
- [ ] Translations updated if adding strings

### PR Requirements

1. **Title**: Follow commit message format (`feat: add X`, `fix: correct Y`)
2. **Description**: Explain what and why
3. **Link issues**: Use `Fixes #123` or `Closes #123`
4. **Screenshots**: Include for UI changes

### Review Process

1. Automated checks must pass (HACS, Hassfest)
2. Code review by maintainer
3. Changes requested → Update PR
4. Approved → Squash and merge

---

## Testing

### Manual Testing

1. Install the integration in your HA instance
2. Configure at least one zone
3. Verify sensors are created and updating
4. Check the Lovelace card displays correctly

### What to Test

| Area | What to check |
|------|---------------|
| **Config Flow** | Add zone, modify options, delete zone |
| **Sensors** | Values update, attributes correct |
| **Card** | Display, themes, loading states |
| **Persistence** | Data survives HA restart |
| **Edge cases** | Missing sensors, unavailable entities |

---

## Branch Naming Convention

This project follows **GitFlow**. Please use the following branch naming:

| Branch Pattern | Purpose | Example |
|----------------|---------|---------|
| `feature/*` | New features | `feature/humidity-sensor` |
| `fix/*` | Bug fixes | `fix/calculation-error` |
| `docs/*` | Documentation only | `docs/update-readme` |
| `refactor/*` | Code refactoring | `refactor/simplify-models` |

### Workflow

1. Create your branch from `dev`
2. Make your changes
3. Open a PR targeting `dev`
4. After review and merge, maintainers will handle releases

---

## Questions?

Feel free to:
- Open a [Question issue](.github/ISSUE_TEMPLATE/question.md)
- Check existing issues and discussions

Thank you for contributing! 🙏

