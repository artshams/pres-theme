from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.finalize_quick_deck import _completion_status, _run, _thresholds


class FinalizeQuickDeckTests(unittest.TestCase):
    def test_warning_only_preflight_is_accepted(self) -> None:
        records: list[dict[str, object]] = []
        completed = subprocess.CompletedProcess(["preflight"], 1, stdout="warning\n")
        with patch("scripts.finalize_quick_deck.subprocess.run", return_value=completed):
            accepted = _run(
                "preflight",
                ["preflight"],
                records,
                accepted_returncodes=(0, 1),
            )
        self.assertTrue(accepted)
        self.assertTrue(records[0]["accepted"])
        self.assertGreaterEqual(float(records[0]["duration_seconds"]), 0.0)
        with tempfile.TemporaryDirectory() as tmp:
            status = _completion_status(records, Path(tmp))
        self.assertEqual(status["failure_category"], "passed")

    def test_preflight_error_remains_blocking(self) -> None:
        records: list[dict[str, object]] = []
        completed = subprocess.CompletedProcess(["preflight"], 2, stdout="error\n")
        with patch("scripts.finalize_quick_deck.subprocess.run", return_value=completed):
            accepted = _run(
                "preflight",
                ["preflight"],
                records,
                accepted_returncodes=(0, 1),
            )
        self.assertFalse(accepted)
        with tempfile.TemporaryDirectory() as tmp:
            status = _completion_status(records, Path(tmp))
        self.assertEqual(status["failure_category"], "outline_preflight")

    def test_quick_defaults_preserve_readability(self) -> None:
        self.assertEqual(_thresholds({}, None, None, None), (16.0, 13.0, 9.0))


if __name__ == "__main__":
    unittest.main()
