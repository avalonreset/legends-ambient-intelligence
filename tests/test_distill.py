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


def _make_audio(filename, mtime, sha, recording_start=None):
    return AudioFile(
        path=Path(f"dummy/{filename}"),
        filename=filename,
        size_bytes=1000,
        last_modified_iso=mtime.isoformat(),
        sha256=sha,
        recording_start_iso=recording_start.isoformat() if recording_start else None,
    )


class TestPromptRecoveryEdge(unittest.TestCase):
    def test_empty_files_raises(self):
        with self.assertRaises(ValueError):
            analyze_prompt_recovery([])

    def test_single_file_has_no_predecessor(self):
        only = _make_audio(
            "solo.wav",
            datetime(2026, 9, 24, 10, 0, 0, tzinfo=timezone.utc),
            "H1",
        )
        plan = analyze_prompt_recovery([only])
        self.assertEqual(plan.status, "latest-only")
        self.assertEqual(plan.reason, "no-predecessor-found")
        self.assertIsNone(plan.predecessor_file)
        self.assertFalse(plan.rollover_detected)
        self.assertIsNone(plan.boundary_gap_seconds)
        self.assertEqual(len(plan.clip_plan), 1)
        self.assertEqual(plan.clip_plan[0].role, "latest-tail")

    def test_tolerance_boundary_exact_match(self):
        pred = _make_audio(
            "a.wav",
            datetime(2026, 9, 24, 10, 15, 0, tzinfo=timezone.utc),
            "H1",
        )
        latest = _make_audio(
            "b.wav",
            datetime(2026, 9, 24, 10, 30, 0, tzinfo=timezone.utc),
            "H2",
            datetime(2026, 9, 24, 10, 15, 2),
        )
        plan = analyze_prompt_recovery([pred, latest])
        self.assertEqual(plan.boundary_gap_seconds, 2.0)
        self.assertTrue(plan.rollover_detected)
        self.assertEqual(plan.status, "include-predecessor-tail")

    def test_tolerance_boundary_just_over(self):
        pred = _make_audio(
            "a.wav",
            datetime(2026, 9, 24, 10, 15, 0, tzinfo=timezone.utc),
            "H1",
        )
        latest = _make_audio(
            "b.wav",
            datetime(2026, 9, 24, 10, 30, 0, tzinfo=timezone.utc),
            "H2",
            datetime(2026, 9, 24, 10, 15, 3),
        )
        plan = analyze_prompt_recovery([pred, latest])
        self.assertFalse(plan.rollover_detected)
        self.assertEqual(plan.status, "latest-only")
        self.assertEqual(plan.reason, "no-rollover-or-continuation-evidence")

    def test_missing_recording_start_skips_gap(self):
        pred = _make_audio(
            "a.wav",
            datetime(2026, 9, 24, 9, 0, 0, tzinfo=timezone.utc),
            "H1",
        )
        latest = _make_audio(
            "b.wav",
            datetime(2026, 9, 24, 10, 0, 0, tzinfo=timezone.utc),
            "H2",
        )
        plan = analyze_prompt_recovery([pred, latest])
        self.assertIsNone(plan.boundary_gap_seconds)
        self.assertFalse(plan.rollover_detected)
        self.assertEqual(plan.status, "latest-only")

    def test_malformed_timestamps_do_not_crash(self):
        pred = AudioFile(
            path=Path("dummy/a.wav"),
            filename="a.wav",
            size_bytes=10,
            last_modified_iso="a",
            sha256="H1",
        )
        latest = AudioFile(
            path=Path("dummy/b.wav"),
            filename="b.wav",
            size_bytes=10,
            last_modified_iso="b",
            sha256="H2",
            recording_start_iso="z",
        )
        plan = analyze_prompt_recovery([pred, latest])
        self.assertIsNone(plan.boundary_gap_seconds)
        self.assertFalse(plan.rollover_detected)
        self.assertEqual(plan.status, "latest-only")

    def test_transcript_variants(self):
        pred = _make_audio("a.wav", datetime(2026, 9, 24, 8, 0, 0, tzinfo=timezone.utc), "H1")
        latest = _make_audio("b.wav", datetime(2026, 9, 24, 10, 0, 0, tzinfo=timezone.utc), "H2")

        for text in (None, "", "   "):
            plan = analyze_prompt_recovery([pred, latest], latest_transcript_text=text)
            self.assertFalse(plan.starts_mid_thought)
            self.assertEqual(plan.status, "latest-only")

        upper = analyze_prompt_recovery([pred, latest], latest_transcript_text="And then we shipped it.")
        self.assertTrue(upper.starts_mid_thought)
        self.assertEqual(upper.status, "include-predecessor-tail")

        padded = analyze_prompt_recovery([pred, latest], latest_transcript_text="  but first we checked.")
        self.assertTrue(padded.starts_mid_thought)

        plain = analyze_prompt_recovery([pred, latest], latest_transcript_text="Hello world today.")
        self.assertFalse(plain.starts_mid_thought)
        self.assertEqual(plain.status, "latest-only")

    def test_negative_tails_clamped_to_zero(self):
        pred = _make_audio("a.wav", datetime(2026, 9, 24, 8, 0, 0, tzinfo=timezone.utc), "H1")
        latest = _make_audio("b.wav", datetime(2026, 9, 24, 10, 0, 0, tzinfo=timezone.utc), "H2")
        plan = analyze_prompt_recovery(
            [pred, latest],
            latest_transcript_text="and so we continue.",
            latest_tail_minutes=-5,
            predecessor_tail_minutes=-2,
        )
        self.assertEqual(plan.status, "include-predecessor-tail")
        for clip in plan.clip_plan:
            self.assertGreaterEqual(clip.tail_seconds, 0)
        self.assertEqual(plan.clip_plan[0].tail_seconds, 0)
        self.assertEqual(plan.clip_plan[1].tail_seconds, 0)


