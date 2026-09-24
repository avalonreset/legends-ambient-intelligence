"""Transcription backends, engine protocols, and artifact writers."""

from .engine import Transcriber, TranscriptionResult, TranscriptSegment, WordTiming
from .mock_backend import MockTranscriber
from .whisper_backend import WhisperTranscriber
from .parakeet_backend import ParakeetTranscriber
from .writers import write_transcript_artifacts, write_transcript_index

__all__ = [
    "Transcriber",
    "TranscriptionResult",
    "TranscriptSegment",
    "WordTiming",
    "MockTranscriber",
    "WhisperTranscriber",
    "ParakeetTranscriber",
    "write_transcript_artifacts",
    "write_transcript_index",
]
