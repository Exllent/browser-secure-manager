from __future__ import annotations

import os
import random
import re
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from browser_backends.browser_discovery import discover_installed_browsers
from browser_backends.selenium_backend import SeleniumBrowserBackend
from models.browser_config import BrowserConfig
from models.fingerprint_config import FingerprintConfig
from models.fingerprint_generator import FINGERPRINT_PRESETS, generate_fingerprint_config
from models.session_entry import SessionEntry

LIVE_FINGERPRINT_ENV = "SECURE_BROWSER_LIVE_FINGERPRINT"
LIVE_BROWSER_ENV = "SECURE_BROWSER_LIVE_BROWSER"
DEFAULT_TIMEOUT_SECONDS = 45
HASH_PATTERN_TEMPLATE = r"\b[0-9a-fA-F]{{{length}}}\b"

CANVAS_URL = "https://browserleaks.com/canvas"
WEBGL_URL = "https://browserleaks.com/webgl"
FONTS_URL = "https://browserleaks.com/fonts"
FEATURES_URL = "https://browserleaks.com/features"
PROXY_URL = "https://browserleaks.com/proxy"
SANNYSOFT_URL = "https://bot.sannysoft.com/"


@dataclass(frozen=True, slots=True)
class LiveSessionSpec:
    label: str
    group: str
    config: FingerprintConfig


@dataclass(frozen=True, slots=True)
class LiveSessionResult:
    label: str
    group: str
    canvas_signature: str
    webgl_report_hash: str
    webgl_image_hash: str
    font_metrics_hash: str
    font_glyphs_hash: str
    features_hash: str

    def stable_identity(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.canvas_signature,
            self.webgl_report_hash,
            self.webgl_image_hash,
            self.font_metrics_hash,
            self.font_glyphs_hash,
            self.features_hash,
        )


@unittest.skipUnless(
    os.environ.get(LIVE_FINGERPRINT_ENV) == "1",
    f"set {LIVE_FINGERPRINT_ENV}=1 to run external browser fingerprint checks",
)
class LiveFingerprintMatrixTest(unittest.TestCase):
    maxDiff = None

    def test_browserleaks_and_bot_matrix(self) -> None:
        browser_config = _browser_config()
        specs = _build_matrix_specs()
        results: list[LiveSessionResult] = []

        with tempfile.TemporaryDirectory(prefix="secure-browser-live-fp-") as temp_dir:
            for index, spec in enumerate(specs, start=1):
                with self.subTest(session=spec.label):
                    result = _run_live_session(
                        index=index,
                        spec=spec,
                        profile_root=Path(temp_dir),
                        browser_config=browser_config,
                    )
                    results.append(result)

        self.assertEqual(len(results), 10)
        _assert_identical_device_pairs(self, results)
        _assert_distinct_device_sessions(self, results)


def _build_matrix_specs() -> list[LiveSessionSpec]:
    mac_preset = _first_preset("MAC")
    windows_preset = _first_preset("WIN")
    linux_preset = _first_preset("LINUX")
    paired_presets = {mac_preset.label, windows_preset.label, linux_preset.label}
    random_presets = random.SystemRandom().sample(
        [preset for preset in FINGERPRINT_PRESETS if preset.label not in paired_presets],
        4,
    )

    mac_config = generate_fingerprint_config(mac_preset)
    windows_config = generate_fingerprint_config(windows_preset)
    linux_config = generate_fingerprint_config(linux_preset)

    specs = [
        LiveSessionSpec("mac-1", "mac-pair", _clone_config(mac_config)),
        LiveSessionSpec("mac-2", "mac-pair", _clone_config(mac_config)),
        LiveSessionSpec("windows-1", "windows-pair", _clone_config(windows_config)),
        LiveSessionSpec("windows-2", "windows-pair", _clone_config(windows_config)),
        LiveSessionSpec("linux-1", "linux-pair", _clone_config(linux_config)),
        LiveSessionSpec("linux-2", "linux-pair", _clone_config(linux_config)),
    ]
    specs.extend(
        LiveSessionSpec(
            f"random-{index}",
            f"random-{index}",
            generate_fingerprint_config(preset),
        )
        for index, preset in enumerate(random_presets, start=1)
    )
    return specs


