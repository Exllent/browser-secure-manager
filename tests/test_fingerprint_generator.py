from __future__ import annotations

import unittest

from models.fingerprint_generator import (
    FINGERPRINT_PRESETS,
    generate_fingerprint_config,
    generate_fingerprint_profile,
)
from models.fingerprint_profile import FingerprintProfile
from models.fingerprint_summary import build_fingerprint_summary_sections


class FingerprintGeneratorTest(unittest.TestCase):
    def test_all_device_presets_are_valid(self) -> None:
        self.assertGreaterEqual(len(FINGERPRINT_PRESETS), 16)

        for preset in FINGERPRINT_PRESETS:
            with self.subTest(label=preset.label):
                config = generate_fingerprint_config(preset)

                self.assertEqual(config.validate(), [])
                self.assertLessEqual(config.screen_avail_width or 0, config.screen_width or 0)
                self.assertLessEqual(config.screen_avail_height or 0, config.screen_height or 0)

                if preset.label.startswith("WIN"):
                    self.assertIn("Windows NT", preset.user_agent)
                    self.assertEqual(preset.platform, "Win32")
                    self.assertIn("Direct3D", preset.webgl_renderer)
                if preset.label.startswith("MAC"):
                    self.assertIn("Macintosh", preset.user_agent)
                    self.assertEqual(preset.platform, "MacIntel")
                    self.assertNotIn("Direct3D", preset.webgl_renderer)
                    if preset.client_hints_architecture == "arm":
                        self.assertIn("Apple", preset.webgl_renderer)
                if preset.label.startswith("LINUX"):
                    self.assertIn("Linux", preset.user_agent)
                    self.assertTrue(preset.platform.startswith("Linux"))
                    self.assertNotIn("Direct3D", preset.webgl_renderer)

    def test_preset_labels_are_informative_device_names(self) -> None:
        forbidden_tokens = (
            "Chrome",
            "Moscow",
            "New York",
            "Seattle",
            "Austin",
            "Tokyo",
            "London",
            "Berlin",
            "Paris",
            "Chicago",
            "Los Angeles",
            "San Francisco",
        )

        for preset in FINGERPRINT_PRESETS:
            with self.subTest(label=preset.label):
                self.assertRegex(
                    preset.label,
                    r"^(WIN|MAC|LINUX) .+ [A-Z]{2} \| .+ \| .+ \| \d+C \d+GB \| \d+x\d+$",
                )
                for token in forbidden_tokens:
                    self.assertNotIn(token, preset.label)

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
            self.assertTrue(config.spoof_speech_voices)
            self.assertGreaterEqual(len(config.speech_voices), 1)
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
        self.assertEqual(first.speech_voices, second.speech_voices)

    def test_generated_profile_uses_requested_name(self) -> None:
        profile = generate_fingerprint_profile("Generated fingerprint")

        self.assertEqual(profile.name, "Generated fingerprint")
        self.assertEqual(profile.config.validate(), [])

    def test_generated_profile_default_name_is_informative(self) -> None:
        profile = generate_fingerprint_profile()

        self.assertIn("|", profile.name)
        self.assertNotIn("Chrome", profile.name)
        self.assertEqual(profile.config.validate(), [])

    def test_fingerprint_summary_has_grouped_device_information(self) -> None:
        config = generate_fingerprint_config(FINGERPRINT_PRESETS[0])
        profile = FingerprintProfile(id=None, name=FINGERPRINT_PRESETS[0].label, config=config)

        sections = build_fingerprint_summary_sections(profile)
        titles = {section.title for section in sections}
        flattened = {label: value for section in sections for label, value in section.rows}

        self.assertIn("Identity", titles)
        self.assertIn("Hardware", titles)
        self.assertIn("Graphics", titles)
        self.assertEqual(flattened["Country"], "RU")
        self.assertIn("RTX 3060", flattened["GPU"])


if __name__ == "__main__":
    unittest.main()
