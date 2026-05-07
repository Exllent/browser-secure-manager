# Secure Browser Agent Instructions

Use this file as the repo-local operating guide. Keep it accurate when architecture changes.

## Project Snapshot

Secure Browser is a Python 3.12 desktop app for managing isolated Chromium-based browser sessions from a PySide6 GUI.

Core stack:
- PySide6 GUI.
- SQLite persistence in `sessions.sqlite3`.
- Selenium-backed Chromium automation.
- Per-session browser profiles under `profiles/session_<id>`.
- Child processes for session launches and lifetime management.
- Fingerprint profiles stored separately from sessions and applied at browser startup.
- HTTP, SOCKS4, and SOCKS5 proxy records with proxy testing.
- English and Russian UI localization only.

Runtime artifacts such as `profiles/`, `logs/`, `sessions.sqlite3`, `.venv/`, `.idea/`, `__pycache__/`, and `.codex` are not source architecture. Do not edit or commit them unless the user explicitly asks.

## Entry Points

- `main.py` configures logging, initializes `AppService`, initializes storage, loads language settings, creates `QApplication`, and opens `MainWindow`.
- `app_config.py` owns immutable application constants through one frozen `APP_CONFIG` dataclass tree.
- `pyproject.toml` defines console scripts:
  - `secure-browser`
  - `secure-browser-gui`

Run locally with:

```bash
python main.py
```

## Layer Boundaries

Keep responsibilities separated:

- `gui/`: widgets and dialogs only. GUI talks to `AppService`; it must not call SQLite, Selenium, webdriver, or CDP directly.
- `app/`: application orchestration. `AppService` validates selections, coordinates storage, starts/stops session processes, polls process events, and exposes CRUD methods to GUI.
- `app/session_process.py`: multiprocessing session runner. Browser launches happen in child processes, not the GUI thread.
- `db/`: SQLite persistence modules. `db/storage.py` is only a compatibility facade; place implementation in focused modules such as `schema.py`, `sessions.py`, `browsers.py`, `proxies.py`, `fingerprints.py`, `settings.py`, `profile_cache.py`, and `backups.py`.
- `models/`: dataclasses, validation, and fingerprint generation data.
- `browser_backends/`: browser backend protocol, Selenium implementation, browser discovery, Chromium extension setup, Chromium bookmark/shortcut profile preparation.
- `browser_backends/fingerprint/`: fingerprint-specific Chromium option, CDP, extension, and JavaScript patch builders.
- `browser_extensions/`: static extension assets, currently WebRTC leak prevention.
- `services/`: supporting non-GUI business logic, currently proxy testing.
- `app_config.py`: frozen dataclass configuration tree for source-controlled constants such as paths, storage defaults, backup format, browser discovery candidates, proxy test targets, fingerprint options, GUI sizes, and localization filenames. Runtime code reads from `APP_CONFIG`; do not introduce new mutable module-level settings for these concerns.
- `translations/`: only `app_ru.ts` and `app_ru.qm` are expected. English is the source/default language.
- `tests/`: unittest test suite.

When adding functionality, place it in the layer that owns the behavior. Avoid growing GUI or Selenium files with unrelated business logic.

## Session Lifecycle

Sessions are represented by `models/session_entry.py`.

Important fields:
- `url`
- `browser`
- `profile_path`
- `proxy_id`
- `fingerprint_id`
- `window_width` / `window_height`
- `status`

Status values stored in SQLite are machine values:

```text
idle
starting
running
stopped
error
```

Localized labels are handled in `gui/session_status.py`.

Launch flow:
1. `MainWindow.open_session()` receives a row state.
2. `AppService.open_session()` saves the session, loads selected browser/proxy/fingerprint configs, and starts `SessionProcessManager`.
3. `SessionProcessManager.start_session()` spawns a child process using multiprocessing `spawn`.
4. The child process validates proxy if selected, creates a local `SeleniumBrowserBackend`, opens the browser, and emits IPC events.
5. GUI polls events with a `QTimer` every 500 ms and updates row status/log tooltips.

