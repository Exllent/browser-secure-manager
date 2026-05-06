from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class AppPathsConfig:
    base_dir: Path = ROOT_DIR
    database_filename: str = "sessions.sqlite3"
    profiles_dirname: str = "profiles"
    logs_dirname: str = "logs"
    translations_dirname: str = "translations"
    browser_extensions_dirname: str = "browser_extensions"

    @property
    def db_path(self) -> Path:
        return self.base_dir / self.database_filename

    @property
    def profiles_dir(self) -> Path:
        return self.base_dir / self.profiles_dirname

    @property
    def logs_dir(self) -> Path:
        return self.base_dir / self.logs_dirname

    @property
    def session_logs_dir(self) -> Path:
        return self.logs_dir / "sessions"

    @property
    def translations_dir(self) -> Path:
        return self.base_dir / self.translations_dirname

    @property
    def browser_extensions_dir(self) -> Path:
        return self.base_dir / self.browser_extensions_dirname


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    app_log_filename: str = "secure_browser.log"
    error_log_filename: str = "secure_browser_errors.log"
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    all_kind: str = "all"
    errors_kind: str = "errors"


@dataclass(frozen=True, slots=True)
class StorageConfig:
    default_browser_key: str = "chrome"
    default_browser_display_name: str = "Chrome / Chromium"
    default_browser_type: str = "chromium"
    default_session_name: str = "Chrome demo"
    default_session_url: str = "https://www.python.org"
    default_session_proxy_label: str = "local profile"
    default_session_notes: str = "Demo Chrome session with its own browser profile."
    default_window_size: tuple[int, int] = (1280, 800)
    default_status: str = "idle"
    session_profile_prefix: str = "session_"
    supported_browser_types: tuple[str, ...] = ("chromium",)


@dataclass(frozen=True, slots=True)
class SettingsKeysConfig:
    confirm_before_delete: str = "confirm_before_delete"
    language: str = "language"
    profile_cache_enabled: str = "profile_cache_enabled"
    profile_cache_days: str = "profile_cache_days"


@dataclass(frozen=True, slots=True)
class BackupConfig:
    format: str = "secure_browser_backup"
    version: int = 1
    full_scope: str = "full"
    session_scope: str = "session"


@dataclass(frozen=True, slots=True)
class ProfileCacheConfig:
    enabled_default: str = "1"
    days_default: str = "1"
    forever_value: str = "forever"
    day_options: tuple[str, ...] = ("1", "3", "7", "30", "90", "120", "forever")
    profile_markers: tuple[str, ...] = ("Local State", "Default")


@dataclass(frozen=True, slots=True)
class SessionProcessConfig:
    multiprocessing_context: str = "spawn"
    default_event_level: str = "INFO"
    starting_state: str = "starting"
    running_state: str = "running"
    stopped_state: str = "stopped"
    started_event: str = "started"
    log_event: str = "log"
    failed_state: str = "failed"
    error_state: str = "error"
    stop_command: str = "stop"
    default_stop_timeout_seconds: float = 2.0
    command_poll_timeout_seconds: float = 1.0
    loop_sleep_seconds: float = 0.2


@dataclass(frozen=True, slots=True)
class ChromiumBookmarksConfig:
    default_bookmarks: tuple[tuple[str, str], ...] = (
        ("BrowserLeaks", "https://browserleaks.com"),
        ("HTTPBin IP", "https://httpbin.org/ip"),
        (
            "Chrome Headless Test",
            "https://intoli.com/blog/not-possible-to-block-chrome-headless/chrome-headless-test.html",
        ),
    )
    url_replacements: tuple[tuple[str, str], ...] = (
        ("https://browserleaks.com/tls", "https://browserleaks.com"),
        ("http://browserleaks.com/tls", "https://browserleaks.com"),
    )


