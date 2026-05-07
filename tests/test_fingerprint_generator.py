from __future__ import annotations

import unittest

from models.fingerprint_generator import (
    FINGERPRINT_PRESETS,
    generate_fingerprint_config,
    generate_fingerprint_profile,
)


class FingerprintGeneratorTest(unittest.TestCase):
    def test_generated_config_is_valid_and_has_user_agent(self) -> None:
        for _ in range(25):
            config = generate_fingerprint_config()

            self.assertIsNotNone(config.user_agent)
            self.assertIsNone(config.canvas_noise_seed)
            self.assertEqual(config.canvas_mode, "fixed")
            self.assertIsNotNone(config.screen_width)
            self.assertIsNotNone(config.screen_height)
            self.assertTrue(config.spoof_media_devices)
            self.assertEqual(len(config.media_devices), 3)
            self.assertIsNotNone(config.connection_effective_type)
            self.assertEqual(config.validate(), [])

            if "Windows NT" in config.user_agent:
                self.assertIn(config.platform, {"Win32", "Win64"})
                self.assertNotIn("Apple", config.webgl_renderer or "")
            if "Macintosh" in config.user_agent:
                self.assertEqual(config.platform, "MacIntel")
                self.assertNotIn("Direct3D", config.webgl_renderer or "")

    def test_generated_configs_get_device_based_canvas_noise_levels(self) -> None:
        levels = {
            generate_fingerprint_config(preset).canvas_noise_level for preset in FINGERPRINT_PRESETS
        }

        self.assertGreater(len(levels), 1)

    def test_same_device_preset_uses_same_canvas_profile(self) -> None:
        preset = FINGERPRINT_PRESETS[0]

        first = generate_fingerprint_config(preset)
        second = generate_fingerprint_config(preset)

        self.assertIsNone(first.canvas_noise_seed)
        self.assertIsNone(second.canvas_noise_seed)
        self.assertEqual(first.canvas_noise_level, second.canvas_noise_level)
        self.assertEqual(first.media_devices, second.media_devices)

    def test_generated_profile_uses_requested_name(self) -> None:
        profile = generate_fingerprint_profile("Generated fingerprint")

        self.assertEqual(profile.name, "Generated fingerprint")
        self.assertEqual(profile.config.validate(), [])


if __name__ == "__main__":
    unittest.main()