Do not move Selenium startup back into the GUI thread. Startup must remain process-based.

Runtime settings are not applied to an already-running browser session. Users stop a session, change settings, and launch again.

Stop behavior:
- Per-session stop calls `AppService.close_session()`.
- Stop all calls `AppService.close_all_sessions()`.
- `SessionProcessManager.kill_session()` first sends a stop command, then escalates to terminate/kill if the child does not exit.

Session logs are written to `logs/sessions/session_<id>.log` and also sent to the GUI through process events.

## Profile Cache

Session profile directories are browser runtime data. They are selected per session through the Profile page in `gui/session_settings_dialog.py`.

Application settings expose profile cache controls:
- `profile_cache_enabled`: when enabled, deleting a session keeps its profile directory so the user can later restore a session by selecting that profile path.
- `profile_cache_days`: retention values are `1`, `3`, `7`, `30`, `90`, `120`, or `forever`; default is `1`.

Cleanup behavior:
- `AppService.init_storage()` runs profile cache cleanup at app startup.
- Cleanup only deletes orphan profile directories under `profiles/`, meaning profile folders not referenced by any existing session.
- Existing sessions keep their profile directories regardless of age.
- When profile cache is disabled, `AppService.delete_session()` deletes the session profile directory immediately after stopping the session.
- Profile deletion must go through storage/service helpers; GUI should not delete profile folders directly.

## Storage

The storage layer is split by responsibility:
- `db/config.py`: mutable paths and SQLite connection factory.
- `db/schema.py`: SQLite schema creation, lightweight migrations, and default browser/session seeding.
- `db/mappers.py`: SQLite row to dataclass mapping and fingerprint JSON compatibility parsing.
- `db/sessions.py`: session CRUD and default profile path normalization.
- `db/browsers.py`: browser config CRUD and key generation.
- `db/proxies.py`: proxy config CRUD.
- `db/fingerprints.py`: fingerprint profile CRUD and validation before persistence.
- `db/settings.py`: app setting CRUD.
- `db/profile_cache.py`: profile cache retention cleanup and safe profile directory deletion.
- `db/backups.py`: portable JSON backup import/export, validation, and id remapping.
- `db/storage.py`: compatibility facade that re-exports the public API used by `AppService` and tests.

Tables:
- `sessions`
- `proxy_configs`
- `browser_configs`
- `fingerprint_profiles`
- `app_settings`

Fingerprint configs are serialized as JSON in `fingerprint_profiles.config_json`. Always validate `FingerprintConfig` before saving.

Do not add direct SQL access in GUI, browser backends, or models.

## Backups

Backups are JSON files with format marker `secure_browser_backup` and version `1`.

Backup behavior:
- `MainWindow.save_all()` saves visible row changes, then exports a full backup.
- A session row `Save` action saves that row, then exports a session-only backup.
- `MainWindow.load_backup()` imports a selected backup through `AppService`.
- Full backup import replaces persisted sessions, browser configs, proxy configs, fingerprint profiles, and app settings.
- Session backup import adds one session and only the related browser config, proxy config, and fingerprint profile used by that session.
- Imported sessions are restored with `idle` status; running process state is never backed up.

Backup contents are persisted app records only. Chromium profile directories, logs, virtualenvs, and other runtime artifacts are not included.

Layering:
- GUI may choose files and show confirmation/messages only.
- `AppService` coordinates saving current UI state, stopping active sessions before import, and calling storage.
- `db/backups.py` owns backup serialization, deserialization, validation, id remapping, and SQLite writes.

## Browser Backend

`browser_backends/base.py` defines the `BrowserBackend` protocol:
- `open_session`
- `close_session`
- `close_all`
- `discover_installed_browsers`

Current backend:
- `browser_backends/selenium_backend.py`

Selenium backend responsibilities:
- Resolve browser binary through `browser_discovery.py`.
- Prepare the session profile directory.
- Ensure default verification bookmarks and Chromium New Tab shortcuts.
- Build `ChromeOptions`.
- Apply proxy and user-agent options.
- Add default and fingerprint extensions.
- Apply fingerprint CDP overrides.
- Track webdriver instances inside the child process.