@dataclass(frozen=True, slots=True)
class ChromiumExtensionConfig:
    webrtc_extension_dirname: str = "webrtc_leak_prevent"
    manifest_filename: str = "manifest.json"
    load_extension_argument_prefix: str = "--load-extension="
    enable_only_extension_argument_prefix: str = "--disable-extensions-except="
    disable_non_proxied_udp_argument: str = (
        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"
    )
    fingerprint_extension_dirname: str = "secure_browser_fingerprint_extension"
    fingerprint_extension_digest_length: int = 12
    fingerprint_script_filename: str = "fingerprint.js"
    fingerprint_extension_name: str = "Secure Browser Fingerprint"
    fingerprint_extension_version: str = "1.0.0"


@dataclass(frozen=True, slots=True)
class BrowserCandidateConfig:
    key: str
    display_name: str
    browser_type: str
    command_names: tuple[str, ...]
    linux_paths: tuple[str, ...]
    mac_paths: tuple[str, ...]
    windows_subdirs: tuple[tuple[str, str, tuple[str, ...]], ...]


@dataclass(frozen=True, slots=True)
class BrowserDiscoveryConfig:
    default_browser_name: str = "Chrome / Chromium"
    default_env_var: str = "CHROME_BINARY"
    validate_timeout_seconds: float = 5.0
    version_keywords: tuple[str, ...] = (
        "Google Chrome",
        "Chromium",
        "Chrome",
        "Brave",
        "Microsoft Edge",
        "Vivaldi",
        "Opera",
    )
    candidates: tuple[BrowserCandidateConfig, ...] = (
        BrowserCandidateConfig(
            key="chrome",
            display_name="Chrome / Chromium",
            browser_type="chromium",
            command_names=(
                "google-chrome",
                "chrome",
                "chromium",
                "chromium-browser",
            ),
            linux_paths=(
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/snap/chromium/current/usr/lib/chromium-browser/chrome",
                "/snap/bin/chromium",
                "/opt/google/chrome/chrome",
            ),
            mac_paths=(
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
                "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ),
            windows_subdirs=(
                (
                    "Google/Chrome/Application",
                    "chrome.exe",
                    ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"),
                ),
                (
                    "Chromium/Application",
                    "chrome.exe",
                    ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"),
                ),
            ),
        ),
        BrowserCandidateConfig(
            key="brave",
            display_name="Brave",
            browser_type="chromium",
            command_names=("brave-browser", "brave"),
            linux_paths=(
                "/usr/bin/brave-browser",
                "/usr/bin/brave",
                "/snap/bin/brave",
                "/opt/brave.com/brave/brave-browser",
            ),
            mac_paths=(
                "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "~/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            ),
            windows_subdirs=(
                (
                    "BraveSoftware/Brave-Browser/Application",
                    "brave.exe",
                    ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"),
                ),
            ),
        ),
        BrowserCandidateConfig(
            key="edge",
            display_name="Microsoft Edge",
            browser_type="chromium",
            command_names=("microsoft-edge",),
            linux_paths=(
                "/usr/bin/microsoft-edge",
                "/usr/bin/microsoft-edge-stable",
                "/opt/microsoft/msedge/msedge",
            ),
            mac_paths=(
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "~/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            ),
            windows_subdirs=(
                (
                    "Microsoft/Edge/Application",
                    "msedge.exe",
                    ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"),
                ),
            ),
        ),
        BrowserCandidateConfig(
            key="vivaldi",
            display_name="Vivaldi",
            browser_type="chromium",
            command_names=("vivaldi",),
            linux_paths=(
                "/usr/bin/vivaldi",
                "/usr/bin/vivaldi-stable",
                "/opt/vivaldi/vivaldi",
            ),
            mac_paths=(
                "/Applications/Vivaldi.app/Contents/MacOS/Vivaldi",
                "~/Applications/Vivaldi.app/Contents/MacOS/Vivaldi",
            ),
            windows_subdirs=(
                (
                    "Vivaldi/Application",
                    "vivaldi.exe",
                    ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"),
                ),
            ),
        ),
        BrowserCandidateConfig(
            key="opera",
            display_name="Opera",
            browser_type="chromium",
            command_names=("opera",),
            linux_paths=(
                "/usr/bin/opera",
                "/snap/opera/current/usr/lib/x86_64-linux-gnu/opera/opera",
                "/snap/bin/opera",
                "/opt/opera/opera",
            ),
            mac_paths=(
                "/Applications/Opera.app/Contents/MacOS/Opera",
                "~/Applications/Opera.app/Contents/MacOS/Opera",
            ),
            windows_subdirs=(
                (
                    "Opera",
                    "launcher.exe",
                    ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"),
                ),
                ("Programs/Opera", "launcher.exe", ("LOCALAPPDATA",)),
            ),
        ),
    )

    @property
    def chromium_command_names(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                command
                for candidate in self.candidates
                for command in candidate.command_names
            )
        )


@dataclass(frozen=True, slots=True)
class ProxyConfigDefaults:
    supported_types: tuple[str, ...] = ("http", "socks4", "socks5")
    default_type: str = "socks5"
    test_target_host: str = "browserleaks.com"
    test_target_port: int = 443
    test_timeout_seconds: float = 5.0
    tls_probe_path: str = "/webrtc"


@dataclass(frozen=True, slots=True)
class FingerprintValidationConfig:
    canvas_modes: tuple[str, ...] = ("noise", "fixed", "passthrough")
    webrtc_modes: tuple[str, ...] = ("disable", "public_ip_only", "proxy_dns", "passthrough")
    tls_profiles: tuple[str, ...] = ("chrome_134", "chromium_134", "random")
    platforms: tuple[str, ...] = ("Win32", "Win64", "MacIntel", "Linux x86_64", "Linux armv8l")
    mac_platform: str = "MacIntel"
    windows_platforms: tuple[str, ...] = ("Win32", "Win64")
    linux_platforms: tuple[str, ...] = ("Linux x86_64", "Linux armv8l")
    device_memory_values: tuple[float, ...] = (0.25, 0.5, 1, 2, 4, 8)
    timezone_language_prefixes: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("Europe/Moscow", ("ru",)),
        ("America/New_York", ("en",)),
        ("America/Los_Angeles", ("en",)),
        ("Europe/Berlin", ("de",)),
        ("Europe/Paris", ("fr",)),
        ("Asia/Tokyo", ("ja",)),
    )
    boolean_fields: tuple[str, ...] = (
        "hide_automation",
        "hide_headless",
        "spoof_plugins",
        "audio_noise",
        "spoof_touch_support",
        "spoof_connection",
        "spoof_permissions",
        "spoof_feature_detection",
        "hide_adblock_signs",
        "spoof_battery",
    )
    list_fields: tuple[str, ...] = (
        "spoof_languages",
        "font_list",
        "locale",
        "custom_js_before_load",
        "custom_js_after_load",
    )
    optional_string_fields: tuple[str, ...] = (
        "user_agent",
        "webgl_vendor",
        "webgl_renderer",
        "timezone",
        "platform",
    )
    canvas_noise_min: float = 0.0
    canvas_noise_max: float = 0.1
    canvas_seed_min: int = 1
    canvas_seed_max: int = 4_294_967_295
    font_spoof_min: int = 0
    font_spoof_max: int = 5
    hardware_concurrency_min: int = 1
    hardware_concurrency_max: int = 128


