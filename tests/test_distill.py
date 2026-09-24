"""Unit tests for prompt recovery, concept extraction, and Obsidian export."""

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from legends_ambient.distill.concepts import extract_distilled_candidates
from legends_ambient.distill.obsidian_export import generate_obsidian_note
from legends_ambient.distill.prompt_recovery import analyze_prompt_recovery
from legends_ambient.ingest.sources import AudioFile
from legends_ambient.transcribe.engine import TranscriptionResult


class TestDistill(unittest.TestCase):
    def test_prompt_recovery_rollover(self):
        # File 1 closed at 10:15:00
        # File 2 encoded timestamp is 10:15:01 (gap = 1.0s, within tolerance 2.0s)
        f1 = AudioFile(
            path=Path("dummy/VR26_09_24-10_00_00.WAV"),
            filename="VR26_09_24-10_00_00.WAV",
            size_bytes=1000,
            last_modified_iso=datetime(2026, 9, 24, 10, 15, 0, tzinfo=timezone.utc).isoformat(),
            sha256="HASH1",
            recording_start_iso=datetime(2026, 9, 24, 10, 0, 0).isoformat(),
        )
        f2 = AudioFile(
            path=Path("dummy/VR26_09_24-10_15_01.WAV"),
            filename="VR26_09_24-10_15_01.WAV",
            size_bytes=1000,
            last_modified_iso=datetime(2026, 9, 24, 10, 30, 0, tzinfo=timezone.utc).isoformat(),
            sha256="HASH2",
            recording_start_iso=datetime(2026, 9, 24, 10, 15, 1).isoformat(),
        )

        plan = analyze_prompt_recovery([f1, f2], latest_tail_minutes=15, predecessor_tail_minutes=5)
        self.assertEqual(plan.status, "include-predecessor-tail")
        self.assertTrue(plan.rollover_detected)
        self.assertEqual(len(plan.clip_plan), 2)
        self.assertEqual(plan.clip_plan[0].role, "predecessor-tail")
        self.assertEqual(plan.clip_plan[1].role, "latest-tail")

    def test_prompt_recovery_continuation_cue(self):
        # Independent timestamps, but newest transcript starts with 'and then'
        f1 = AudioFile(
            path=Path("dummy/rec1.wav"),
            filename="rec1.wav",
            size_bytes=1000,
            last_modified_iso=datetime(2026, 9, 24, 8, 0, 0, tzinfo=timezone.utc).isoformat(),
            sha256="HASH1",
        )
        f2 = AudioFile(
            path=Path("dummy/rec2.wav"),
            filename="rec2.wav",
            size_bytes=1000,
            last_modified_iso=datetime(2026, 9, 24, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
            sha256="HASH2",
        )

        plan = analyze_prompt_recovery(
            [f1, f2],
            latest_transcript_text="and because of that we need to publish the module today.",
        )
        self.assertEqual(plan.status, "include-predecessor-tail")
        self.assertTrue(plan.starts_mid_thought)

    def test_extract_concepts_and_obsidian_export(self):
        sample_transcript = (
            "We had a long discussion about audio pipelines. "
            "We decided to release the new ambient intelligence package today. "
            "You need to make sure to update the documentation and publish the release. "
            "The architecture is modular and runs locally."
        )
        candidates = extract_distilled_candidates(sample_transcript)
        self.assertGreater(len(candidates.action_items), 0)
        self.assertTrue(any("make sure to" in a.lower() for a in candidates.action_items))

        with tempfile.TemporaryDirectory() as tmp_vault:
            vault_path = Path(tmp_vault)
            res = TranscriptionResult(
                audio_path="",
                filename="meeting_note_01.wav",
                duration_seconds=124.5,
                language="en",
                text=sample_transcript,
                model="mock-v1",
            )
            content, written = generate_obsidian_note(
                candidate=candidates,
                result=res,
                vault_path=vault_path,
                note_slug="meeting_note_01",
            )

            self.assertIsNotNone(written)
            self.assertTrue(written.is_file())
            note_text = written.read_text(encoding="utf-8")
            self.assertIn("type: ambient-distill", note_text)
            self.assertIn("meeting_note_01.wav", note_text)
            self.assertIn("Action candidates", note_text)


if __name__ == "__main__":
    unittest.main()