Browser support is currently Chromium-based only. Do not add Firefox/Safari behavior unless explicitly requested.

## Browser Discovery

`browser_backends/browser_discovery.py` is the only place for installed-browser discovery and executable validation.

It detects Chromium-family browsers:
- Chrome / Chromium
- Brave
- Microsoft Edge
- Vivaldi
- Opera

If browser search rules change, update this module rather than embedding paths in GUI or Selenium code.

## Chromium Bookmarks And New Tab Shortcuts

`browser_backends/chromium_bookmarks.py` prepares verification links before browser startup.

It currently ensures these three URLs:
- `https://browserleaks.com`
- `https://httpbin.org/ip`
- `https://intoli.com/blog/not-possible-to-block-chrome-headless/chrome-headless-test.html`

It writes three separate Chromium profile mechanisms:
- `Default/Bookmarks`
- `Default/Preferences` using real Chromium custom link prefs:
  - `custom_links.initialized`
  - `custom_links.list`
- `Default/Top Sites` sqlite table for visible New Tab tiles / most visited shortcuts.

Do not write shortcuts under `ntp.custom_links`; Chromium does not read that as the custom links pref.

The old URL `https://browserleaks.com/tls` must be replaced with `https://browserleaks.com`.

## Fingerprints

Fingerprint data model:
- `models/fingerprint_config.py`
- `models/fingerprint_profile.py`
- `models/fingerprint_generator.py`

Fingerprint UI:
- Fingerprint profiles list: `gui/app_settings_dialog.py` and `gui/fingerprint_profile_row.py`.
- Fingerprint edit dialog: `gui/fingerprint_config_dialog.py`.
- Per-session dialog only selects a fingerprint profile; it does not edit individual fingerprint fields.

User-Agent belongs to fingerprint settings, not session settings.

Fingerprint application:
- `selenium_backend.py` passes selected `FingerprintConfig` into Chromium setup.
- `browser_backends/fingerprint/chromium.py` applies Chromium options, writes a generated extension into the profile, and applies CDP overrides.
- Individual fingerprint Python builders live in separate files:
  - `audio.py`
  - `canvas.py`
  - `client_rects.py`
  - `content_filter.py`
  - `device.py`
  - `features_detection.py`
  - `fonts.py`
  - `geolocation.py`
  - `headless.py`
  - `media_devices.py`
  - `navigator.py`
  - `speech_voices.py`
  - `user_agent.py`
  - `webgl.py`
  - `webgpu.py`
  - `workers.py`
  - `utils.py`

Large JavaScript patch bodies live under `browser_backends/fingerprint/js/`.
`browser_backends/fingerprint/templates.py` is the only helper that reads these files and injects dynamic data. Prefer one JSON config object placeholder named `__SECURE_BROWSER_CONFIG__` inside JS templates instead of ad-hoc string formatting. This avoids breaking JavaScript braces, regular expressions, and template strings.

Current JS templates:
- `audio.js`
- `canvas.js`
- `canvas_capture.js`
- `client_rects.js`
- `content_filter.js`
- `device.js`
- `features_core.js`
- `fonts.js`
- `geolocation.js`
- `headless.js`
- `media_devices.js`
- `speech_voices.js`
- `webgl.js`
- `webgpu.js`
- `worker_fingerprint.js`
- `worker_wrapper.js`

Keep Python builders responsible for deciding whether a patch is enabled and for deriving dynamic values from `FingerprintConfig`; keep stable JavaScript behavior in the `.js` templates.

Current fingerprint settings include:
- automation/headless/plugin hiding
- user agent and client hints
- languages and locale
- canvas behavior
- WebGL vendor/renderer
- WebGPU adapter/device API spoofing
- audio noise
- font list and fake font count
- ClientRects/layout metrics
- timezone and geolocation
- WebRTC mode
- hardware concurrency
- device memory
- platform
- TLS profile metadata
- feature detection toggles
- battery spoofing
- content-filter/adblock sign hiding
- custom JavaScript before/after load