def _first_preset(prefix: str):
    for preset in FINGERPRINT_PRESETS:
        if preset.label.startswith(prefix):
            return preset
    raise AssertionError(f"No {prefix} fingerprint preset configured")


def _clone_config(config: FingerprintConfig) -> FingerprintConfig:
    return FingerprintConfig.from_dict(config.to_dict())


def _browser_config() -> BrowserConfig:
    explicit_browser = os.environ.get(LIVE_BROWSER_ENV) or os.environ.get("CHROME_BINARY")
    if explicit_browser:
        return BrowserConfig(
            id=None,
            key="live-chromium",
            display_name="Live Chromium",
            browser_type="chromium",
            executable_path=explicit_browser,
        )

    discovered = discover_installed_browsers()
    if discovered:
        return discovered[0]

    return BrowserConfig(
        id=None,
        key="live-chromium",
        display_name="Live Chromium",
        browser_type="chromium",
    )


def _run_live_session(
    *,
    index: int,
    spec: LiveSessionSpec,
    profile_root: Path,
    browser_config: BrowserConfig,
) -> LiveSessionResult:
    profile_dir = profile_root / spec.label
    session = SessionEntry(
        id=index,
        name=spec.label,
        url=CANVAS_URL,
        browser=browser_config.key,
        profile_path=str(profile_dir),
        window_width=spec.config.screen_width or 1365,
        window_height=spec.config.screen_height or 768,
    )

    driver: WebDriver | None = None
    try:
        driver = SeleniumBrowserBackend._open_chromium(
            session=session,
            browser_config=browser_config,
            profile_dir=profile_dir,
            proxy_config=None,
            fingerprint_config=spec.config,
        )

        canvas_signature = _check_browserleaks_canvas(driver)
        webgl_report_hash, webgl_image_hash = _check_browserleaks_webgl(driver, spec.config)
        font_metrics_hash, font_glyphs_hash = _check_browserleaks_fonts(driver)
        features_hash = _check_browserleaks_features(driver)
        _check_browserleaks_proxy(driver)
        _check_sannysoft(driver)

        return LiveSessionResult(
            label=spec.label,
            group=spec.group,
            canvas_signature=canvas_signature,
            webgl_report_hash=webgl_report_hash,
            webgl_image_hash=webgl_image_hash,
            font_metrics_hash=font_metrics_hash,
            font_glyphs_hash=font_glyphs_hash,
            features_hash=features_hash,
        )
    finally:
        if driver is not None:
            try:
                driver.quit()
            except WebDriverException:
                pass


def _check_browserleaks_canvas(driver: WebDriver) -> str:
    driver.get(CANVAS_URL)

    signature = _wait_for_text(driver, "#canvas-hash")
    for selector in (
        "#canvas-support-2d",
        "#canvas-support-text",
        "#canvas-support-todataurl",
    ):
        support_text = _wait_for_text(driver, selector)
        if "True" not in support_text:
            raise AssertionError(f"{CANVAS_URL} {selector} expected True, got {support_text!r}")

    return _normalized_hash(signature, 32, "Canvas Signature")


