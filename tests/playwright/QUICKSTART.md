# Quick Start Guide - Playwright Tests

This guide helps you get the Playwright tests running quickly using `uv` (the modern Python package manager).

## Prerequisites

- Python 3.10+ installed
- `uv` package manager installed: `pip install uv`

## TL;DR - Just Run the Tests

```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[test]"
python tests/playwright/run_tests.py --install-browsers
```

## Step by Step Setup

### 1. Install Dependencies
```bash
# Create virtual environment (required for uv)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Option A: Install with test dependencies
uv pip install -e ".[test]"

# Option B: Install manually
uv pip install playwright pytest pytest-playwright pytest-asyncio
```

### 2. Install Browsers
```bash
# Install Chromium (recommended)
python -m playwright install chromium

# Or use the test runner to do it automatically
python tests/playwright/run_tests.py --install-browsers
```

### 3. Validate Setup
```bash
python tests/playwright/validate_setup.py
```

### 4. Run Tests
```bash
# Run all tests
pytest tests/playwright/

# Or use the test runner
python tests/playwright/run_tests.py

# Run with visible browser (for debugging)
python tests/playwright/run_tests.py --headed
```

## What the Tests Cover

- **Authentication**: Login, signup, form validation, session management
- **Chat Interface**: Message input, send functionality, UI controls
- **Navigation**: Menu interactions, responsive design, theme switching
- **Error Handling**: Form validation, network errors, JavaScript errors

## Common Issues

### Browser Installation Fails
```bash
# Try installing system dependencies first
python -m playwright install-deps
python -m playwright install chromium

# If download fails due to network issues, try:
# 1. Check your internet connection
# 2. Try again later (servers may be temporarily unavailable)
# 3. Use different network (corporate firewalls may block downloads)

# Alternative: Install only what you need
python -m playwright install chromium --force
```

### Virtual Environment Issues
```bash
# Make sure uv is installed and virtual environment is activated
pip install uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Verify activation
which python  # Should show .venv path
```

### Tests Timeout or Fail
- Try running with `--headed` to see what's happening
- Check if the test server starts properly
- Ensure no other services are using port 8001

### Permission Errors
- Make sure you have write permissions in the test directory
- The tests create temporary files and databases

## CI/CD Integration

Add to your GitHub Actions or CI pipeline:

```yaml
- name: Setup Python and uv
  run: |
    pip install uv
    uv venv
    source .venv/bin/activate

- name: Install Playwright
  run: |
    uv pip install -e ".[test]"
    python -m playwright install chromium

- name: Run Playwright Tests  
  run: |
    source .venv/bin/activate
    pytest tests/playwright/ --browser=chromium
```

## Getting Help

- Check the full README: `tests/playwright/README.md`
- Run setup validation: `python tests/playwright/validate_setup.py`
- Use headed mode to debug: `--headed`
- Check test logs and screenshots on failure