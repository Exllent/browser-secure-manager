# Secure Browser Sessions

A Python desktop application for managing isolated browser sessions through a GUI.

The app lets you create browser session records, launch browsers with separate profiles, store configuration in SQLite, manage browser executables, and manage proxy lists.

## Features

- PySide6 GUI.
- Browser session list management.
- Separate browser profile path per session.
- Support for Chrome/Chromium-based browsers, Firefox, and Safari.
- Configurable browser executables.
- Proxy import from CSV.
- HTTP, SOCKS4, and SOCKS5 proxy support.
- Asynchronous proxy testing with `QThreadPool`.
- Bulk removal of failed proxies and proxies with ping greater than 500 ms.
- SQLite persistence with a dedicated storage layer.
- Clear separation between GUI, application logic, and browser backend.

## Safety Scope

This project does not implement:

- anti-detect features;
- anti-bot bypasses;
- Selenium hiding;
- browser fingerprint spoofing;
- `navigator.*`, canvas, or WebGL spoofing;
- device, OS, or browser engine impersonation.

The supported behavior is limited to regular browser launches with separate profiles, window settings, User-Agent as a normal launch setting, and proxy configuration.

## Architecture

```text
secure_browser/
├── main.py
├── app/
│   └── app_service.py
├── browser_backends/
│   ├── base.py
│   └── selenium_backend.py
├── db/
│   └── storage.py
├── gui/
│   ├── app_settings_dialog.py
│   ├── main_window.py
│   └── session_row_widget.py
├── models/
│   ├── browser_config.py
│   ├── proxy_config.py
│   └── session_entry.py
└── services/
    └── proxy_tester.py
```

### Layers

`gui/`

User interface. It should not directly use SQLite, Selenium, or webdriver APIs.

`app/`

Application/business logic. The GUI communicates with `AppService`.

`browser_backends/`

Browser backend interface and implementations. The current implementation uses Selenium.

`db/`

SQLite storage layer.

`services/`

Supporting business logic, such as proxy testing.

## Replacing Selenium

Selenium is isolated in:

```text
browser_backends/selenium_backend.py
```

To replace Selenium with another library, create a new backend implementing the interface from:

```text
browser_backends/base.py
```

Then change the backend composition in `main.py`:

```python
app_service = AppService(MyBrowserBackend())
```

The GUI and core application logic should not need to change.

## Installation

Python 3.12+ is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

On Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .
```

## Running

```bash
python main.py
```

Or, after installing the package in editable mode:

```bash
secure-browser-gui
```

For console logs:

```bash
secure-browser
```

## Browser Configuration

Open:

```text
Application Settings -> Browsers
```

You can:

- auto-detect installed browsers;
- add a browser manually;
- choose an engine type:
  - `Chromium-based`;
  - `Firefox`;
  - `Safari`;
- specify a browser executable path.

For Opera and other Chromium-based browsers, use:

```text
Chromium-based
```

## Safari

Safari is supported only on macOS through `safaridriver`.

Before using Safari WebDriver on macOS, you usually need to run:

```bash
safaridriver --enable
```

Safari limitation: `safaridriver` does not support a separate `user-data-dir` or `profile_path` per session in the same way Chrome and Firefox do.

## Session Settings

Each row on the main screen contains:

- id;
- name;
- status;
- action buttons.

Advanced settings are available in the session settings dialog:

- `General`: start URL and browser;
- `Profile`: profile path;
- `Proxy`: selected saved proxy;
- `Window`: width and height;
- `User-Agent`: custom User-Agent;
- `Notes`: comments.

## Proxies

Open:

```text
Application Settings -> Proxies
```

Supported proxy types:

- HTTP;
- SOCKS4;
- SOCKS5.

Each proxy has:

- name;
- host/IP;
- port;
- protocol;
- username;
- password;
- enabled flag.

Proxy testing runs asynchronously, so the GUI should remain responsive.

Result colors:

- under 200 ms: green;
- 200-500 ms: yellow;
- over 500 ms: red;
- error: red.

Available bulk actions:

- select all proxies;
- clear all proxy checkboxes;
- remove proxies with errors;
- remove proxies with ping greater than 500 ms.

## Importing Proxies from CSV

In the `Proxies` section, click:

```text
Load CSV
```

Supported columns:

- `ip`, `host`, `address`;
- `port`;
- `protocols`, `protocol`, `type`;
- `username`, `user`, `login`;
- `password`, `pass`;
- `country`, `label`, `name`.

Example:

```csv
ip,country,port,protocols
109.135.16.145,BE,49879,socks4
```

After import, proxy tests are started asynchronously.

## Local Data

The app creates:

```text
sessions.sqlite3
profiles/
```

These files are excluded from git through `.gitignore`.

## Code Check

```bash
python -m compileall -f main.py app browser_backends models db services gui
```

## Dependencies

See [pyproject.toml](pyproject.toml).

Main dependencies:

- PySide6;
- Selenium.
