"""Unit tests for offline doctor health checks."""

import sys
from pathlib import Path
import tempfile
import unittest

from legends_ambient.doctor import Doctor


class TestDoctor(unittest.TestCase):
    def test_run_all_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = Doctor(archive_root=Path(tmp)).run_all()
            names = [r.name for r in results]
            for expected in (
                "python",
                "archive_dir",
                "audio_tools",
                "whisper_asr",
                "parakeet_asr",
                "hardware_device",
            ):
                self.assertIn(expected, names)
            for r in results:
                self.assertIn(r.status, ("OK", "WARN", "INFO", "FAIL"))

    def test_python_check_matches_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = Doctor(archive_root=Path(tmp)).run_all()
            py = next(r for r in results if r.name == "python")
            if sys.version_info >= (3, 11):
                self.assertEqual(py.status, "OK")
            else:
                self.assertEqual(py.status, "FAIL")

    def test_archive_failure_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "file.txt"
            blocker.write_text("x", encoding="utf-8")
            results = Doctor(archive_root=blocker).run_all()
            entry = next(r for r in results if r.name == "archive_dir")
            self.assertEqual(entry.status, "FAIL")

    def test_missing_device_is_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = Doctor(
                archive_root=Path(tmp), device_label="NO_SUCH_VOLUME_XYZ_123"
            ).run_all()
            entry = next(r for r in results if r.name == "hardware_device")
            self.assertEqual(entry.status, "INFO")


if __name__ == "__main__":
    unittest.main()
