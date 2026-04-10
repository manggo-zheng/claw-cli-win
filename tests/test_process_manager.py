from __future__ import annotations

import sys
import unittest

from claw_tray.config import CommandConfig, ServiceConfig, StatusConfig
from claw_tray.process_manager import ProcessManager, run_command


class ProcessManagerTests(unittest.TestCase):
    def test_start_and_stop_managed_process(self) -> None:
        manager = ProcessManager(
            ServiceConfig(
                auto_start=False,
                start=CommandConfig(
                    args=(
                        sys.executable,
                        "-c",
                        "import time; time.sleep(30)",
                    ),
                    hide_window=True,
                ),
                status=StatusConfig(),
            )
        )

        started = manager.start()
        self.assertEqual(started.state, "running")
        self.assertIsNotNone(started.pid)

        stopped = manager.stop(timeout=3)
        self.assertEqual(stopped.state, "stopped")
        self.assertIsNone(stopped.pid)

    def test_waiting_command_captures_output(self) -> None:
        result = run_command(
            CommandConfig(
                args=(sys.executable, "-c", "print('hello')"),
                wait=True,
                hide_window=True,
            ),
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "hello")


if __name__ == "__main__":
    unittest.main()
