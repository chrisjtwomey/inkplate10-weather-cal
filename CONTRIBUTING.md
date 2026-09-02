# Contributing to Inkplate 10 Weather Calendar

Thank you for your interest in contributing! This document explains how to run the project from source, make changes, and test your contributions.

For end-user setup and deployment, start with [README.md](README.md).
For server-specific API and configuration reference, see [server/README.md](server/README.md).

## Server Development Setup

You can run the server directly with Python for development or advanced usage:

```sh
git clone https://github.com/chrisjtwomey/inkplate10-weather-cal.git
cd inkplate10-weather-cal
python3 -m pip install -r server/requirements.txt
cp server/config.example.yaml server/config.yaml
# Edit server/config.yaml and fill in your API keys, map ID, and location
cd server
python3 server.py
```

- The server listens on the port configured in `config.yaml` (default `8080`).
- For development, you can regenerate the PNG once and exit (no HTTP server):

```sh
cd server && python3 server.py --once
# Output: server/views/calendar.png
```

- For production deployment and advanced server configuration, see [server/README.md](server/README.md).

### Server Automated Tests

The server has tests under `tests/`. Run them from the `server` directory with `pytest`:

```sh
cd server
pytest
```

### Running Locally with Chrome/Selenium

The server uses Selenium + Chrome to render HTML templates into PNGs. When running locally, you may need to set the `CHROME_BIN` environment variable:

### macOS
```sh
export CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# or, if using Chromium via Homebrew:
# export CHROME_BIN="/Applications/Chromium.app/Contents/MacOS/Chromium"
```

### Linux
```sh
sudo apt install chromium chromium-driver   # Debian/Ubuntu
export CHROME_BIN="/usr/bin/chromium"
```

### Windows
```powershell
$env:CHROME_BIN = "C:\Program Files\Google\Chrome\Application\chrome.exe"
```

## Client Firmware Development (PlatformIO)

Use this workflow when developing firmware changes for the client.

### Choose your configuration mode

- No SD card mode: copy `src/defaults.example.cpp` to `src/defaults.cpp`, then edit `src/defaults.cpp`.
- SD card mode: use `release_sdcard` and put `config.yaml` on the SD card root (see [doc/config.yaml](doc/config.yaml)).

### Build, flash, and monitor

Build and flash a debug build:

```sh
pio run -e debug -t upload
```

Watch serial logs while iterating:

```sh
pio device monitor -b 115200
```

Build release variants before final validation:

```sh
# No SD card release build
pio run -e release

# SD card release build
pio run -e release_sdcard
```

`platformio.ini` firmware environments:

| Environment | Use |
|---|---|
| `debug` | Verbose serial logging (`LOG_LEVEL=5`). Use during development. |
| `release` | Minimal logging (`LOG_LEVEL=4`). Use for day-to-day deployment. |
| `release_sdcard` | Release build with `USE_SDCARD` enabled. Used for SD card configuration mode. |

### Automated Tests

The client firmware and its tests live in
[epd](https://github.com/chrisjtwomey/epd). This repo keeps only
`src/main.cpp` (which board to use) and `src/defaults.cpp` (credentials and
server URL), so there is no client test suite here.

To run the client tests, clone epd beside this repo and run them there.
No device is needed — all three environments are host-only:

```sh
cd ../epd/firmware
pio test -e native              # back-off, battery, refresh header parsing
pio test -e native_mock         # display + sleep against MockBoard
pio test -e native_integration  # the full run_app() control flow
```

The server test suite still lives here:

```sh
cd server && pytest
```

Building firmware from this repo needs epd checked out alongside it,
because `lib_deps` points at `symlink://../epd/firmware`.


## Making Changes

- Please fork the repository and create a new branch for your changes.
- Follow the existing code style and conventions.
- Update or add documentation as needed.
- Follow the policy in the [AI-Assisted Code](#ai-assisted-code) section when AI tools are used.

## AI-Assisted Code

If your change was written by an AI tool (such as GitHub Copilot, Claude, or similar), add a `Co-authored-by` trailer in your commit message to acknowledge AI assistance.

Example commit message:

```
Add new feature X

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## Submitting Pull Requests

- Ensure your changes build and pass tests.
- Open a pull request with a clear description of your changes.
- Reference any related issues.

Thank you for helping improve this project!
