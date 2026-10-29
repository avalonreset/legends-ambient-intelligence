"""Environment and diagnostic health checks for Legends Ambient Intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import sys
from typing import Optional

from .config import get_default_archive_root, get_default_device_label
from .ingest.device_source import find_mounted_device


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str


class Doctor:
    """Performs offline system and environment readiness checks."""

    def __init__(self, archive_root: Optional[Path] = None, device_label: Optional[str] = None) -> None:
        self.archive_root = archive_root or get_default_archive_root()
        self.device_label = device_label or get_default_device_label()

    def run_all(self) -> list[CheckResult]:
        results: list[CheckResult] = []

        # 1. Python version
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        if sys.version_info >= (3, 11):
            results.append(CheckResult("python", "OK", f"Python {py_ver} (supported)"))
        else:
            results.append(CheckResult("python", "FAIL", f"Python {py_ver} (requires 3.11+)"))

        # 2. Archive root directory
        try:
            self.archive_root.mkdir(parents=True, exist_ok=True)
            results.append(CheckResult("archive_dir", "OK", f"Writable: {self.archive_root}"))
        except Exception as e:
            results.append(CheckResult("archive_dir", "FAIL", f"Cannot write to {self.archive_root}: {e}"))

        # 3. Audio tools: ffmpeg and ffprobe
        ffmpeg_bin = shutil.which("ffmpeg")
        ffprobe_bin = shutil.which("ffprobe")
        if ffmpeg_bin and ffprobe_bin:
            results.append(CheckResult("audio_tools", "OK", f"Found ffmpeg and ffprobe ({ffmpeg_bin})"))
        else:
            missing = []
            if not ffmpeg_bin:
                missing.append("ffmpeg")
            if not ffprobe_bin:
                missing.append("ffprobe")
            results.append(CheckResult("audio_tools", "WARN", f"Missing {', '.join(missing)} on PATH"))

        # 4. ASR engines
        whisper_ready = False
        try:
            import faster_whisper  # noqa: F401
            whisper_ready = True
            results.append(CheckResult("whisper_asr", "OK", "faster-whisper is installed"))
        except ImportError:
            if shutil.which("whisper"):
                whisper_ready = True
                results.append(CheckResult("whisper_asr", "OK", "whisper CLI found on PATH"))
            else:
                results.append(CheckResult("whisper_asr", "INFO", "faster-whisper not installed (optional: pip install faster-whisper)"))

        # 5. NeMo / Parakeet
        try:
            import nemo  # noqa: F401
            import torch  # noqa: F401
            cuda = torch.cuda.is_available()
            results.append(CheckResult("parakeet_asr", "OK" if cuda else "WARN", f"NeMo installed (CUDA available: {cuda})"))
        except ImportError:
            results.append(CheckResult("parakeet_asr", "INFO", "NVIDIA NeMo not installed (optional: used for local Parakeet GPU runs)"))

        # 6. Removable hardware device check
        device_mount = find_mounted_device(self.device_label)
        if device_mount:
            results.append(CheckResult("hardware_device", "OK", f"Volume '{self.device_label}' mounted at {device_mount}"))
        else:
            results.append(CheckResult("hardware_device", "INFO", f"Volume '{self.device_label}' not currently mounted (normal if using mic/local folder)"))

        return results
