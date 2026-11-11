"""NVIDIA NeMo Parakeet ASR backend for high-throughput GPU transcription."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .engine import Transcriber, TranscriptionResult, TranscriptSegment
from ..ingest.sources import is_symlink_or_reparse

ALLOWED_PARAKEET_MODELS = {
    "nvidia/parakeet-tdt-0.6b-v2",
    "nvidia/parakeet-tdt-0.6b-v3",
    "nvidia/parakeet-tdt-1.1b",
    "nvidia/parakeet-ctc-0.6b",
    "nvidia/parakeet-ctc-1.1b",
    "nvidia/parakeet-rnnt-0.6b",
    "nvidia/parakeet-rnnt-1.1b",
}


class ParakeetTranscriber(Transcriber):
    """ASR backend targeting NVIDIA NeMo Parakeet models."""

    def __init__(
        self,
        model_name: str = "nvidia/parakeet-tdt-0.6b-v3",
        runner_cmd: Optional[list[str]] = None,
        *,
        offline: bool = False,
        allow_custom_model: bool = False,
    ) -> None:
        normalized = "nvidia/parakeet-tdt-0.6b-v3" if model_name == "base" else model_name
        if not allow_custom_model and normalized not in ALLOWED_PARAKEET_MODELS:
            raise ValueError(
                f"Untrusted Parakeet model {normalized!r}; pass --allow-custom-model to override."
            )
        self.model_name = normalized
        # Reserved for future use. Transcription currently requires
        # NVIDIA NeMo with a CUDA-capable GPU.
        self.runner_cmd = runner_cmd
        self.offline = offline
        self.allow_custom_model = allow_custom_model

    def is_available(self) -> bool:
        """Check if NVIDIA NeMo with CUDA is available."""
        try:
            import nemo.collections.asr as nemo_asr  # noqa: F401
            import torch  # noqa: F401
            return torch.cuda.is_available()
        except ImportError:
            return False

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        if is_symlink_or_reparse(audio_path):
            raise ValueError(f"Refusing symlinked audio input: {audio_path}")
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

        resolved_audio = audio_path.resolve()
        candidate_model_path = Path(self.model_name)
        prev_hf_offline = os.environ.get("HF_HUB_OFFLINE")
        if self.offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
        try:
            if candidate_model_path.suffix.lower() == ".nemo" or candidate_model_path.exists():
                if is_symlink_or_reparse(candidate_model_path):
                    raise ValueError(f"Refusing symlinked NeMo model path: {candidate_model_path}")
                if not candidate_model_path.is_file():
                    raise FileNotFoundError(f"Local NeMo model file not found: {candidate_model_path}")
                model = nemo_asr.models.ASRModel.restore_from(
                    restore_path=str(candidate_model_path.resolve())
                )
            else:
                model = nemo_asr.models.ASRModel.from_pretrained(model_name=self.model_name)
        finally:
            if self.offline:
                if prev_hf_offline is None:
                    os.environ.pop("HF_HUB_OFFLINE", None)
                else:
                    os.environ["HF_HUB_OFFLINE"] = prev_hf_offline

        transcriptions = model.transcribe([str(resolved_audio)])
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
