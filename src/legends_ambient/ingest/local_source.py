"""Local filesystem audio source (computer mic recordings, local drops, voice memos)."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .sources import AudioFile, scan_audio_directory


class LocalDirectorySource:
    """Manages audio file discovery from a local directory or mic capture folder."""

    def __init__(self, directory: Path, recursive: bool = False) -> None:
        self.directory = directory.resolve()
        self.recursive = recursive

    def exists(self) -> bool:
        """Check if the source directory exists."""
        return self.directory.is_dir()

    def discover(self) -> list[AudioFile]:
        """Scan directory and return AudioFile descriptors."""
        if not self.exists():
            return []
        paths = scan_audio_directory(self.directory, recursive=self.recursive)
        return [AudioFile.from_path(p) for p in paths]
