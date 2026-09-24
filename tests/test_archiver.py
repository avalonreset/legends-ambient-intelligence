"""Unit tests for content-addressable audio archiving and deduplication."""

import json
from pathlib import Path
import tempfile
import unittest

from legends_ambient.archiver import Archiver
from legends_ambient.ingest.sources import AudioFile


class TestArchiver(unittest.TestCase):
    def test_archive_new_files_and_deduplicate(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as archive_dir:
            src_path = Path(source_dir)
            arc_path = Path(archive_dir)

            # Create two dummy audio files
            f1 = src_path / "rec1.wav"
            f1.write_bytes(b"AUDIO_DATA_ALPHA")
            f2 = src_path / "rec2.wav"
            f2.write_bytes(b"AUDIO_DATA_BETA")

            audio1 = AudioFile.from_path(f1)
            audio2 = AudioFile.from_path(f2)

            archiver = Archiver(archive_root=arc_path)

            # Pass 1: Archive both files
            receipt1 = archiver.archive([audio1, audio2], slug="test-pass")
            self.assertEqual(receipt1.status, "archived")
            self.assertEqual(receipt1.new_archived, 2)
            self.assertIsNotNone(receipt1.manifest_path)

            manifest_file = Path(receipt1.manifest_path)
            self.assertTrue(manifest_file.is_file())
            manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            self.assertEqual(manifest_data["recordings_count"], 2)

            # Check raw copied files
            raw_dir = manifest_file.parent / "raw"
            self.assertTrue((raw_dir / "rec1.wav").is_file())
            self.assertTrue((raw_dir / "rec2.wav").is_file())
            self.assertTrue((manifest_file.parent / "SHA256SUMS.txt").is_file())

            # Pass 2: Repeat pass with same files -> status should be no-new-recordings
            receipt2 = archiver.archive([audio1, audio2], slug="test-pass")
            self.assertEqual(receipt2.status, "no-new-recordings")
            self.assertEqual(receipt2.new_archived, 0)
            self.assertEqual(receipt2.already_archived, 2)

            # Pass 3: Add a 3rd new file
            f3 = src_path / "rec3.wav"
            f3.write_bytes(b"AUDIO_DATA_GAMMA")
            audio3 = AudioFile.from_path(f3)

            receipt3 = archiver.archive([audio1, audio2, audio3], slug="test-pass-two")
            self.assertEqual(receipt3.status, "archived")
            self.assertEqual(receipt3.new_archived, 1)
            self.assertEqual(receipt3.already_archived, 2)

    def test_what_if_mode(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as archive_dir:
            src_path = Path(source_dir)
            arc_path = Path(archive_dir)

            f1 = src_path / "preview.wav"
            f1.write_bytes(b"PREVIEW_BYTES")
            audio = AudioFile.from_path(f1)

            archiver = Archiver(archive_root=arc_path)
            receipt = archiver.archive([audio], slug="dry-run", what_if=True)

            self.assertEqual(receipt.status, "dry-run")
            self.assertEqual(receipt.new_archived, 1)
            # Verify no actual files were written
            self.assertEqual(len(list(arc_path.glob("**/*"))), 0)


if __name__ == "__main__":
    unittest.main()
