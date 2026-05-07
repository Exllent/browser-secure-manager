# Secure Browser

Python 3.12 desktop app for managing isolated Chromium-based browser sessions from a
PySide6 GUI.

The app stores session metadata in SQLite, keeps a separate browser profile directory per
session, launches browser sessions in child processes, and applies saved browser, proxy,
window, and fingerprint settings at startup.

## Features

- PySide6 desktop GUI for session management.
- SQLite persistence in `sessions.sqlite3`.
- Per-session Chromium profile directories under `profiles/session_<id>`.
- Chromium-family browser discovery for Chrome, Chromium, Brave, Edge, Vivaldi, and Opera.
- Selenium-backed browser launch behind a `BrowserBackend` interface.
- Child-process session runtime so Selenium startup does not block the GUI thread.
- HTTP, SOCKS4, and SOCKS5 proxy records with async proxy testing.
- CSV proxy import and bulk proxy cleanup.
- Application-level fingerprint profiles selected per session.
- Fingerprint patches for user agent, client hints, languages, platform, canvas, WebGL,
  WebGPU, audio, fonts, ClientRects, workers, geolocation, WebRTC policy, and
  automation/headless indicators.
- Per-session logs plus application and error log export.
- JSON backup import/export for sessions and application records.
- Profile cache retention controls for deleted session profiles.
- English source UI with Russian Qt translation files.

## Limits

- Browser support is Chromium-based only.
- Runtime settings are applied when a session starts. Already-running sessions must be
  stopped and launched again to receive changed settings.
- TLS fingerprints are metadata in the app unless an external browser or proxy stack applies
  them. Selenium does not replace Chromium's TLS stack.
- Backups include persisted app records only. Browser profile directories, logs, virtualenvs,
  and other runtime artifacts are not included.

## Project Layout

```text
secure_browser/
├── main.py
├── app_config.py
├── app/
│   ├── app_service.py
│   ├── fonts.py
│   ├── i18n.py
│   ├── i18n_strings.py
│   ├── logging_config.py
│   └── session_process.py
├── browser_backends/
│   ├── base.py
│   ├── browser_discovery.py
│   ├── chromium_bookmarks.py
│   ├── chromium_extensions.py
│   ├── selenium_backend.py
│   └── fingerprint/
│       ├── audio.py
│       ├── canvas.py
│       ├── client_rects.py
│       ├── chromium.py
│       ├── content_filter.py
│       ├── device.py
│       ├── features_detection.py
│       ├── fonts.py
│       ├── geolocation.py
│       ├── headless.py
│       ├── media_devices.py
│       ├── navigator.py
│       ├── speech_voices.py
│       ├── templates.py
│       ├── user_agent.py
│       ├── utils.py
│       ├── webgl.py
│       ├── webgpu.py
│       ├── workers.py
│       └── js/
├── browser_extensions/
│   └── webrtc_leak_prevent/
├── db/
│   ├── backups.py
│   ├── browsers.py
│   ├── config.py
│   ├── fingerprints.py
│   ├── mappers.py
│   ├── profile_cache.py
│   ├── proxies.py
│   ├── schema.py
│   ├── sessions.py
│   ├── settings.py
│   └── storage.py
├── docs/
│   └── fingerprint_boundaries.md
├── gui/
│   ├── app_settings_dialog.py
│   ├── browser_config_row.py
│   ├── fingerprint_config_dialog.py
│   ├── fingerprint_profile_row.py
│   ├── main_window.py
│   ├── proxy_config_row.py
│   ├── proxy_csv.py
│   ├── session_row_widget.py
│   ├── session_settings_dialog.py
│   └── session_status.py
├── models/
│   ├── browser_config.py
│   ├── fingerprint_config.py
│   ├── fingerprint_generator.py
│   ├── fingerprint_profile.py
│   ├── fingerprint_summary.py
│   ├── proxy_config.py
│   └── session_entry.py
├── services/
│   └── proxy_tester.py
├── tests/
└── translations/
    ├── app_ru.ts
    └── app_ru.qm
```

## Architecture

`gui/` contains widgets and dialogs only. GUI code talks to `AppService`; it should not call
SQLite, Selenium, webdriver, or CDP directly.

`app/` coordinates application workflows. `AppService` validates selected records, starts and
stops session processes, exports logs, imports backups, and exposes CRUD methods to the GUI.

