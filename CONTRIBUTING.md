# Contributing to Inkplate 10 Weather Calendar

How to run the project from source, change it, test it and publish it. To set
up a display, start with [README.md](README.md). Every server setting is in
[server/README.md](server/README.md).

## Server Development Setup

```sh
git clone https://github.com/chrisjtwomey/inkplate10-weather-cal.git
cd inkplate10-weather-cal
python3 -m venv server/.venv && source server/.venv/bin/activate
python3 -m pip install -r server/requirements-dev.txt
cp server/config.example.yaml server/config.yaml   # then fill in the keys, the map ID and the location
cd server
python3 server.py
```

- `requirements-dev.txt` is `requirements.txt` plus the test tools.
- The server's generic code is [epd](https://github.com/chrisjtwomey/epd)'s
  `epd-server`, which `requirements.txt` pins to a release on PyPI. To work
  against an epd checkout, install it editable after the requirements, since a
  later `pip install -r` puts the pinned release back:

  ```sh
  python3 -m pip install -e ../epd/server
  ```

- `python3 server.py --once` renders the five pages into `server/views/` and
  exits, with no HTTP server.

### Tests

```sh
cd server
pytest
```

### Chrome

The server renders its pages with Chrome, through Selenium. If it cannot find
Chrome, set `CHROME_BIN`:

| System | `CHROME_BIN` |
|---|---|
| macOS | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` |
| Linux | `/usr/bin/chromium` (`sudo apt install chromium chromium-driver`) |
| Windows | `C:\Program Files\Google\Chrome\Application\chrome.exe` |

## Client Firmware Development (PlatformIO)

The firmware's settings come from `src/defaults.cpp`, which is gitignored: copy
`src/defaults.example.cpp` to it and fill it in. With an SD card, build
`release_sdcard` and put a `config.yaml` on the card: see
[doc/config.yaml](doc/config.yaml).

```sh
pio run -e debug -t upload           # build and flash
pio device monitor -b 115200         # watch the serial log
```

| Environment | Use |
|---|---|
| `debug` | Development: DEBUG log lines (`LOG_LEVEL=5`) and the core's own on serial. |
| `release` | A display without an SD card (`LOG_LEVEL=4`). |
| `release_sdcard` | A display with an SD card (`USE_SDCARD`). The releases' firmware. |
| `timing` | Test work: `release` that wakes at least every 10 minutes (`MAX_SLEEP_SECONDS`) and logs, at the next wake, when each step of the last one ended (`TIMING_LOG`). Its version ends in `+timing`. |
| `debug-dev` | `debug` against an epd checkout beside this repo, to try a change to epd before it is released. |

- The firmware's version is what `git describe` gives, from
  `scripts/version.py`: `v2.1.0` on a tag, `v2.1.0-3-g62c793c` past one.
- The board environments take epd from the PlatformIO registry, at the release
  `[epd]` in `platformio.ini` names. It must match the `epd-server` pin in
  `server/requirements.txt`: the firmware and the server share the headers.

### Automated Tests

`src/app.cpp` holds the order of one wake and every decision about how it
ends: the battery thresholds, the retries, the back-off, and when to take an
update. `src/panel.cpp` draws what goes over a page. Both are this project's,
so their tests are here, and run on the host:

```sh
pio test -e native_integration      # run_app() against MockBoard and stubs in test/test_integration/
pio test -e native_panel            # the battery icon, the update screen and its banner
```

- `pio test` with no environment does nothing: the board environments ignore
  tests. Name the environment.
- Both compile epd's sources from the registry package. `native_integration-dev`
  and `native_panel-dev` compile them from an epd checkout beside this repo.
- The steps `app.cpp` is built from are epd's, and so are their tests: see
  [epd's Tests](https://github.com/chrisjtwomey/epd/blob/main/CONTRIBUTING.md#tests).

## Coverage

```sh
pip install gcovr                       # once, into the Python that runs the script
python3 scripts/coverage_report.py      # --server or --firmware for one
```

Both figures count lines. The server's leaves out the tests. The firmware's
counts only the part of `src/` that the host tests compile, `app.cpp` and
`panel.cpp`. `main.cpp` runs only on a board, and epd's sources are measured
in epd.

On each push to main, the Coverage workflow (`.github/workflows/coverage.yaml`)
runs the script with `--badges` and writes the two figures, rounded down, to a
public gist that the README's badges read. It writes with the `GIST_TOKEN`
secret, a fine-grained token with only the Gists permission. When the token
expires, the workflow fails and the badges keep their last figures; it is
apart from PlatformIO CI, so CI still passes.

## Publishing

| Event | What it publishes |
|---|---|
| A push to main that passes CI | The server image as `latest` and as its version, such as `2.1.0-3-g62c793c`. It carries the firmware of its own version in `builds/nocard`, `builds/sdcard` and `builds/timing`. |
| A published GitHub release | The same image as `X.Y.Z` and `X.Y` too, and `firmware.bin` and `firmware.factory.bin`, the `release_sdcard` build, attached to the release. |
| A tag pushed alone | Nothing. |

- A server's `client.firmware.dir` picks which build its displays take: see
  [Firmware updates](server/README.md#firmware-updates).
- To move to a new epd: set its version in both `[epd]` in `platformio.ini` and
  `epd-server` in `server/requirements.txt`. Push only once PyPI lists the new
  `epd-server`: CI installs it, and fails before then.
- A release is for a version worth upgrading to. The work in between is tested
  on `latest`.

## Making Changes

- Fork the repository, and make your change on a branch.
- Follow the code style around it.
- Update the docs your change touches.
- Make sure it builds and the tests pass, then open a pull request that says
  what it changes and why.

## AI-Assisted Code

If an AI tool wrote your change, name it in a `Co-Authored-By` trailer in the
commit message:

```
Add new feature X

Co-Authored-By: Claude <noreply@anthropic.com>
```
