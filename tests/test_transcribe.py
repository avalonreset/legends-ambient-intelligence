"""Unit tests for transcript engine, mock backend, and sidecar artifact writers."""

import json
from pathlib import Path
import tempfile
import unittest

from legends_ambient.transcribe.mock_backend import MockTranscriber
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


if __name__ == "__main__":
    unittest.main()
