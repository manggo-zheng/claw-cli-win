from __future__ import annotations

from pathlib import Path
import unittest

from claw_tray.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def test_resolves_relative_command_cwd(self) -> None:
        fixture = Path(__file__).resolve().parent / "fixtures" / "config-relative.json"
        config = load_config(fixture)
        expected = (fixture.parent / "service").resolve()
        self.assertEqual(config.service.start.cwd, expected)

    def test_command_status_requires_probe_command(self) -> None:
        fixture = Path(__file__).resolve().parent / "fixtures" / "config-status-missing.json"
        with self.assertRaises(ConfigError):
            load_config(fixture)


if __name__ == "__main__":
    unittest.main()
