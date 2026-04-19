from __future__ import annotations

import unittest

from models.fingerprint_config import FingerprintConfig


class FingerprintConfigTest(unittest.TestCase):
    def test_default_config_is_valid(self) -> None:
        self.assertEqual(FingerprintConfig().validate(), [])

    def test_validate_returns_list_without_timezone(self) -> None:
        errors = FingerprintConfig(timezone=None).validate()

        self.assertIsInstance(errors, list)
        self.assertEqual(errors, [])

    def test_invalid_timezone_is_reported(self) -> None:
        errors = FingerprintConfig(timezone="Invalid/Zone").validate()

        self.assertIn("Invalid timezone: Invalid/Zone", errors)

    def test_invalid_ranges_are_reported(self) -> None:
        errors = FingerprintConfig(
            canvas_noise_level=0.2,
            font_spoof_count=6,
            hardware_concurrency=0,
            device_memory=16,
        ).validate()

        self.assertIn("canvas_noise_level must be between 0.0 and 0.1", errors)
        self.assertIn("font_spoof_count must be between 0 and 5", errors)
        self.assertIn("hardware_concurrency must be between 1 and 128", errors)
        self.assertTrue(any(error.startswith("device_memory must be one of:") for error in errors))

    def test_invalid_value_types_are_reported(self) -> None:
        config = FingerprintConfig(
            hide_automation="yes",  # type: ignore[arg-type]
            canvas_noise_level="high",  # type: ignore[arg-type]
            font_spoof_count=1.5,  # type: ignore[arg-type]
            hardware_concurrency="eight",  # type: ignore[arg-type]
            device_memory="lots",  # type: ignore[arg-type]
            geolocation=(True, 10),  # type: ignore[arg-type]
            timezone=123,  # type: ignore[arg-type]
            webgl_vendor=123,  # type: ignore[arg-type]
        )

        errors = config.validate()

        self.assertIn("hide_automation must be a boolean", errors)
        self.assertIn("canvas_noise_level must be a number", errors)
        self.assertIn("font_spoof_count must be an integer", errors)
        self.assertIn("hardware_concurrency must be an integer", errors)
        self.assertIn("device_memory must be a number", errors)
        self.assertIn("geolocation latitude and longitude must be numbers", errors)
        self.assertIn("timezone must be a string or None", errors)
        self.assertIn("webgl_vendor must be a string or None", errors)

    def test_invalid_runtime_literals_are_reported(self) -> None:
        config = FingerprintConfig(
            canvas_mode="randomized",  # type: ignore[arg-type]
            webrtc_mode="leaky",  # type: ignore[arg-type]
            tls_profile="chrome_old",  # type: ignore[arg-type]
            platform="Amiga",
        )

        errors = config.validate()

        self.assertIn("Invalid canvas_mode: randomized", errors)
        self.assertIn("Invalid webrtc_mode: leaky", errors)
        self.assertIn("Invalid tls_profile: chrome_old", errors)
        self.assertIn("Invalid platform: Amiga", errors)

    def test_invalid_geolocation_is_reported(self) -> None:
        errors = FingerprintConfig(geolocation=(120, 200)).validate()

        self.assertIn("geolocation latitude must be between -90 and 90", errors)
        self.assertIn("geolocation longitude must be between -180 and 180", errors)

    def test_invalid_string_lists_are_reported(self) -> None:
        config = FingerprintConfig(
            spoof_languages=["en-US", 1],  # type: ignore[list-item]
            locale="en-US",  # type: ignore[arg-type]
        )

        errors = config.validate()

        self.assertIn("spoof_languages must contain only strings", errors)
        self.assertIn("locale must be a list", errors)

    def test_raise_if_invalid_raises_value_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid platform: Amiga"):
            FingerprintConfig(platform="Amiga").raise_if_invalid()

    def test_from_dict_normalizes_geolocation(self) -> None:
        config = FingerprintConfig.from_dict({"geolocation": [55.75, 37.62], "locale": None})

        self.assertEqual(config.geolocation, (55.75, 37.62))
        self.assertEqual(config.locale, [])
        self.assertEqual(config.validate(), [])

    def test_to_dict_exports_config(self) -> None:
        config = FingerprintConfig(locale=["ru-RU"], geolocation=(55.75, 37.62))
        data = config.to_dict()

        self.assertEqual(data["locale"], ["ru-RU"])
        self.assertEqual(data["geolocation"], (55.75, 37.62))
        self.assertEqual(data["canvas_mode"], "noise")

    def test_user_agent_consistency_is_validated(self) -> None:
        errors = FingerprintConfig(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36",
            platform="Win32",
            webgl_renderer="ANGLE (NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)",
            timezone="Europe/Moscow",
            locale=["zh-CN", "zh"],
        ).validate()

        self.assertIn("Macintosh User-Agent requires platform MacIntel", errors)
        self.assertIn("Macintosh User-Agent requires Apple WebGL renderer", errors)
        self.assertIn("timezone Europe/Moscow is inconsistent with primary language zh-CN", errors)


if __name__ == "__main__":
    unittest.main()
