"""NVIDIA NeMo Parakeet ASR backend for high-throughput GPU transcription."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
from typing import Optional

from .engine import Transcriber, TranscriptionResult, TranscriptSegment, WordTiming


class ParakeetTranscriber:
    """ASR backend targeting NVIDIA NeMo Parakeet models."""

    def __init__(
        self,
        model_name: str = "nvidia/parakeet-tdt-0.6b-v3",
        runner_cmd: Optional[list[str]] = None,
    ) -> None:
        self.model_name = model_name
        self.runner_cmd = runner_cmd

    def is_available(self) -> bool:
        """Check if NeMo or a designated runner command is available."""
        if self.runner_cmd:
            return shutil.which(self.runner_cmd[0]) is not None
        try:
            import nemo.collections.asr as nemo_asr  # noqa: F401
            import torch  # noqa: F401
            return torch.cuda.is_available()
        except ImportError:
            return False

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        if not self.is_available():
            raise RuntimeError(
                "Parakeet ASR requires NVIDIA NeMo and a CUDA-capable GPU, "
                "or a configured custom runner command."
            )

        import nemo.collections.asr as nemo_asr  # type: ignore

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
