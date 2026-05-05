# Secure Browser Sessions

A cross-platform Python desktop application for managing isolated browser sessions through a PySide6 GUI.

The application stores session records in SQLite, launches browsers through a replaceable browser backend, keeps browser profile directories separate per session, and provides GUI-only localization through compiled Qt translation files.

## Safety Scope

This project intentionally does not implement:

- anti-detect features;
- anti-bot bypasses;
- Selenium hiding;
- browser fingerprint spoofing;
- `navigator.*`, canvas, or WebGL spoofing;
- device, OS, browser engine, or user impersonation.

The supported browser behavior is limited to regular launches with separate browser profiles, window size settings, optional User-Agent through fingerprint profiles, and proxy configuration.

## Features

- PySide6 desktop GUI.
- Cross-platform target: Linux, Windows, and macOS.
- Session list with per-session settings.
- Separate profile path per browser session.
- Browser configuration in application settings.
- Chromium-based browser support.
- SQLite persistence with a dedicated storage layer.
- App settings stored in SQLite.
- HTTP, SOCKS4, and SOCKS5 proxy records.
- Proxy CSV import.
- Asynchronous proxy testing with `QThreadPool`.
- Bulk proxy cleanup by failed test or ping greater than 500 ms.
- Clear separation between GUI, application logic, and browser backend.
- GUI-only localization through Django-like `_()`.
- Compiled Qt `.qm` translations.
- Runtime language switching after saving application settings.
- RTL layout direction for Arabic, Persian, and Hebrew.
- Application font fallback for multi-language UI.

## Project Structure

```text
secure_browser/
├── main.py
├── app/
│   ├── app_service.py
│   ├── fonts.py
│   ├── i18n.py
│   └── i18n_strings.py
├── browser_backends/
│   ├── base.py
│   ├── browser_discovery.py
│   ├── chromium_extensions.py
│   ├── fingerprint/
│   └── selenium_backend.py
├── db/
│   └── storage.py
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
│   ├── proxy_config.py
│   └── session_entry.py
├── services/
│   └── proxy_tester.py
└── translations/
    ├── app_ru.ts
    ├── app_ru.qm
    └── app_<language>.ts/.qm
```

## Architecture

`gui/`

User interface only. GUI code talks to `AppService` and should not directly use SQLite, Selenium, or webdriver APIs.

`app/`

Application layer. `AppService` owns business operations, coordinates storage, proxy testing, and the selected browser backend. GUI localization helpers and font configuration also live here.

`browser_backends/`

Browser backend interface and implementation. The current implementation uses Selenium.

`db/`

SQLite storage layer. It owns database schema creation and CRUD functions.

`services/`

Supporting business logic, currently proxy testing.

## Replacing Selenium

Selenium is isolated in:

```text
browser_backends/selenium_backend.py
```

To replace Selenium with another library, implement the `BrowserBackend` protocol from:

```text
browser_backends/base.py
```

Then compose the new backend in `main.py`:

```python
app_service = AppService(MyBrowserBackend())
```

The GUI and most business logic should not need to change.

## Requirements

- Python 3.12+
- PySide6
- Selenium
- Installed browser binaries for the browsers you want to launch
- WebDriver support for the selected browser

Linux users should install broad Unicode font support for the localized UI:

```bash
sudo apt update
sudo apt install fonts-noto fonts-noto-core fonts-noto-extra fonts-noto-cjk fonts-noto-color-emoji
fc-cache -f -v
```

## Installation

Linux/macOS:

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

## Running

From the repository:

```bash
python main.py
```

After editable installation:

```bash
secure-browser-gui
```

Console entry point:

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
- choose a browser engine type:
  - `Chromium-based`;
- specify a browser executable path.

For Opera, Brave, Edge, Vivaldi, and other Chromium-based browsers, use `Chromium-based` and set the executable path manually if auto-detection does not find it.

## Session Settings

The main screen shows compact session rows:

- ID;
- name;
- status;
- action buttons.

Advanced settings are in the session settings dialog:

- `General`: start URL and browser;
- `Profile`: profile path;
- `Proxy`: selected saved proxy and proxy note;
- `Fingerprint`: selected saved fingerprint profile;
- `Window`: width and height;
- `Notes`: comments.

User-Agent is configured inside application-level fingerprint settings, not in the per-session settings dialog.

Status values remain English machine values in SQLite:

```text
idle
running
stopped
error
```

The GUI displays localized status labels.

## Proxies

Open:

```text
Application Settings -> Proxies
```

Supported proxy types:

- HTTP;
- SOCKS4;
- SOCKS5.

Each proxy record has:

- row number;
- enabled checkbox;
- label;
- host/IP;
- port;
- protocol;
- username;
- password;
- test status.

Proxy testing runs asynchronously, so the GUI remains responsive.

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

## Localization

Localization is GUI-only. Business logic, storage values, exceptions, and logs stay in English.

The code uses a Django-like helper:

```python
from app.i18n import _

button.setText(_("Add session"))
```

Translation files are stored in:

```text
translations/
```

Each supported language has:

```text
app_<code>.ts
app_<code>.qm
```

The `.ts` file is the editable translation source. The `.qm` file is the compiled Qt translation used at runtime.

To compile all translations:

```bash
pyside6-lrelease translations/app_*.ts
```

Supported language codes currently include:

```text
en, ru, es, de, zh, ja, ko, fr, ar, pl, uk, vi, pt,
hi, bn, id, tr, it, nl, cs, ro, el, th, ms, fa, he,
sv, no, da, fi, hu, sr, bg
```

Language selection is available in:

```text
Application Settings -> Language
```

The selected language is stored in SQLite and is applied immediately after saving settings.

## Font Fallback

The application configures a broad font fallback chain in:

```text
app/fonts.py
```

It prefers a readable base UI font and adds substitutions for Noto fonts covering Arabic, Hebrew, Devanagari, Bengali, Thai, CJK, Korean, Japanese, Chinese, and emoji.

`main.py` also suppresses the narrow Qt logging category:

```text
qt.text.font.db=false
```

This hides noisy font database warnings without disabling other Qt logging.

## Local Data

The app creates local runtime data:

```text
sessions.sqlite3
profiles/
```

These are excluded from git through `.gitignore`.

## Database

SQLite tables include:

- `sessions`;
- `browser_configs`;
- `proxy_configs`;
- `app_settings`.

The storage API is intentionally small and can be replaced later with PostgreSQL-backed implementations behind the same application service boundary.

## Code Checks

Compile Python files:

```bash
python -m compileall -f main.py app browser_backends models db services gui
```

Compile translations:

```bash
pyside6-lrelease translations/app_*.ts
```

## Git Ignore Policy

Tracked:

- source code;
- `.ts` translation sources;
- compiled `.qm` translation files;
- project metadata.

Ignored:

- virtual environments;
- Python caches;
- local SQLite databases;
- browser profile directories;
- logs;
- imported/exported private CSV data;
- IDE/editor files;
- scratch prompt files.

## Dependencies

See [pyproject.toml](pyproject.toml).

Main runtime dependencies:

- PySide6;
- Selenium.