@dataclass(frozen=True, slots=True)
class FontConfig:
    base_candidates: tuple[str, ...] = (
        "Noto Sans",
        "Segoe UI",
        "San Francisco",
        "Helvetica Neue",
        "Arial",
        "DejaVu Sans",
        "Ubuntu Sans",
    )
    fallback_candidates: tuple[str, ...] = (
        "Noto Sans Arabic",
        "Noto Sans Hebrew",
        "Noto Sans Devanagari",
        "Noto Sans Bengali",
        "Noto Sans Thai",
        "Noto Sans CJK SC",
        "Noto Sans CJK TC",
        "Noto Sans CJK JP",
        "Noto Sans CJK KR",
        "Noto Color Emoji",
        "DejaVu Sans",
        "Segoe UI",
        "Arial",
    )
    substituted_families: tuple[str, ...] = (
        "Ubuntu Sans",
        "Arial",
        "Helvetica",
        "Helvetica Neue",
        "Segoe UI",
        "Sans Serif",
        "sans-serif",
    )
    emoji_candidates: tuple[str, ...] = (
        "Noto Color Emoji",
        "Segoe UI Emoji",
        "Apple Color Emoji",
    )


@dataclass(frozen=True, slots=True)
class FingerprintPresetConfig:
    label: str
    user_agent: str
    languages: tuple[str, ...]
    timezone: str
    geolocation: tuple[float, float]
    platform: str
    hardware_concurrency: int
    device_memory: float
    webgl_vendor: str
    webgl_renderer: str
    fonts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FingerprintGenerationConfig:
    known_font_families: tuple[str, ...] = (
        "Arial",
        "Calibri",
        "Cambria",
        "Courier New",
        "Geneva",
        "DejaVu Sans",
        "DejaVu Sans Mono",
        "DejaVu Serif",
        "Georgia",
        "Helvetica",
        "Hiragino Sans",
        "Liberation Sans",
        "Liberation Serif",
        "Menlo",
        "Monaco",
        "Noto Sans",
        "Osaka",
        "Roboto",
        "Segoe UI",
        "Tahoma",
        "Times",
        "Times New Roman",
        "Ubuntu",
        "Verdana",
        "Yu Gothic",
    )
    fake_font_prefix: str = "Secure UI "
    canvas_noise_choices: tuple[float, ...] = (0.01, 0.015, 0.02, 0.025)
    font_spoof_count_choices: tuple[int, ...] = (0, 1, 2)
    presets: tuple[FingerprintPresetConfig, ...] = (
        FingerprintPresetConfig(
            label="Windows Chrome RU Moscow",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            languages=("ru-RU", "ru", "en-US", "en"),
            timezone="Europe/Moscow",
            geolocation=(55.755826, 37.6173),
            platform="Win32",
            hardware_concurrency=8,
            device_memory=8,
            webgl_vendor="Google Inc. (NVIDIA)",
            webgl_renderer="ANGLE (NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)",
            fonts=("Arial", "Calibri", "Cambria", "Segoe UI", "Tahoma", "Times New Roman"),
        ),
        FingerprintPresetConfig(
            label="macOS Chrome US New York",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            languages=("en-US", "en"),
            timezone="America/New_York",
            geolocation=(40.712776, -74.005974),
            platform="MacIntel",
            hardware_concurrency=8,
            device_memory=8,
            webgl_vendor="Google Inc. (Apple)",
            webgl_renderer="ANGLE (Apple, ANGLE Metal Renderer: Apple M2 Pro, Unspecified Version)",
            fonts=("Arial", "Helvetica", "Menlo", "Monaco", "Times", "Verdana"),
        ),
        FingerprintPresetConfig(
            label="macOS Chrome JP Tokyo",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/133.0.0.0 Safari/537.36"
            ),
            languages=("ja-JP", "ja", "en-US", "en"),
            timezone="Asia/Tokyo",
            geolocation=(35.6762, 139.6503),
            platform="MacIntel",
            hardware_concurrency=10,
            device_memory=8,
            webgl_vendor="Google Inc. (Apple)",
            webgl_renderer="ANGLE (Apple, ANGLE Metal Renderer: Apple M3, Unspecified Version)",
            fonts=("Hiragino Sans", "Helvetica", "Menlo", "Osaka", "Times", "Yu Gothic"),
        ),
        FingerprintPresetConfig(
            label="Windows Chrome DE Berlin",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/133.0.0.0 Safari/537.36"
            ),
            languages=("de-DE", "de", "en-US", "en"),
            timezone="Europe/Berlin",
            geolocation=(52.52, 13.405),
            platform="Win32",
            hardware_concurrency=12,
            device_memory=8,
            webgl_vendor="Google Inc. (Intel)",
            webgl_renderer="ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0)",
            fonts=("Arial", "Calibri", "Segoe UI", "Tahoma", "Times New Roman", "Verdana"),
        ),
        FingerprintPresetConfig(
            label="Windows Chrome FR Paris",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            languages=("fr-FR", "fr", "en-US", "en"),
            timezone="Europe/Paris",
            geolocation=(48.856613, 2.352222),
            platform="Win32",
            hardware_concurrency=8,
            device_memory=8,
            webgl_vendor="Google Inc. (AMD)",
            webgl_renderer="ANGLE (AMD, AMD Radeon RX 6600 Direct3D11 vs_5_0 ps_5_0)",
            fonts=("Arial", "Calibri", "Segoe UI", "Tahoma", "Times New Roman", "Verdana"),
        ),
        FingerprintPresetConfig(
            label="Linux Chrome US Los Angeles",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            languages=("en-US", "en"),
            timezone="America/Los_Angeles",
            geolocation=(34.052235, -118.243683),
            platform="Linux x86_64",
            hardware_concurrency=8,
            device_memory=8,
            webgl_vendor="Google Inc. (Intel)",
            webgl_renderer="ANGLE (Intel, Mesa Intel(R) UHD Graphics 620, OpenGL 4.6)",
            fonts=("Arial", "DejaVu Sans", "Liberation Sans", "Noto Sans", "Ubuntu"),
        ),
    )