def _check_browserleaks_webgl(
    driver: WebDriver,
    config: FingerprintConfig,
) -> tuple[str, str]:
    driver.get(WEBGL_URL)

    report_hash = _wait_for_text(driver, "#gl-report-hash")
    image_hash = _wait_for_text(driver, "#gl-image-hash")
    http_user_agent = _row_value_by_label(driver, "HTTP User-Agent")
    unmasked_vendor = _wait_for_text(driver, "#UNMASKED_VENDOR_WEBGL")
    unmasked_renderer = _wait_for_text(driver, "#UNMASKED_RENDERER_WEBGL")
    runtime = _runtime_fingerprint(driver)

    if config.user_agent and config.user_agent not in http_user_agent:
        raise AssertionError(
            f"{WEBGL_URL} HTTP User-Agent mismatch: expected {config.user_agent!r}, "
            f"got {http_user_agent!r}"
        )
    if config.user_agent and runtime["userAgent"] != config.user_agent:
        raise AssertionError(
            f"{WEBGL_URL} navigator.userAgent mismatch: expected {config.user_agent!r}, "
            f"got {runtime['userAgent']!r}"
        )
    if config.platform and runtime["platform"] != config.platform:
        raise AssertionError(
            f"{WEBGL_URL} navigator.platform mismatch: expected {config.platform!r}, "
            f"got {runtime['platform']!r}"
        )
    if config.webgl_vendor and config.webgl_vendor not in unmasked_vendor:
        raise AssertionError(
            f"{WEBGL_URL} WebGL vendor mismatch: expected {config.webgl_vendor!r}, "
            f"got {unmasked_vendor!r}"
        )
    if config.webgl_renderer and config.webgl_renderer not in unmasked_renderer:
        raise AssertionError(
            f"{WEBGL_URL} WebGL renderer mismatch: expected {config.webgl_renderer!r}, "
            f"got {unmasked_renderer!r}"
        )

    return (
        _normalized_hash(report_hash, 32, "WebGL Report Hash"),
        _normalized_hash(image_hash, 32, "WebGL Image Hash"),
    )


def _check_browserleaks_fonts(driver: WebDriver) -> tuple[str, str]:
    driver.get(FONTS_URL)

    metrics_hash = _wait_for_text(driver, "#fonts-metrics-hash")
    glyphs_hash = _wait_for_text(driver, "#fonts-glyphs-hash")

    return (
        _normalized_hash(metrics_hash, 32, "Font Metrics Fingerprint"),
        _normalized_hash(glyphs_hash, 8, "Unicode Glyphs Fingerprint"),
    )


def _check_browserleaks_features(driver: WebDriver) -> str:
    driver.get(FEATURES_URL)

    features_hash = _wait_for_text(driver, "#ft-hash")

    return _normalized_hash(features_hash, 32, "Features Hash")


def _check_browserleaks_proxy(driver: WebDriver) -> None:
    driver.get(PROXY_URL)

    canvas_protection = _wait_for_text(driver, "#tbb-canvas")
    if "not detected" not in canvas_protection.lower() or "Detected" in canvas_protection:
        raise AssertionError(
            f"{PROXY_URL} Canvas Protection expected not detected, got {canvas_protection!r}"
        )


def _check_sannysoft(driver: WebDriver) -> None:
    driver.get(SANNYSOFT_URL)

    _wait_for_condition(
        driver,
        lambda current: bool(
            _execute_script(current, "return document.querySelectorAll('#fp2 tr').length")
        ),
        "Sannysoft Fingerprint Scanner rows",
    )

    intoli_failures = _execute_script(
        driver,
        """
        return Array.from(document.querySelectorAll('td.result')).map((cell) => ({
            label: cell.parentElement && cell.parentElement.cells.length
                ? cell.parentElement.cells[0].innerText.trim()
                : '',
            text: cell.innerText.trim(),
            classes: Array.from(cell.classList),
        })).filter((row) => !row.classes.includes('passed'));
        """,
    )
    if intoli_failures:
        raise AssertionError(f"{SANNYSOFT_URL} Intoli result failures: {intoli_failures!r}")

    scanner_failures = _execute_script(
        driver,
        """
        return Array.from(document.querySelectorAll('#fp2 tr')).map((row) => {
            const status = row.cells[1];
            return {
                label: row.cells[0] ? row.cells[0].innerText.trim() : '',
                text: status ? status.innerText.trim() : '',
                classes: status ? Array.from(status.classList) : [],
            };
        }).filter((row) => row.text !== 'ok' || !row.classes.includes('passed'));
        """,
    )
    if scanner_failures:
        raise AssertionError(f"{SANNYSOFT_URL} Fingerprint Scanner failures: {scanner_failures!r}")