If adding a fingerprint setting, update all of these together:
- `FingerprintConfig` field, validation, `to_dict` / `from_dict` compatibility if needed.
- `models/fingerprint_generator.py` if generated profiles should include it.
- `gui/fingerprint_config_dialog.py`.
- The relevant builder in `browser_backends/fingerprint/`.
- The relevant JS template in `browser_backends/fingerprint/js/` when browser-side behavior changes.
- Storage/tests.

Feature Detection has its own file: `browser_backends/fingerprint/features_detection.py`.

TLS note: Selenium does not control Chromium's TLS stack. `tls_profile` is metadata unless an external proxy/browser network stack supports the actual TLS behavior.

## Proxies

Proxy model:
- `models/proxy_config.py`

Proxy UI:
- `gui/proxy_config_row.py`
- `gui/proxy_csv.py`
- proxy page in `gui/app_settings_dialog.py`

Proxy testing:
- `services/proxy_tester.py`

Supported proxy types:
- `http`
- `socks4`
- `socks5`

Proxy testing opens a tunnel to `browserleaks.com:443` and verifies a TLS response. GUI proxy testing uses `QThreadPool`; do not block the GUI thread.

## GUI Structure

Main files:
- `gui/main_window.py`: top-level session list, toolbar, process polling, event handling.
- `gui/session_row_widget.py`: compact session row, action buttons, status and process-log tooltip.
- `gui/session_settings_dialog.py`: per-session settings pages: General, Profile, Proxy, Fingerprint, Window, Notes.
- `gui/app_settings_dialog.py`: application settings pages: General, Browsers, Proxies, Fingerprints, Language.
- `gui/fingerprint_config_dialog.py`: detailed fingerprint edit dialog grouped by fingerprint area with separators.
- `gui/browser_config_row.py`, `gui/proxy_config_row.py`, `gui/fingerprint_profile_row.py`: reusable list rows.

Keep session settings and application settings separate:
- Session settings choose start URL, browser, profile path/folder, proxy, fingerprint, window size, notes.
- Application settings manage browsers, proxies, fingerprint profiles, language, delete confirmation, and profile cache retention.

## Localization

Only English and Russian should be exposed in the UI language list.

Implementation:
- `_()` helper: `app/i18n.py`
- source string collector: `app/i18n_strings.py`
- app settings language page: `gui/app_settings_dialog.py`
- Russian files: `translations/app_ru.ts`, `translations/app_ru.qm`

When adding user-facing text:
- Wrap it with `_()`.
- Keep English source strings stable.
- Add/update Russian translation when practical.
- Use natural Russian labels:
  - `Запустить` for launch/open action if shown as text.
  - `Цифровой отпечаток` / `Цифровые отпечатки` for fingerprint UI.

## Tests And Verification

Primary test command:

```bash
python -m unittest discover
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

Use focused tests while iterating, then run full discovery before finalizing code changes when feasible.

Formatting and linting are part of every code change. After creating or editing Python files, run:

```bash
uv run black <paths>
uv run ruff check <paths> --fix
uv run ruff check <paths>
```

For whole-project cleanup or before a broad commit, use `.` instead of explicit paths. Ruff owns import sorting and practical lint checks; Black owns formatting. The Ruff config intentionally keeps high-signal checks and avoids noisy docstring, annotation, and line-length churn.

For syntax checks:

```bash
python -m compileall app browser_backends db gui models services tests
```

## Change Guidelines

- Prefer small, focused modules with clear ownership.
- Follow existing dataclass and PySide6 patterns.
- Keep persistence changes in the focused `db/` module that owns the behavior; keep `db/storage.py` as a thin facade.
- Keep browser-launch behavior behind `BrowserBackend`.
- Keep Chromium/Selenium details out of GUI.
- Keep fingerprint JavaScript builders separated by fingerprint area.
- Preserve existing user data and runtime artifacts unless explicitly asked to clean them.
- Do not remove unrelated dirty worktree changes.
- Do not commit `.codex` or generated `__pycache__` files.
