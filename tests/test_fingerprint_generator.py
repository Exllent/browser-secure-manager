from __future__ import annotations

import unittest

from models.fingerprint_generator import generate_fingerprint_config, generate_fingerprint_profile


class FingerprintGeneratorTest(unittest.TestCase):
    def test_generated_config_is_valid_and_has_user_agent(self) -> None:
        for _ in range(25):
            config = generate_fingerprint_config()

            self.assertIsNotNone(config.user_agent)
            self.assertIsNotNone(config.canvas_noise_seed)
            self.assertEqual(config.validate(), [])

    def test_generated_configs_get_different_canvas_seeds(self) -> None:
        seeds = {generate_fingerprint_config().canvas_noise_seed for _ in range(20)}

        self.assertGreater(len(seeds), 1)

    def test_generated_profile_uses_requested_name(self) -> None:
        profile = generate_fingerprint_profile("Generated fingerprint")

        self.assertEqual(profile.name, "Generated fingerprint")
        self.assertEqual(profile.config.validate(), [])


if __name__ == "__main__":
    unittest.main()
