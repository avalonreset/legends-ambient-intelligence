"""Unit tests for transcript engine, mock backend, and sidecar artifact writers."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from legends_ambient.transcribe.engine import (
    Transcriber,
    TranscriptionResult,
    TranscriptSegment,
    WordTiming,
)
from legends_ambient.transcribe.mock_backend import MockTranscriber
from legends_ambient.transcribe.parakeet_backend import ParakeetTranscriber
from legends_ambient.transcribe.whisper_backend import WhisperTranscriber
from legends_ambient.transcribe.writers import (
    format_timestamp_srt,
    format_timestamp_vtt,
    write_transcript_artifacts,
    write_transcript_index,
)


class TestTranscribe(unittest.TestCase):
    def test_timestamp_formatting(self):
        self.assertEqual(format_timestamp_srt(0.0), "00:00:00,000")
        self.assertEqual(format_timestamp_srt(65.5), "00:01:05,500")
        self.assertEqual(format_timestamp_srt(3661.125), "01:01:01,125")

        self.assertEqual(format_timestamp_vtt(0.0), "00:00:00.000")
        self.assertEqual(format_timestamp_vtt(65.5), "00:01:05.500")

    def test_mock_transcriber_and_sidecar_writers(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            dummy_audio = tmp_path / "recording_01.wav"
            dummy_audio.write_bytes(b"RIFF_FAKE_AUDIO")

            mock = MockTranscriber(sample_text="Testing ambient capture and prompt continuation.")
            res = mock.transcribe(dummy_audio)

            self.assertEqual(res.filename, "recording_01.wav")
            self.assertGreater(res.duration_seconds, 0)
            self.assertEqual(len(res.segments), 1)

            out_dir = tmp_path / "transcripts"
            artifacts = write_transcript_artifacts(res, out_dir)

            self.assertIn("txt", artifacts)
            self.assertIn("json", artifacts)
            self.assertIn("srt", artifacts)
            self.assertIn("vtt", artifacts)
            self.assertIn("words", artifacts)

            # Validate TXT
            self.assertEqual(
                artifacts["txt"].read_text(encoding="utf-8").strip(),
                "Testing ambient capture and prompt continuation.",
            )

            # Validate JSON
            json_data = json.loads(artifacts["json"].read_text(encoding="utf-8"))
            self.assertEqual(json_data["filename"], "recording_01.wav")
            self.assertEqual(len(json_data["segments"]), 1)

            # Validate SRT
            srt_content = artifacts["srt"].read_text(encoding="utf-8")
            self.assertIn("00:00:00,000 -->", srt_content)
            self.assertIn("Testing ambient capture", srt_content)

            # Validate index
            index_path = out_dir / "index.md"
            write_transcript_index([res], index_path)
            self.assertTrue(index_path.is_file())
            index_content = index_path.read_text(encoding="utf-8")
            self.assertIn("Transcript index", index_content)
            self.assertIn("recording_01", index_content)


class TestTranscribeEdge(unittest.TestCase):
    def test_timestamp_rounding_carry(self):
        self.assertEqual(format_timestamp_srt(1.9999), "00:00:02,000")
        self.assertEqual(format_timestamp_srt(59.9999), "00:01:00,000")
        self.assertEqual(format_timestamp_srt(3599.9999), "01:00:00,000")
        self.assertEqual(format_timestamp_vtt(1.9999), "00:00:02.000")
        self.assertEqual(format_timestamp_vtt(61.9999), "00:01:02.000")

    def test_timestamp_negative_clamped(self):
        self.assertEqual(format_timestamp_srt(-5.0), "00:00:00,000")
        self.assertEqual(format_timestamp_vtt(-0.1), "00:00:00.000")

    def test_mock_empty_text(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dummy = Path(tmp_dir) / "empty.wav"
            dummy.write_bytes(b"RIFF")
            res = MockTranscriber(sample_text="").transcribe(dummy)
            self.assertEqual(res.text, "")
            self.assertEqual(res.total_words, 0)
            self.assertEqual(len(res.segments), 1)

    def test_total_words_fallback(self):
        text_only = TranscriptionResult(
            audio_path="",
            filename="a.wav",
            duration_seconds=1.0,
            language="en",
            text="one two three",
        )
        self.assertEqual(text_only.total_words, 3)

        with_words = TranscriptionResult(
            audio_path="",
            filename="b.wav",
            duration_seconds=1.0,
            language="en",
            text="ignored",
            segments=[
                TranscriptSegment(
                    id=0,
                    start=0.0,
                    end=1.0,
                    text="hi there",
                    words=[
                        WordTiming(word="hi", start=0.0, end=0.5),
                        WordTiming(word="there", start=0.5, end=1.0),
                    ],
                )
            ],
        )
        self.assertEqual(with_words.total_words, 2)

    def test_writers_empty_segments(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            res = TranscriptionResult(
                audio_path="",
                filename="silent.wav",
                duration_seconds=0.0,
                language="en",
                text="",
                segments=[],
                model="mock-v1",
            )
            artifacts = write_transcript_artifacts(res, Path(tmp_dir))
            self.assertEqual(artifacts["srt"].read_text(encoding="utf-8"), "")
            vtt = artifacts["vtt"].read_text(encoding="utf-8")
            self.assertTrue(vtt.startswith("WEBVTT"))
            words = json.loads(artifacts["words"].read_text(encoding="utf-8"))
            self.assertEqual(words, [])
            payload = json.loads(artifacts["json"].read_text(encoding="utf-8"))
            self.assertEqual(payload["segments"], [])

    def test_index_empty_results(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            index_path = Path(tmp_dir) / "index.md"
            write_transcript_index([], index_path)
            content = index_path.read_text(encoding="utf-8")
            self.assertIn("Transcript index", content)

    def test_backends_follow_transcriber_contract(self):
        for cls in (MockTranscriber, WhisperTranscriber, ParakeetTranscriber):
            self.assertIn(Transcriber, cls.__mro__)
            self.assertTrue(callable(getattr(cls(), "transcribe", None)))

    def test_whisper_availability_is_bool(self):
        self.assertIsInstance(WhisperTranscriber().is_available(), bool)

    def test_whisper_transcribe_unavailable_raises(self):
        transcriber = WhisperTranscriber()
        with mock.patch.object(WhisperTranscriber, "_get_model", return_value=None):
            with mock.patch("legends_ambient.transcribe.whisper_backend.shutil.which", return_value=None):
                with self.assertRaises(RuntimeError):
                    transcriber.transcribe(Path("dummy.wav"))

    def test_parakeet_unavailable_raises(self):
        transcriber = ParakeetTranscriber()
        with mock.patch.object(ParakeetTranscriber, "is_available", return_value=False):
            with self.assertRaises(RuntimeError):
                transcriber.transcribe(Path("dummy.wav"))

    def test_parakeet_runner_cmd_does_not_change_availability(self):
        self.assertEqual(
            ParakeetTranscriber(runner_cmd=["python3"]).is_available(),
            ParakeetTranscriber().is_available(),
        )

    def test_model_allowlist_and_overwrite_guard(self):
        with self.assertRaises(ValueError):
            WhisperTranscriber(model_name="--evil-flag")
        with self.assertRaises(ValueError):
            WhisperTranscriber(model_name="attacker/rogue-repo")
        custom_w = WhisperTranscriber(model_name="org/custom-whisper", allow_custom_model=True)
        self.assertEqual(custom_w.model_name, "org/custom-whisper")

        with self.assertRaises(ValueError):
            ParakeetTranscriber(model_name="attacker/rogue-nemo")
        custom_p = ParakeetTranscriber(model_name="org/custom-nemo", allow_custom_model=True)
        self.assertEqual(custom_p.model_name, "org/custom-nemo")

    def test_parakeet_offline_sets_hf_hub_offline_and_supports_restore_from(self):
        import os
        import sys
        import types

        captured_env = []
        restore_calls = []

        class FakeModel:
            def transcribe(self, paths):
                return ["offline parakeet transcript"]

        class FakeASRModel:
            @staticmethod
            def from_pretrained(model_name):
                captured_env.append(os.environ.get("HF_HUB_OFFLINE"))
                return FakeModel()

            @staticmethod
            def restore_from(restore_path):
                captured_env.append(os.environ.get("HF_HUB_OFFLINE"))
                restore_calls.append(restore_path)
                return FakeModel()

        fake_nemo = types.ModuleType("nemo")
        fake_collections = types.ModuleType("nemo.collections")
        fake_asr = types.ModuleType("nemo.collections.asr")
        fake_asr.models = types.SimpleNamespace(ASRModel=FakeASRModel)
        fake_collections.asr = fake_asr
        fake_nemo.collections = fake_collections

        with tempfile.TemporaryDirectory() as tmp_dir:
            audio = Path(tmp_dir) / "sample.wav"
            audio.write_bytes(b"RIFF")
            nemo_file = Path(tmp_dir) / "local_model.nemo"
            nemo_file.write_bytes(b"NEMO")

            with mock.patch.dict(
                sys.modules,
                {
                    "nemo": fake_nemo,
                    "nemo.collections": fake_collections,
                    "nemo.collections.asr": fake_asr,
                },
            ), mock.patch.object(ParakeetTranscriber, "is_available", return_value=True):
                t1 = ParakeetTranscriber(offline=True)
                res1 = t1.transcribe(audio)
                self.assertEqual(res1.text, "offline parakeet transcript")
                self.assertEqual(captured_env[-1], "1")
                self.assertIsNone(os.environ.get("HF_HUB_OFFLINE"))

                t2 = ParakeetTranscriber(
                    model_name=str(nemo_file),
                    offline=True,
                    allow_custom_model=True,
                )
                res2 = t2.transcribe(audio)
                self.assertEqual(res2.text, "offline parakeet transcript")
                self.assertEqual(restore_calls, [str(nemo_file.resolve())])

        with tempfile.TemporaryDirectory() as tmp_dir:
            res = TranscriptionResult(
                audio_path="",
                filename="dup.wav",
                duration_seconds=1.0,
                language="en",
                text="hello",
                segments=[],
                model="mock-v1",
            )
            write_transcript_artifacts(res, Path(tmp_dir))
            with self.assertRaises(FileExistsError):
                write_transcript_artifacts(res, Path(tmp_dir), overwrite=False)
            write_transcript_artifacts(res, Path(tmp_dir), overwrite=True)


if __name__ == "__main__":
    unittest.main()