class TestConceptsEdge(unittest.TestCase):
    def test_empty_text_uses_default_summary(self):
        candidate = extract_distilled_candidates("")
        self.assertEqual(candidate.summary, "Ambient capture recording.")
        self.assertEqual(candidate.action_items, [])
        self.assertEqual(candidate.key_themes, [])

    def test_whitespace_text_uses_default_summary(self):
        candidate = extract_distilled_candidates("   \n  ")
        self.assertEqual(candidate.summary, "Ambient capture recording.")

    def test_plain_text_has_no_actions(self):
        candidate = extract_distilled_candidates(
            "The sky was blue over the quiet harbor this morning."
        )
        self.assertEqual(candidate.action_items, [])
        self.assertGreater(len(candidate.raw_takeaways), 0)

    def test_short_text_does_not_crash(self):
        candidate = extract_distilled_candidates("hi")
        self.assertEqual(candidate.summary, "hi")
        self.assertEqual(candidate.action_items, [])


class TestObsidianEdge(unittest.TestCase):
    def _result(self, filename="note.wav"):
        return TranscriptionResult(
            audio_path="",
            filename=filename,
            duration_seconds=10.0,
            language="en",
            text="We decided to ship. You should update the docs.",
            model="mock-v1",
        )

    def test_no_vault_returns_content_only(self):
        candidate = extract_distilled_candidates("We decided to ship today quickly.")
        content, written = generate_obsidian_note(candidate=candidate, result=self._result())
        self.assertIsNone(written)
        self.assertIn("type: ambient-distill", content)
        self.assertIn("Ambient Note:", content)

    def test_slug_with_separators_stays_in_vault(self):
        with tempfile.TemporaryDirectory() as tmp_vault:
            vault = Path(tmp_vault)
            candidate = extract_distilled_candidates("We decided to ship today quickly.")
            content, written = generate_obsidian_note(
                candidate=candidate,
                result=self._result(),
                vault_path=vault,
                note_slug="../evil",
            )
            self.assertIsNotNone(written)
            self.assertEqual(written.parent.resolve(), vault.resolve())
            self.assertNotIn("/", written.name)
            self.assertTrue(written.is_file())

    def test_multiline_items_stay_on_one_line(self):
        candidate = extract_distilled_candidates("line one")
        candidate.raw_takeaways = ["first\nsecond"]
        candidate.action_items = ["do this\nthen that"]
        content, written = generate_obsidian_note(candidate=candidate, result=self._result())
        self.assertIsNone(written)
        self.assertIn("- first second", content)
        self.assertIn("- [ ] do this then that", content)

    def test_vault_path_must_be_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "file.txt"
            blocker.write_text("x", encoding="utf-8")
            candidate = extract_distilled_candidates("We decided to ship today quickly.")
            with self.assertRaises(ValueError):
                generate_obsidian_note(
                    candidate=candidate, result=self._result(), vault_path=blocker
                )


if __name__ == "__main__":
    unittest.main()
