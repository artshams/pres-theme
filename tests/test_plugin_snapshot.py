from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sync_plugin_snapshot


class PluginSnapshotTests(unittest.TestCase):
    def test_check_detects_drift_without_writing_actual_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / "expected"
            actual = root / "actual"
            expected.mkdir()
            actual.mkdir()
            (expected / "SKILL.md").write_text("current\n", encoding="utf-8")
            (actual / "SKILL.md").write_text("stale\n", encoding="utf-8")
            before = (actual / "SKILL.md").read_bytes()

            with (
                patch.object(sync_plugin_snapshot, "PLUGIN_SKILL_ROOT", actual),
                patch.object(sync_plugin_snapshot, "PLUGIN_ASSETS", root / "assets"),
                patch.object(sync_plugin_snapshot, "SCREENSHOTS", {}),
                patch.object(sync_plugin_snapshot, "_sync_skill", side_effect=lambda target: _copy_expected(expected, target)),
            ):
                self.assertEqual(sync_plugin_snapshot._check_snapshot(), 1)

            self.assertEqual((actual / "SKILL.md").read_bytes(), before)


def _copy_expected(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for path in source.rglob("*"):
        if path.is_file():
            destination = target / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(path.read_bytes())


if __name__ == "__main__":
    unittest.main()
