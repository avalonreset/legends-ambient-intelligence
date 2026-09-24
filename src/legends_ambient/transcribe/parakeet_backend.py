"""NVIDIA NeMo Parakeet ASR backend for high-throughput GPU transcription."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .engine import Transcriber, TranscriptionResult, TranscriptSegment


class ParakeetTranscriber(Transcriber):
    """ASR backend targeting NVIDIA NeMo Parakeet models."""

    def __init__(
        self,
        model_name: str = "nvidia/parakeet-tdt-0.6b-v3",
        runner_cmd: Optional[list[str]] = None,
    ) -> None:
        self.model_name = model_name
        # Reserved for future use. Transcription currently requires
        # NVIDIA NeMo with a CUDA-capable GPU.
        self.runner_cmd = runner_cmd

    def is_available(self) -> bool:
        """Check if NVIDIA NeMo with CUDA is available."""
        try:
            import nemo.collections.asr as nemo_asr  # noqa: F401
            import torch  # noqa: F401
            return torch.cuda.is_available()
        except ImportError:
            return False

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        if not self.is_available():
            raise RuntimeError(
                "Parakeet ASR requires NVIDIA NeMo and a CUDA-capable GPU."
            )

        try:
            import nemo.collections.asr as nemo_asr  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Parakeet ASR requires NVIDIA NeMo and a CUDA-capable GPU."
            ) from exc

        model = nemo_asr.models.ASRModel.from_pretrained(model_name=self.model_name)
        transcriptions = model.transcribe([str(audio_path)])
        text = transcriptions[0] if transcriptions else ""

        # Construct basic segment
        seg = TranscriptSegment(
            id=0,
            start=0.0,
            end=0.0,
            text=text,
        )

        return TranscriptionResult(
            audio_path=str(audio_path.resolve()),
            filename=audio_path.name,
            duration_seconds=0.0,
            language="en",
            text=text,
            segments=[seg],
            model=f"nemo-{self.model_name}",
        )
