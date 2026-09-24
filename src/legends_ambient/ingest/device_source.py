"""Removable hardware audio device source (USB voice recorders, wearable capture)."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Optional

from .sources import AudioFile, scan_audio_directory


class DeviceSource:
    """Manages audio file discovery and safe handling on removable hardware recorders."""

    def __init__(self, root_path: Path, volume_label: str = "KT5000") -> None:
        self.root_path = root_path.resolve()
        self.volume_label = volume_label

    def discover(self, subfolder: Optional[str] = "RECORDED") -> list[AudioFile]:
        """Scan device folder for recordings."""
        target = self.root_path
        if subfolder:
            candidate = self.root_path / subfolder
            if candidate.is_dir():
                target = candidate

        paths = scan_audio_directory(target, recursive=True)
        return [AudioFile.from_path(p) for p in paths]

    def safe_eject(self) -> bool:
        """Safely eject the removable volume."""
        return eject_volume(self.root_path)


def find_mounted_device(label: str = "KT5000") -> Optional[Path]:
    """Find the mount root of a USB volume matching the given label."""
    if sys.platform == "win32":
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            f"@((Get-Volume | Where-Object {{ $_.FileSystemLabel -ieq '{label}' -and $_.DriveLetter }}).DriveLetter) -join ','",
        ]
        try:
            out = subprocess.check_output(cmd, text=True, timeout=10).strip()
            letters = [x.strip() for x in out.split(",") if x.strip()]
            if len(letters) == 1:
                return Path(f"{letters[0]}:\\")
        except Exception:
            return None
    elif sys.platform == "darwin":
        vol = Path(f"/Volumes/{label}")
        if vol.is_dir():
            return vol
    elif sys.platform.startswith("linux"):
        for base in (Path("/media"), Path("/mnt")):
            if base.is_dir():
                matches = list(base.glob(f"**/{label}"))
                if matches and matches[0].is_dir():
                    return matches[0]

    return None


def eject_volume(path: Path) -> bool:
    """Safely eject a mounted removable volume across operating systems."""
    if sys.platform == "win32":
        drive = str(path)[:2]
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            f"$drive = '{drive}'; "
            "$vol = Get-WmiObject -Class Win32_Volume -Filter \"DriveLetter='$drive'\"; "
            "if ($vol) { $vol.Dismount($false, $false) | Out-Null; $true } else { $false }",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return res.returncode == 0
        except Exception:
            return False
    elif sys.platform == "darwin":
        try:
            res = subprocess.run(["diskutil", "eject", str(path)], capture_output=True, timeout=15)
            return res.returncode == 0
        except Exception:
            return False
    elif sys.platform.startswith("linux"):
        try:
            res = subprocess.run(["umount", str(path)], capture_output=True, timeout=15)
            return res.returncode == 0
        except Exception:
            return False

    return False
