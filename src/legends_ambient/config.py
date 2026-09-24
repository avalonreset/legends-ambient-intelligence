"""Configuration and environment defaults for Legends Ambient Intelligence."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

SUPPORTED_AUDIO_EXTENSIONS: Final[tuple[str, ...]] = (
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".ogg",
    ".webm",
    ".aac",
)


def get_default_archive_root() -> Path:
    """Return the default archive directory, honoring environment variables."""
    env_root = os.environ.get("LEGENDS_AMBIENT_ARCHIVE")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return (Path.home() / ".legends-ambient" / "archive").resolve()


def get_default_device_label() -> str:
    """Return the default USB hardware volume label to probe."""
    return os.environ.get("LEGENDS_AMBIENT_DEVICE_LABEL", "KT5000")


def get_default_model_name() -> str:
    """Return the default ASR model name or identifier."""
    return os.environ.get("LEGENDS_AMBIENT_MODEL", "base")
