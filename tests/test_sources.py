"""Unit tests for audio source scanning and timestamp parsing."""

from datetime import datetime
from pathlib import Path
import tempfile
import unittest

from legends_ambient.ingest.device_source import DeviceSource, find_mounted_device
from legends_ambient.ingest.local_source import LocalDirectorySource
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


class TestSourcesEdge(unittest.TestCase):
    def test_scan_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.assertEqual(scan_audio_directory(Path(tmp_dir)), [])

    def test_scan_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing = Path(tmp_dir) / "nope"
            self.assertEqual(scan_audio_directory(missing), [])

    def test_scan_file_path_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "file.wav"
            target.write_bytes(b"RIFF")
            self.assertEqual(scan_audio_directory(target), [])

    def test_scan_non_audio_only(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
            (tmp_path / "image.png").write_bytes(b"PNG")
            self.assertEqual(scan_audio_directory(tmp_path), [])

    def test_scan_uppercase_extension(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "REC.WAV").write_bytes(b"RIFF")
            scanned = scan_audio_directory(tmp_path)
            self.assertEqual([p.name for p in scanned], ["REC.WAV"])

    def test_scan_recursive(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "top.wav").write_bytes(b"RIFF")
            sub = tmp_path / "sub"
            sub.mkdir()
            (sub / "nested.mp3").write_bytes(b"ID3")

            flat = scan_audio_directory(tmp_path, recursive=False)
            self.assertEqual([p.name for p in flat], ["top.wav"])

            deep = scan_audio_directory(tmp_path, recursive=True)
            self.assertEqual(sorted(p.name for p in deep), ["nested.mp3", "top.wav"])

    def test_parse_invalid_calendar_dates(self):
        self.assertIsNone(parse_recording_timestamp("VR13_45_99-99_99_99.WAV"))
        self.assertIsNone(parse_recording_timestamp("2026-13-45_10-00-00.wav"))
        self.assertIsNone(parse_recording_timestamp("2026-09-24_25-00-00.wav"))

    def test_audiofile_missing_path_raises(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing = Path(tmp_dir) / "gone.wav"
            with self.assertRaises(OSError):
                AudioFile.from_path(missing)

    def test_compute_hash_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "empty.wav"
            target.write_bytes(b"")
            self.assertEqual(
                compute_file_sha256(target),
                "E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855",
            )

    def test_local_source_missing_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            src = LocalDirectorySource(Path(tmp_dir) / "missing")
            self.assertFalse(src.exists())
            self.assertEqual(src.discover(), [])

    def test_local_source_discovers_audio(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "a.wav").write_bytes(b"RIFF")
            (tmp_path / "b.txt").write_text("x", encoding="utf-8")
            src = LocalDirectorySource(tmp_path)
            self.assertTrue(src.exists())
            found = src.discover()
            self.assertEqual([a.filename for a in found], ["a.wav"])

    def test_device_source_prefers_recorded_subfolder(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "root.wav").write_bytes(b"RIFF")
            rec = root / "RECORDED"
            rec.mkdir()
            (rec / "field.wav").write_bytes(b"RIFF")

            dev = DeviceSource(root)
            preferred = dev.discover()
            self.assertEqual([a.filename for a in preferred], ["field.wav"])

            all_files = dev.discover(subfolder=None)
            self.assertEqual(sorted(a.filename for a in all_files), ["field.wav", "root.wav"])

    def test_device_source_missing_root(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dev = DeviceSource(Path(tmp_dir) / "missing")
            self.assertEqual(dev.discover(), [])

    def test_find_mounted_device_empty_label(self):
        self.assertIsNone(find_mounted_device(""))
        self.assertIsNone(find_mounted_device("   "))

    def test_find_mounted_device_unlikely_label(self):
        self.assertIsNone(find_mounted_device("NO_SUCH_VOLUME_XYZ_123"))


if __name__ == "__main__":
    unittest.main()
