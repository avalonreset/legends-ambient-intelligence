"""Deterministic mock ASR backend for offline verification and unit testing."""

from __future__ import annotations

from pathlib import Path
from .engine import Transcriber, TranscriptionResult, TranscriptSegment, WordTiming


class MockTranscriber(Transcriber):
    """Mock ASR backend producing deterministic transcript artifacts."""

    def __init__(self, sample_text: str = "This is an ambient voice sketchpad recording testing prompt continuation.") -> None:
        self.sample_text = sample_text

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        words = self.sample_text.split()
        word_timings = [
            WordTiming(word=w, start=i * 0.5, end=(i + 1) * 0.5)
            for i, w in enumerate(words)
        ]
        duration = len(words) * 0.5 + 0.5
        segment = TranscriptSegment(
            id=0,
            start=0.0,
            end=duration,
            text=self.sample_text,
            words=word_timings,
        )

        return TranscriptionResult(
            audio_path=str(audio_path.resolve()),
            filename=audio_path.name,
            duration_seconds=duration,
            language="en",
            text=self.sample_text,
            segments=[segment],
            model="mock-v1",
        )
