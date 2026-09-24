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


class TestArchiverEdge(unittest.TestCase):
    def test_archive_empty_input(self):
        with tempfile.TemporaryDirectory() as archive_dir:
            arc_path = Path(archive_dir)
            archiver = Archiver(archive_root=arc_path)
            receipt = archiver.archive([], slug="empty")
            self.assertEqual(receipt.status, "no-new-recordings")
            self.assertEqual(receipt.total_scanned, 0)
            self.assertEqual(receipt.new_archived, 0)
            self.assertIsNone(receipt.manifest_path)
            self.assertFalse(receipt.source_mutated)

    def test_known_hashes_skip_corrupted_manifests(self):
        with tempfile.TemporaryDirectory() as archive_dir:
            arc_path = Path(archive_dir)
            bad_dir = arc_path / "2026" / "09" / "24" / "bad"
            bad_dir.mkdir(parents=True)
            (bad_dir / "manifest.json").write_text("{not valid json", encoding="utf-8")

            good_dir = arc_path / "2026" / "09" / "24" / "good"
            good_dir.mkdir(parents=True)
            known_hash = "AB" * 32
            (good_dir / "manifest.json").write_text(
                json.dumps({"recordings": [{"sha256": known_hash}]}), encoding="utf-8"
            )

            archiver = Archiver(archive_root=arc_path)
            known = archiver.get_known_hashes()
            self.assertIn(known_hash, known)

    def test_known_hashes_tolerate_missing_keys(self):
        with tempfile.TemporaryDirectory() as archive_dir:
            arc_path = Path(archive_dir)
            odd_dir = arc_path / "odd"
            odd_dir.mkdir(parents=True)
            (odd_dir / "manifest.json").write_text(json.dumps({}), encoding="utf-8")
            none_dir = arc_path / "none"
            none_dir.mkdir(parents=True)
            (none_dir / "manifest.json").write_text(
                json.dumps({"recordings": None}), encoding="utf-8"
            )
            archiver = Archiver(archive_root=arc_path)
            self.assertEqual(archiver.get_known_hashes(), set())

    def test_known_hashes_missing_archive_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist"
            archiver = Archiver(archive_root=missing)
            self.assertEqual(archiver.get_known_hashes(), set())

    def test_archive_slug_sanitization(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as archive_dir:
            src_path = Path(source_dir)
            f1 = src_path / "a.wav"
            f1.write_bytes(b"BYTES")
            audio = AudioFile.from_path(f1)

            archiver = Archiver(archive_root=Path(archive_dir))
            receipt = archiver.archive([audio], slug="!!!")
            self.assertEqual(receipt.status, "archived")
            self.assertIn("ingest", Path(receipt.ingest_dir).name)

            f2 = src_path / "b.wav"
            f2.write_bytes(b"OTHER")
            audio2 = AudioFile.from_path(f2)
            receipt2 = archiver.archive([audio2], slug="My Session 01")
            self.assertIn("my-session-01", Path(receipt2.ingest_dir).name)

    def test_archive_duplicate_filenames_preserved(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as archive_dir:
            src_path = Path(source_dir)
            (src_path / "sub1").mkdir()
            (src_path / "sub2").mkdir()
            (src_path / "sub1" / "same.wav").write_bytes(b"DATA_ONE")
            (src_path / "sub2" / "same.wav").write_bytes(b"DATA_TWO")
            aud1 = AudioFile.from_path(src_path / "sub1" / "same.wav")
            aud2 = AudioFile.from_path(src_path / "sub2" / "same.wav")

            archiver = Archiver(archive_root=Path(archive_dir))
            receipt = archiver.archive([aud1, aud2], slug="dup")
            self.assertEqual(receipt.new_archived, 2)

            raw_dir = Path(receipt.manifest_path).parent / "raw"
            raw_files = sorted(p.name for p in raw_dir.iterdir())
            self.assertEqual(len(raw_files), 2)

            manifest = json.loads(Path(receipt.manifest_path).read_text(encoding="utf-8"))
            rel_paths = [r["relative_path"] for r in manifest["recordings"]]
            self.assertEqual(len(set(rel_paths)), 2)
            for rel in rel_paths:
                self.assertTrue((Path(receipt.manifest_path).parent / rel).is_file())

    def test_archive_preserves_source_files(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as archive_dir:
            src_path = Path(source_dir)
            f1 = src_path / "keep.wav"
            f1.write_bytes(b"ORIGINAL_BYTES")
            audio = AudioFile.from_path(f1)

            archiver = Archiver(archive_root=Path(archive_dir))
            receipt = archiver.archive([audio], slug="safe")
            self.assertEqual(receipt.status, "archived")
            self.assertFalse(receipt.source_mutated)
            self.assertTrue(f1.is_file())
            self.assertEqual(f1.read_bytes(), b"ORIGINAL_BYTES")

    def test_archive_case_insensitive_dedupe(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as archive_dir:
            src_path = Path(source_dir)
            arc_path = Path(archive_dir)
            f1 = src_path / "c.wav"
            f1.write_bytes(b"CASE_BYTES")
            audio = AudioFile.from_path(f1)

            prior = arc_path / "prior"
            prior.mkdir(parents=True)
            (prior / "manifest.json").write_text(
                json.dumps({"recordings": [{"sha256": audio.sha256.lower()}]}),
                encoding="utf-8",
            )

            archiver = Archiver(archive_root=arc_path)
            receipt = archiver.archive([audio], slug="case")
            self.assertEqual(receipt.status, "no-new-recordings")
            self.assertEqual(receipt.already_archived, 1)

    def test_archive_failure_leaves_no_manifest(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as archive_dir:
            src_path = Path(source_dir)
            arc_path = Path(archive_dir)
            f1 = src_path / "gone.wav"
            f1.write_bytes(b"VANISHING")
            audio = AudioFile.from_path(f1)
            f1.unlink()

            archiver = Archiver(archive_root=arc_path)
            with self.assertRaises(OSError):
                archiver.archive([audio], slug="fail")
            self.assertEqual(list(arc_path.glob("**/manifest.json")), [])


if __name__ == "__main__":
    unittest.main()
