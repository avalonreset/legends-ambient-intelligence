"""Removable hardware audio device source (USB voice recorders, wearable capture)."""

from __future__ import annotations

import ctypes
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


def _win32_find_mounted_device(label: str) -> Optional[Path]:
    """Find mounted volume root matching label using Win32 kernel32 APIs (zero PowerShell/WMI)."""
    target = label.strip().lower()
    if not target:
        return None
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        bitmask = int(kernel32.GetLogicalDrives())
        matches: list[str] = []
        for idx in range(26):
            if not (bitmask & (1 << idx)):
                continue
            letter = chr(ord("A") + idx)
            root = f"{letter}:\\"
            vol_buf = ctypes.create_unicode_buffer(261)
            ok = kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(root),
                vol_buf,
                len(vol_buf),
                None,
                None,
                None,
                None,
                0,
            )
            if ok and vol_buf.value.strip().lower() == target:
                matches.append(letter)
        if len(matches) == 1:
            return Path(f"{matches[0]}:\\")
    except Exception:
        return None
    return None


def _win32_eject_volume(path: Path) -> bool:
    """Safely lock, dismount, and eject a removable volume via Win32 DeviceIoControl."""
    drive = str(path)[:2]
    if len(drive) != 2 or not drive[0].isalpha() or drive[1] != ":":
        return False
    device_path = f"\\\\.\\{drive}"
    generic_read = 0x80000000
    generic_write = 0x40000000
    file_share_rw = 0x00000001 | 0x00000002
    open_existing = 3
    fsctl_lock_volume = 0x00090018
    fsctl_dismount_volume = 0x00090020
    ioctl_storage_media_removal = 0x002D4804
    ioctl_storage_eject_media = 0x002D4808

    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.CreateFileW.restype = ctypes.c_void_p
        handle = kernel32.CreateFileW(
            ctypes.c_wchar_p(device_path),
            generic_read | generic_write,
            file_share_rw,
            None,
            open_existing,
            0,
            None,
        )
        invalid = ctypes.c_void_p(-1).value
        if handle is None or handle == invalid:
            handle = kernel32.CreateFileW(
                ctypes.c_wchar_p(device_path),
                generic_read,
                file_share_rw,
                None,
                open_existing,
                0,
                None,
            )
        if handle is None or handle == invalid:
            return False

        try:
            bytes_returned = ctypes.c_ulong(0)
            kernel32.DeviceIoControl(
                ctypes.c_void_p(handle),
                fsctl_lock_volume,
                None,
                0,
                None,
                0,
                ctypes.byref(bytes_returned),
                None,
            )
            dismount_ok = bool(
                kernel32.DeviceIoControl(
                    ctypes.c_void_p(handle),
                    fsctl_dismount_volume,
                    None,
                    0,
                    None,
                    0,
                    ctypes.byref(bytes_returned),
                    None,
                )
            )
            prevent = ctypes.c_byte(0)
            kernel32.DeviceIoControl(
                ctypes.c_void_p(handle),
                ioctl_storage_media_removal,
                ctypes.byref(prevent),
                ctypes.sizeof(prevent),
                None,
                0,
                ctypes.byref(bytes_returned),
                None,
            )
            eject_ok = bool(
                kernel32.DeviceIoControl(
                    ctypes.c_void_p(handle),
                    ioctl_storage_eject_media,
                    None,
                    0,
                    None,
                    0,
                    ctypes.byref(bytes_returned),
                    None,
                )
            )
            return dismount_ok or eject_ok
        finally:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
    except Exception:
        return False


def find_mounted_device(label: str = "KT5000") -> Optional[Path]:
    """Find the mount root of a USB volume matching the given label."""
    if not label or not label.strip():
        return None
    if sys.platform == "win32":
        return _win32_find_mounted_device(label)
    elif sys.platform == "darwin":
        vol = Path(f"/Volumes/{label}")
        if vol.is_dir():
            return vol
    elif sys.platform.startswith("linux"):
        for base in (Path("/media"), Path("/mnt")):
            if not base.is_dir():
                continue
            direct = base / label
            if direct.is_dir():
                return direct
            try:
                children = [c for c in base.iterdir() if c.is_dir()]
            except OSError:
                continue
            for child in children:
                candidate = child / label
                if candidate.is_dir():
                    return candidate

    return None


def eject_volume(path: Path) -> bool:
    """Safely eject a mounted removable volume across operating systems."""
    if sys.platform == "win32":
        return _win32_eject_volume(path)
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