@dataclass(frozen=True, slots=True)
class GuiConfig:
    main_window_size: tuple[int, int] = (1160, 720)
    main_poll_interval_ms: int = 500
    session_settings_size: tuple[int, int] = (720, 520)
    app_settings_size: tuple[int, int] = (980, 620)
    fingerprint_settings_size: tuple[int, int] = (760, 680)
    proxy_test_thread_count: int = 32
    default_session_url_placeholder: str = "https://example.com"
    profile_path_placeholder: str = "profiles/session_<id>"
    notes_minimum_height: int = 120
    window_width_range: tuple[int, int] = (320, 7680)
    window_height_range: tuple[int, int] = (240, 4320)
    default_backup_filename: str = "secure_browser_backup.json"
    backup_file_filter: str = "Backup files (*.json);;All files (*)"
    log_file_filter: str = "Log files (*.log);;All files (*)"
    csv_file_filter: str = "CSV files (*.csv);;All files (*)"
    language_options: tuple[tuple[str, str], ...] = (("English", "en"), ("Русский", "ru"))
    session_table_columns: tuple[tuple[str, int], ...] = (
        ("", 64),
        ("Name", 360),
        ("Status", 110),
        ("Open", 72),
        ("Stop", 72),
        ("Settings", 92),
        ("Save", 92),
        ("Delete", 72),
    )