`app/session_process.py` owns the multiprocessing session runner. Browser launches happen in
child processes using the `spawn` context.

`browser_backends/` contains the browser backend protocol, Selenium implementation, browser
discovery, Chromium profile preparation, extension setup, and fingerprint startup logic.

`browser_backends/fingerprint/` contains focused Python builders and JavaScript templates for
browser-side fingerprint patches. Stable JavaScript bodies live in
`browser_backends/fingerprint/js/`.

`db/` owns SQLite schema, migrations, mappers, CRUD modules, profile cache cleanup, and JSON
backup import/export. `db/storage.py` is a compatibility facade.

`models/` contains dataclasses and validation. `services/` contains supporting business logic,
currently proxy testing.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .
```

For development with the locked toolchain:

```bash
uv sync --dev
```

## Run

From the repository:

```bash
python main.py
```

After editable installation:

```bash
secure-browser-gui
```

Console script:

```bash
secure-browser
```

## Browser Setup

Open `Application Settings -> Browsers`.

You can scan for installed Chromium-family browsers or add a browser manually. Browser records
store a display name, enabled flag, Chromium browser type, and executable path. If discovery
does not find Brave, Edge, Vivaldi, Opera, Chrome, or Chromium, add the executable path
manually.

## Session Settings

Each session has:

- start URL;
- selected browser;
- profile path;
- selected proxy;
- selected fingerprint profile;
- window width and height;
- notes.

Status values stored in SQLite are machine values:

```text
idle
starting
running
stopped
error
```

The GUI renders localized labels separately.

## Fingerprints

Open `Application Settings -> Fingerprints` to create, generate, inspect, edit, enable, or
delete fingerprint profiles. A session only selects an existing fingerprint profile;
individual fingerprint fields are edited in application settings.

Fingerprint profiles are saved as JSON in SQLite and validated before persistence. Canvas
noise uses a saved seed so tabs in the same session keep the same canvas signature.

Chromium startup applies fingerprint settings through:

- Chromium command-line options and preferences;
- CDP overrides where Chromium supports them;
- a generated per-profile extension loaded at startup;
- JavaScript templates injected at document start and into supported new tabs/frames.

## Proxies

Open `Application Settings -> Proxies`.

Supported proxy types:

- HTTP;
- SOCKS4;
- SOCKS5.

Proxy testing opens a tunnel to `browserleaks.com:443` and verifies a TLS response. GUI proxy
tests run through `QThreadPool`, so the main window remains responsive.

CSV import accepts common columns such as `ip`, `host`, `address`, `port`, `protocol`,
`protocols`, `type`, `username`, `user`, `login`, `password`, `pass`, `country`, `label`, and
`name`.

## Backups

Backups are JSON files with format marker `secure_browser_backup` and version `1`.

Full backup import replaces persisted sessions, browser configs, proxy configs, fingerprint
profiles, and app settings. Session backup import adds one session plus the related browser,
proxy, and fingerprint records used by that session.

Imported sessions are restored with `idle` status. Running process state is never backed up.

## Local Data

Runtime artifacts are local and should not be committed:

```text
sessions.sqlite3
profiles/
logs/
.venv/
.idea/
__pycache__/
.codex
```

Session logs are written under `logs/sessions/`. Application logs use `logs/secure_browser.log`
and `logs/secure_browser_errors.log`.

## Localization

English is the source/default UI language. Russian translation files are tracked in
`translations/app_ru.ts` and `translations/app_ru.qm`.

Compile translations after editing `.ts` files:

```bash
pyside6-lrelease translations/app_*.ts
```

## Development Checks

Format:

```bash
uv run black .
```

Lint and import order:

```bash
uv run ruff check . --fix
```

Run tests:

```bash
python -m unittest discover
```

Syntax check:

```bash
python -m compileall app browser_backends db gui models services tests
```

Focused tests:

```bash
python -m unittest tests.test_fingerprint_config
python -m unittest tests.test_fingerprint_generator
python -m unittest tests.test_fingerprint_storage
python -m unittest tests.test_backup_storage
python -m unittest tests.test_profile_cache
python -m unittest tests.test_selenium_fingerprint_script
python -m unittest tests.test_chromium_bookmarks
```

## Dependencies

Runtime dependencies are declared in `pyproject.toml`:

- PySide6;
- Selenium;
- websocket-client.

Development tools:

- Black;
- Ruff.