def _assert_identical_device_pairs(
    test_case: unittest.TestCase,
    results: list[LiveSessionResult],
) -> None:
    for group in ("mac-pair", "windows-pair", "linux-pair"):
        group_results = [result for result in results if result.group == group]
        test_case.assertEqual(len(group_results), 2, group)
        test_case.assertEqual(
            group_results[0].stable_identity(),
            group_results[1].stable_identity(),
            f"{group} should keep the same canvas/webgl/fonts/features identity",
        )


def _assert_distinct_device_sessions(
    test_case: unittest.TestCase,
    results: list[LiveSessionResult],
) -> None:
    for left_index, left in enumerate(results):
        for right in results[left_index + 1 :]:
            if left.group == right.group:
                continue
            test_case.assertNotEqual(
                left.stable_identity(),
                right.stable_identity(),
                f"{left.label} and {right.label} should not share one full fingerprint",
            )


def _wait_for_text(
    driver: WebDriver,
    selector: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    try:
        return WebDriverWait(driver, timeout).until(
            lambda current: _query_text(current, selector) or False
        )
    except TimeoutException as exc:
        raise AssertionError(f"Timed out waiting for text in {selector}") from exc


def _query_text(driver: WebDriver, selector: str) -> str:
    return str(
        _execute_script(
            driver,
            """
            const element = document.querySelector(arguments[0]);
            return element ? element.innerText.trim() : '';
            """,
            selector,
        )
        or ""
    ).strip()


def _row_value_by_label(driver: WebDriver, label: str) -> str:
    value = _execute_script(
        driver,
        """
        const wanted = arguments[0].trim();
        for (const row of document.querySelectorAll('tr')) {
            if (!row.cells || row.cells.length < 2) continue;
            const label = row.cells[0].innerText.trim();
            if (label === wanted) {
                return Array.from(row.cells).slice(1).map((cell) => cell.innerText.trim()).join(' ');
            }
        }
        return '';
        """,
        label,
    )
    if not value:
        raise AssertionError(f"Could not find row label {label!r} at {driver.current_url}")
    return str(value).strip()


def _runtime_fingerprint(driver: WebDriver) -> dict[str, Any]:
    value = _execute_script(
        driver,
        """
        return {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            languages: Array.from(navigator.languages || []),
            hardwareConcurrency: navigator.hardwareConcurrency,
            deviceMemory: navigator.deviceMemory,
        };
        """,
    )
    if not isinstance(value, dict):
        raise AssertionError(f"Could not read runtime fingerprint at {driver.current_url}")
    return value


def _wait_for_condition(
    driver: WebDriver,
    condition,
    description: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> None:
    try:
        WebDriverWait(driver, timeout).until(condition)
    except TimeoutException as exc:
        raise AssertionError(f"Timed out waiting for {description}") from exc


def _execute_script(driver: WebDriver, script: str, *args):
    return driver.execute_script(script, *args)


def _normalized_hash(value: str, length: int, label: str) -> str:
    cleaned = value.strip()
    matches = re.findall(HASH_PATTERN_TEMPLATE.format(length=length), cleaned)
    if not matches:
        raise AssertionError(f"{label} expected {length} hex chars, got {cleaned!r}")
    cleaned = matches[0]
    try:
        int(cleaned, 16)
    except ValueError as exc:
        raise AssertionError(f"{label} is not hex: {cleaned!r}") from exc
    return cleaned.upper()


if __name__ == "__main__":
    unittest.main()
