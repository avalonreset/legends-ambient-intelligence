"""Data structures and discovery helpers for audio sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from typing import Optional

from ..config import SUPPORTED_AUDIO_EXTENSIONS


@dataclass(frozen=True)
class AudioFile:
    """Represents a discovered audio recording."""

    path: Path
    filename: str
    size_bytes: int
    last_modified_iso: str
    sha256: str
    recording_start_iso: Optional[str] = None

    @classmethod
    def from_path(cls, path: Path) -> AudioFile:
        """Inspect a file path on disk and compute its hash and metadata."""
        resolved = path.resolve()
        stat = resolved.stat()
        sha256 = compute_file_sha256(resolved)
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        rec_start = parse_recording_timestamp(resolved.name)
        rec_start_iso = rec_start.isoformat() if rec_start else None

        return cls(
            path=resolved,
            filename=resolved.name,
            size_bytes=stat.st_size,
            last_modified_iso=mtime,
            sha256=sha256,
            recording_start_iso=rec_start_iso,
        )


def compute_file_sha256(path: Path) -> str:
    """Compute the SHA-256 hash of a file in 64KB chunks."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().upper()


def parse_recording_timestamp(filename: str) -> Optional[datetime]:
    """Parse start timestamp from common hardware recording formats.

    Supports:
    - KT5000 / Olympus style: VRyy_mm_dd-hh_mm_ss.WAV or Ryy_mm_dd-hh_mm_ss.WAV
    - Dash/underscore style: 2026-09-24_10-15-30.wav or 20260924_101530.wav
    """
    # Hardware style: VRmm_dd_yy-hh_mm_ss.WAV, Vmm_dd_yy-hh_mm_ss.WAV, Rmm_dd_yy-hh_mm_ss.WAV
    m = re.match(
        r"^(?:VR|[VR])(\d{2})_(\d{2})_(\d{2})-(\d{2})_(\d{2})_(\d{2})\.[a-zA-Z0-9]+$",
        filename,
    )
    if m:
        p1, p2, p3, hour, minute, second = (int(x) for x in m.groups())
        # If p1 > 12, it must be YY_MM_DD; otherwise default to KT5000 standard MM_DD_YY
        if p1 > 12:
            year, month, day = 2000 + p1, p2, p3
        else:
            month, day, year = p1, p2, 2000 + p3
        try:
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            return None

    # Full year style: 20260924_101530 or 2026-09-24_10-15-30
    m2 = re.match(
        r"^(\d{4})[-_]?(\d{2})[-_]?(\d{2})[-_T](\d{2})[-_]?(\d{2})[-_]?(\d{2})",
        filename,
    )
    if m2:
        year, month, day, hour, minute, second = (int(x) for x in m2.groups())
        try:
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            return None

    return None


def scan_audio_directory(
    directory: Path,
    recursive: bool = False,
) -> list[Path]:
    """Scan a directory for supported audio recordings."""
    if not directory.is_dir():
        return []

    results: list[Path] = []
    pattern = "**/*" if recursive else "*"
    for item in directory.glob(pattern):
        if item.is_file() and item.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS:
            results.append(item.resolve())

    return sorted(results, key=lambda p: p.name)
