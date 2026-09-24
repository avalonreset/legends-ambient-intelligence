"""Unit tests for audio source scanning and timestamp parsing."""

from datetime import datetime
from pathlib import Path
import tempfile
import unittest

from legends_ambient.ingest.sources import (
    AudioFile,
    compute_file_sha256,
    parse_recording_timestamp,
    scan_audio_directory,
)


class TestSources(unittest.TestCase):
    def test_parse_recording_timestamp_kt5000(self):
        # Format: VRmm_dd_yy-hh_mm_ss.WAV (standard hardware recorder format)
        parsed_us = parse_recording_timestamp("VR09_24_26-10_15_30.WAV")
        self.assertIsNotNone(parsed_us)
        self.assertEqual(parsed_us, datetime(2026, 9, 24, 10, 15, 30))

        # Format: VRyy_mm_dd-hh_mm_ss.WAV (ISO variant)
        parsed_iso = parse_recording_timestamp("VR26_09_24-10_15_30.WAV")
        self.assertIsNotNone(parsed_iso)
        self.assertEqual(parsed_iso, datetime(2026, 9, 24, 10, 15, 30))

        parsed_r = parse_recording_timestamp("R07_17_26-00_48_10.WAV")
        self.assertIsNotNone(parsed_r)
        self.assertEqual(parsed_r, datetime(2026, 7, 17, 0, 48, 10))

    def test_parse_recording_timestamp_iso(self):
        parsed = parse_recording_timestamp("2026-09-24_10-15-30.wav")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed, datetime(2026, 9, 24, 10, 15, 30))

        parsed_compact = parse_recording_timestamp("20260924_101530.mp3")
        self.assertIsNotNone(parsed_compact)
        self.assertEqual(parsed_compact, datetime(2026, 9, 24, 10, 15, 30))

    def test_parse_recording_timestamp_invalid(self):
        self.assertIsNone(parse_recording_timestamp("not_a_recording.wav"))
        self.assertIsNone(parse_recording_timestamp("test.txt"))

    def test_scan_audio_directory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "rec1.wav").write_bytes(b"RIFFdummywav1")
            (tmp_path / "rec2.mp3").write_bytes(b"ID3dummymp3")
            (tmp_path / "notes.txt").write_text("not audio", encoding="utf-8")

            scanned = scan_audio_directory(tmp_path)
            self.assertEqual(len(scanned), 2)
            names = [p.name for p in scanned]
            self.assertIn("rec1.wav", names)
            self.assertIn("rec2.mp3", names)
            self.assertNotIn("notes.txt", names)

    def test_compute_file_sha256_and_audio_file(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"SAMPLE_AUDIO_DATA_FOR_HASHING")
            temp_path = Path(f.name)

        try:
            expected_hash = "2CF66ACB13C2FBF53E6EDF2F82DD44222A9F0851F9E9DB619FC13258B87F8D74"
            actual_hash = compute_file_sha256(temp_path)
            self.assertEqual(actual_hash, expected_hash)

            audio_file = AudioFile.from_path(temp_path)
            self.assertEqual(audio_file.filename, temp_path.name)
            self.assertEqual(audio_file.size_bytes, 29)
            self.assertEqual(audio_file.sha256, expected_hash)
        finally:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
