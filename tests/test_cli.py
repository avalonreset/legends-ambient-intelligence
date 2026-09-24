"""Unit tests for CLI commands using offline temp dirs and the mock backend."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from legends_ambient.cli import main


def _run(argv):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


class TestCliIngest(unittest.TestCase):
    def test_ingest_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = _run([
                "--archive-root", tmp, "ingest",
                "--source", str(Path(tmp) / "missing"),
            ])
            self.assertEqual(code, 1)
            self.assertIn("does not exist", err)

    def test_ingest_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            archive = Path(tmp) / "archive"
            code, out, _ = _run([
                "--archive-root", str(archive), "ingest",
                "--source", str(src), "--slug", "empty",
            ])
            self.assertEqual(code, 0)
            receipt = json.loads(out)
            self.assertEqual(receipt["status"], "no-new-recordings")

    def test_ingest_what_if_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "a.wav").write_bytes(b"RIFF")
            archive = Path(tmp) / "archive"
            code, out, _ = _run([
                "--archive-root", str(archive), "ingest",
                "--source", str(src), "--slug", "preview", "--what-if",
            ])
            self.assertEqual(code, 0)
            receipt = json.loads(out)
            self.assertEqual(receipt["status"], "dry-run")
            self.assertEqual(list(archive.glob("**/manifest.json")), [])

    def test_ingest_archives_new_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "a.wav").write_bytes(b"RIFF")
            archive = Path(tmp) / "archive"
            code, out, _ = _run([
                "--archive-root", str(archive), "ingest",
                "--source", str(src), "--slug", "first",
            ])
            self.assertEqual(code, 0)
            receipt = json.loads(out)
            self.assertEqual(receipt["status"], "archived")
            self.assertEqual(receipt["new_archived"], 1)
            self.assertTrue((src / "a.wav").is_file())

    def test_ingest_missing_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = _run([
                "--archive-root", tmp, "ingest",
                "--device", "--device-label", "NO_SUCH_VOLUME_XYZ_123",
            ])
            self.assertEqual(code, 1)
            self.assertIn("No mounted USB device", err)


class TestCliTranscribe(unittest.TestCase):
    def _ingest_one(self, tmp):
        src = Path(tmp) / "src"
        src.mkdir(exist_ok=True)
        (src / "a.wav").write_bytes(b"RIFF")
        archive = Path(tmp) / "archive"
        code, _, _ = _run([
            "--archive-root", str(archive), "ingest",
            "--source", str(src), "--slug", "pkg",
        ])
        self.assertEqual(code, 0)
        manifests = list(archive.glob("**/manifest.json"))
        self.assertEqual(len(manifests), 1)
        return manifests[0].parent

    def test_transcribe_missing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = _run([
                "--archive-root", tmp, "transcribe", str(Path(tmp) / "missing"),
            ])
            self.assertEqual(code, 1)
            self.assertIn("does not exist", err)

    def test_transcribe_no_audio_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            code, out, _ = _run([
                "--archive-root", tmp, "transcribe", str(empty), "--backend", "mock",
            ])
            self.assertEqual(code, 0)
            self.assertIn("No audio files found", out)

    def test_transcribe_package_with_mock(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = self._ingest_one(tmp)
            code, _, _ = _run([
                "--archive-root", str(Path(tmp) / "archive"), "transcribe",
                str(pkg), "--backend", "mock",
            ])
            self.assertEqual(code, 0)
            transcripts = pkg / "transcripts"
            for name in ("a.txt", "a.json", "a.srt", "a.vtt", "a.words.json", "index.md"):
                self.assertTrue((transcripts / name).is_file(), name)

    def test_transcribe_single_file_with_mock(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "solo.wav"
            target.write_bytes(b"RIFF")
            code, _, _ = _run([
                "--archive-root", tmp, "transcribe", str(target), "--backend", "mock",
            ])
            self.assertEqual(code, 0)
            self.assertTrue((Path(tmp) / "transcripts" / "solo.txt").is_file())

    def test_transcribe_unavailable_backend_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = self._ingest_one(tmp)
            with mock.patch(
                "legends_ambient.cli.ParakeetTranscriber.is_available", return_value=False
            ):
                code, _, err = _run([
                    "--archive-root", str(Path(tmp) / "archive"), "transcribe",
                    str(pkg), "--backend", "parakeet",
                ])
            self.assertEqual(code, 1)
            self.assertIn("not available", err)

    def test_transcribe_backend_error_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = self._ingest_one(tmp)
            with mock.patch(
                "legends_ambient.cli.MockTranscriber.transcribe",
                side_effect=RuntimeError("boom"),
            ):
                code, _, err = _run([
                    "--archive-root", str(Path(tmp) / "archive"), "transcribe",
                    str(pkg), "--backend", "mock",
                ])
            self.assertEqual(code, 1)
            self.assertIn("Transcription failed", err)


class TestCliRecover(unittest.TestCase):
    def test_recover_empty_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            code, out, _ = _run([
                "--archive-root", tmp, "recover", "--source", str(src),
            ])
            self.assertEqual(code, 1)
            self.assertIn("No audio recordings found", out)

    def test_recover_missing_source_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = _run([
                "--archive-root", tmp, "recover",
                "--source", str(Path(tmp) / "missing"),
            ])
            self.assertEqual(code, 1)
            self.assertIn("No audio recordings found", out)

    def test_recover_with_continuation(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "a.wav").write_bytes(b"RIFF1")
            (src / "b.wav").write_bytes(b"RIFF2")
            transcript = Path(tmp) / "latest.txt"
            transcript.write_text("and then we kept talking.", encoding="utf-8")
            code, out, _ = _run([
                "--archive-root", tmp, "recover",
                "--source", str(src), "--transcript", str(transcript),
            ])
            self.assertEqual(code, 0)
            plan = json.loads(out)
            self.assertEqual(plan["status"], "include-predecessor-tail")
            self.assertTrue(plan["starts_mid_thought"])

    def test_recover_missing_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = _run([
                "--archive-root", tmp, "recover",
                "--device", "--device-label", "NO_SUCH_VOLUME_XYZ_123",
            ])
            self.assertEqual(code, 1)
            self.assertIn("not found", err)


class TestCliDistill(unittest.TestCase):
    def test_distill_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = _run([
                "--archive-root", tmp, "distill", str(Path(tmp) / "missing.txt"),
            ])
            self.assertEqual(code, 1)
            self.assertIn("not found", err)

    def test_distill_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            code, _, err = _run(["--archive-root", tmp, "distill", str(bad)])
            self.assertEqual(code, 1)
            self.assertIn("Cannot parse", err)

    def test_distill_json_must_be_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "list.json"
            target.write_text("[1, 2]", encoding="utf-8")
            code, _, err = _run(["--archive-root", tmp, "distill", str(target)])
            self.assertEqual(code, 1)
            self.assertIn("must be an object", err)

    def test_distill_bad_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "t.json"
            target.write_text(json.dumps({"text": "hi", "duration_seconds": "abc"}), encoding="utf-8")
            code, _, err = _run(["--archive-root", tmp, "distill", str(target)])
            self.assertEqual(code, 1)
            self.assertIn("Invalid duration_seconds", err)

    def test_distill_text_to_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "note.txt"
            target.write_text("We decided to ship today. You should update the docs.", encoding="utf-8")
            code, out, _ = _run(["--archive-root", tmp, "distill", str(target)])
            self.assertEqual(code, 0)
            self.assertIn("Ambient Note", out)

    def test_distill_json_to_vault(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "t.json"
            target.write_text(
                json.dumps({
                    "text": "We decided to ship today quickly.",
                    "duration_seconds": 5.0,
                    "model": "mock-v1",
                    "language": "en",
                }),
                encoding="utf-8",
            )
            vault = Path(tmp) / "vault"
            code, out, _ = _run([
                "--archive-root", tmp, "distill", str(target),
                "--vault", str(vault), "--slug", "note1",
            ])
            self.assertEqual(code, 0)
            self.assertTrue((vault / "note1.md").is_file())
            self.assertIn("Exported", out)

    def test_distill_vault_is_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "note.txt"
            target.write_text("hello world today", encoding="utf-8")
            blocker = Path(tmp) / "blocker.txt"
            blocker.write_text("x", encoding="utf-8")
            code, _, err = _run([
                "--archive-root", tmp, "distill", str(target), "--vault", str(blocker),
            ])
            self.assertEqual(code, 1)
            self.assertIn("Cannot write", err)


class TestCliDoctorStatus(unittest.TestCase):
    def test_doctor_runs_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = _run(["--archive-root", tmp, "doctor"])
            self.assertEqual(code, 0)
            self.assertIn("Doctor", out)

    def test_doctor_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = _run(["--archive-root", tmp, "doctor", "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(out)
            names = [r["name"] for r in payload]
            for expected in ("python", "archive_dir", "audio_tools", "whisper_asr", "parakeet_asr", "hardware_device"):
                self.assertIn(expected, names)

    def test_status_runs_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = _run(["--archive-root", tmp, "status"])
            self.assertEqual(code, 0)
            self.assertIn("Status", out)


if __name__ == "__main__":
    unittest.main()
