"""ASR interfaces and transcript data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Sequence


@dataclass(frozen=True)
class WordTiming:
    """Word-level timing information."""

    word: str
    start: float
    end: float
    confidence: float = 1.0


@dataclass(frozen=True)
class TranscriptSegment:
    """Individual utterance or chunk in a transcript."""

    id: int
    start: float
    end: float
    text: str
    words: list[WordTiming] = field(default_factory=list)


@dataclass
class TranscriptionResult:
    """Complete result of transcribing one audio file."""

    audio_path: str
    filename: str
    duration_seconds: float
    language: str
    text: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    model: str = "unknown"

    @property
    def total_words(self) -> int:
        return sum(len(s.words) for s in self.segments) or len(self.text.split())


class Transcriber(Protocol):
    """Protocol for pluggable ASR backends."""

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        """Transcribe an audio file and return a TranscriptionResult."""
        ...