@dataclass(frozen=True, slots=True)
class I18nConfig:
    context: str = "App"
    translation_prefix: str = "app_"
    translation_suffix: str = ".qm"


@dataclass(frozen=True, slots=True)
class AppConfig:
    paths: AppPathsConfig = field(default_factory=AppPathsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    settings_keys: SettingsKeysConfig = field(default_factory=SettingsKeysConfig)
    backups: BackupConfig = field(default_factory=BackupConfig)
    profile_cache: ProfileCacheConfig = field(default_factory=ProfileCacheConfig)
    session_process: SessionProcessConfig = field(default_factory=SessionProcessConfig)
    bookmarks: ChromiumBookmarksConfig = field(default_factory=ChromiumBookmarksConfig)
    chromium_extensions: ChromiumExtensionConfig = field(default_factory=ChromiumExtensionConfig)
    browser_discovery: BrowserDiscoveryConfig = field(default_factory=BrowserDiscoveryConfig)
    proxies: ProxyConfigDefaults = field(default_factory=ProxyConfigDefaults)
    fingerprint_validation: FingerprintValidationConfig = field(
        default_factory=FingerprintValidationConfig
    )
    fingerprint_generation: FingerprintGenerationConfig = field(
        default_factory=FingerprintGenerationConfig
    )
    fonts: FontConfig = field(default_factory=FontConfig)
    gui: GuiConfig = field(default_factory=GuiConfig)
    i18n: I18nConfig = field(default_factory=I18nConfig)


APP_CONFIG = AppConfig()
