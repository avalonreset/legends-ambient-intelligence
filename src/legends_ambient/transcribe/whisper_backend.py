"""Portable local Whisper ASR backend (supporting faster-whisper and CLI)."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from typing import Optional

from .engine import Transcriber, TranscriptionResult, TranscriptSegment, WordTiming


class WhisperTranscriber:
    """ASR backend using faster-whisper or local whisper CLI."""

    def __init__(
        self,
        model_name: str = "base",
        device: str = "auto",
        compute_type: str = "default",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _get_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel  # type: ignore

            self._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )
            return self._model
        except ImportError:
            return None

    def is_available(self) -> bool:
        """Check if faster-whisper or whisper CLI is installed."""
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return shutil.which("whisper") is not None

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        model = self._get_model()
        if model is not None:
            return self._transcribe_faster_whisper(model, audio_path)

        if shutil.which("whisper") is not None:
            return self._transcribe_cli(audio_path)

        raise RuntimeError(
            "Whisper backend requires 'faster-whisper' (pip install faster-whisper) "
            "or the 'whisper' command line tool on PATH."
        )

    def _transcribe_faster_whisper(self, model, audio_path: Path) -> TranscriptionResult:
        segments_raw, info = model.transcribe(
            str(audio_path),
            word_timestamps=True,
            vad_filter=True,
        )

        segments: list[TranscriptSegment] = []
        full_text_parts: list[str] = []

        for idx, s in enumerate(segments_raw):
            full_text_parts.append(s.text.strip())
            words = [
                WordTiming(word=w.word.strip(), start=w.start, end=w.end, confidence=getattr(w, "probability", 1.0))
                for w in (s.words or [])
            ]
            segments.append(
                TranscriptSegment(
                    id=idx,
                    start=s.start,
                    end=s.end,
                    text=s.text.strip(),
                    words=words,
                )
            )

        return TranscriptionResult(
            audio_path=str(audio_path.resolve()),
            filename=audio_path.name,
            duration_seconds=getattr(info, "duration", 0.0),
            language=getattr(info, "language", "en"),
            text=" ".join(full_text_parts),
            segments=segments,
            model=f"faster-whisper-{self.model_name}",
        )

    def _transcribe_cli(self, audio_path: Path) -> TranscriptionResult:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            cmd = [
                "whisper",
                str(audio_path),
                "--model",
                self.model_name,
                "--output_dir",
                tmp_dir,
                "--output_format",
                "json",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"whisper CLI execution failed: {res.stderr}")

            json_out = Path(tmp_dir) / f"{audio_path.stem}.json"
            if not json_out.is_file():
                raise RuntimeError(f"whisper CLI output not found: {json_out}")

            data = json.loads(json_out.read_text(encoding="utf-8"))
            segments: list[TranscriptSegment] = []
            for s in data.get("segments", []):
                words = [
                    WordTiming(word=w["word"].strip(), start=w["start"], end=w["end"])
                    for w in s.get("words", [])
                ]
                segments.append(
                    TranscriptSegment(
                        id=s.get("id", len(segments)),
                        start=s.get("start", 0.0),
                        end=s.get("end", 0.0),
                        text=s.get("text", "").strip(),
                        words=words,
                    )
                )

            return TranscriptionResult(
                audio_path=str(audio_path.resolve()),
                filename=audio_path.name,
                duration_seconds=float(data.get("duration", 0.0)),
                language=data.get("language", "en"),
                text=data.get("text", "").strip(),
                segments=segments,
                model=f"whisper-cli-{self.model_name}",
            )
