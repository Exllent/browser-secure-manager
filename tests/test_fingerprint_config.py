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
            screen_width=0,
            device_scale_factor=5,
            max_touch_points=20,
            connection_downlink=-1,
            connection_rtt=-1,
            battery_level=1.5,
        ).validate()

        self.assertIn("canvas_noise_level must be between 0.0 and 0.1", errors)
        self.assertIn("font_spoof_count must be between 0 and 5", errors)
        self.assertIn("hardware_concurrency must be between 1 and 128", errors)
        self.assertTrue(any(error.startswith("device_memory must be one of:") for error in errors))
        self.assertIn("screen_width must be between 1 and 16384", errors)
        self.assertIn("device_scale_factor must be between 0.5 and 4.0", errors)
        self.assertIn("max_touch_points must be between 0 and 16", errors)
        self.assertIn("connection_downlink must be between 0.0 and 10000.0", errors)
        self.assertIn("connection_rtt must be between 0 and 10000", errors)
        self.assertIn("battery_level must be between 0.0 and 1.0", errors)

    def test_invalid_value_types_are_reported(self) -> None:
        config = FingerprintConfig(
            hide_automation="yes",  # type: ignore[arg-type]
            spoof_feature_detection="yes",  # type: ignore[arg-type]
            spoof_media_devices="yes",  # type: ignore[arg-type]
            spoof_speech_voices="yes",  # type: ignore[arg-type]
            global_privacy_control="yes",  # type: ignore[arg-type]
            media_devices="camera",  # type: ignore[arg-type]
            speech_voices="voice",  # type: ignore[arg-type]
            canvas_noise_level="high",  # type: ignore[arg-type]
            canvas_noise_seed="seed",  # type: ignore[arg-type]
            font_spoof_count=1.5,  # type: ignore[arg-type]
            hardware_concurrency="eight",  # type: ignore[arg-type]
            device_memory="lots",  # type: ignore[arg-type]
            geolocation=(True, 10),  # type: ignore[arg-type]
            timezone=123,  # type: ignore[arg-type]
            do_not_track=1,  # type: ignore[arg-type]
            webgl_vendor=123,  # type: ignore[arg-type]
            connection_save_data="no",  # type: ignore[arg-type]
            battery_charging="yes",  # type: ignore[arg-type]
            screen_height="1080",  # type: ignore[arg-type]
            connection_rtt="fast",  # type: ignore[arg-type]
            battery_charging_time="soon",  # type: ignore[arg-type]
        )

        errors = config.validate()

        self.assertIn("hide_automation must be a boolean", errors)
        self.assertIn("spoof_feature_detection must be a boolean", errors)
        self.assertIn("spoof_media_devices must be a boolean", errors)
        self.assertIn("spoof_speech_voices must be a boolean", errors)
        self.assertIn("global_privacy_control must be a boolean", errors)
        self.assertIn("media_devices must be a list", errors)
        self.assertIn("speech_voices must be a list", errors)
        self.assertIn("canvas_noise_level must be a number", errors)
        self.assertIn("canvas_noise_seed must be an integer", errors)
        self.assertIn("font_spoof_count must be an integer", errors)
        self.assertIn("hardware_concurrency must be an integer", errors)
        self.assertIn("device_memory must be a number", errors)
        self.assertIn("geolocation latitude and longitude must be numbers", errors)
        self.assertIn("timezone must be a string or None", errors)
        self.assertIn("do_not_track must be a string or None", errors)
        self.assertIn("webgl_vendor must be a string or None", errors)
        self.assertIn("connection_save_data must be a boolean", errors)
        self.assertIn("battery_charging must be a boolean", errors)
        self.assertIn("screen_height must be an integer", errors)
        self.assertIn("connection_rtt must be an integer", errors)
        self.assertIn("battery_charging_time must be an integer or None", errors)

    def test_invalid_runtime_literals_are_reported(self) -> None:
        config = FingerprintConfig(
            canvas_mode="randomized",  # type: ignore[arg-type]
            webrtc_mode="leaky",  # type: ignore[arg-type]
            tls_profile="chrome_old",  # type: ignore[arg-type]
            platform="Amiga",
            client_hints_architecture="mips",
            client_hints_bitness="128",
            do_not_track="maybe",
            media_devices=[
                {
                    "kind": "sensor",
                    "label": "Device",
                    "deviceId": "device",
                    "groupId": "group",
                    "extra": "value",
                }
            ],
            speech_voices=[
                {
                    "voiceURI": 1,
                    "name": "Voice",
                    "lang": "en-US",
                    "localService": "yes",
                    "default": False,
                    "extra": "value",
                }
            ],
            connection_effective_type="5g",
            connection_type="fiber",
        )

        errors = config.validate()

        self.assertIn("Invalid canvas_mode: randomized", errors)
        self.assertIn("Invalid webrtc_mode: leaky", errors)
        self.assertIn("Invalid tls_profile: chrome_old", errors)
        self.assertIn("Invalid platform: Amiga", errors)
        self.assertIn("Invalid client_hints_architecture: mips", errors)
        self.assertIn("Invalid client_hints_bitness: 128", errors)
        self.assertIn("Invalid do_not_track: maybe", errors)
        self.assertIn("media_devices item 1 has unknown keys: extra", errors)
        self.assertIn("media_devices item 1 has invalid kind: sensor", errors)
        self.assertIn("speech_voices item 1 has unknown keys: extra", errors)
        self.assertIn("speech_voices item 1 voiceURI must be a string", errors)
        self.assertIn("speech_voices item 1 localService must be a boolean", errors)
        self.assertIn("Invalid connection_effective_type: 5g", errors)
        self.assertIn("Invalid connection_type: fiber", errors)

    def test_invalid_geolocation_is_reported(self) -> None:
        errors = FingerprintConfig(geolocation=(120, 200)).validate()

        self.assertIn("geolocation latitude must be between -90 and 90", errors)
        self.assertIn("geolocation longitude must be between -180 and 180", errors)

    def test_invalid_canvas_seed_is_reported(self) -> None:
        errors = FingerprintConfig(canvas_noise_seed=0).validate()

        self.assertIn("canvas_noise_seed must be between 1 and 4294967295", errors)

    def test_captured_canvas_requires_png_data_url(self) -> None:
        errors = FingerprintConfig(canvas_mode="captured").validate()

        self.assertIn("captured canvas mode requires canvas_capture_data_url", errors)

        errors = FingerprintConfig(
            canvas_mode="captured",
            canvas_capture_data_url="https://example.com/canvas.png",
            canvas_capture_width=0,
        ).validate()

        self.assertIn("canvas_capture_data_url must be a PNG data URL", errors)
        self.assertIn("canvas_capture_width must be between 1 and 16384", errors)

    def test_ensure_canvas_seed_keeps_legacy_seed_optional(self) -> None:
        config = FingerprintConfig()

        result = config.ensure_canvas_noise_seed()

        self.assertIs(result, config)
        self.assertIsNone(config.canvas_noise_seed)
        self.assertEqual(config.validate(), [])

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
        self.assertIsNone(data["canvas_noise_seed"])
        self.assertTrue(data["spoof_feature_detection"])
        self.assertTrue(data["spoof_media_devices"])
        self.assertEqual(data["media_devices"], [])
        self.assertTrue(data["spoof_speech_voices"])
        self.assertEqual(data["speech_voices"], [])
        self.assertIsNone(data["do_not_track"])
        self.assertFalse(data["global_privacy_control"])
        self.assertFalse(data["hide_adblock_signs"])

    def test_user_agent_consistency_is_validated(self) -> None:
        errors = FingerprintConfig(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36",
            platform="Win32",
            webgl_renderer="ANGLE (NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)",
            timezone="Europe/Moscow",
            locale=["zh-CN", "zh"],
        ).validate()

        self.assertIn("Macintosh User-Agent requires platform MacIntel", errors)
        self.assertIn("Macintosh User-Agent must not use Direct3D WebGL renderer", errors)
        self.assertIn("timezone Europe/Moscow is inconsistent with primary language zh-CN", errors)


if __name__ == "__main__":
    unittest.main()
