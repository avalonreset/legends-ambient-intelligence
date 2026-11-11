"""Removable hardware audio device source (USB voice recorders, wearable capture)."""

from __future__ import annotations

import ctypes
from pathlib import Path
import re
import subprocess
import sys
from typing import Optional

from .sources import AudioFile, is_symlink_or_reparse, scan_audio_directory

DRIVE_REMOVABLE = 2
DEVICE_LABEL_RE = re.compile(r"^[A-Za-z0-9 _.-]{1,64}$")


def validate_device_label(label: str) -> str:
    """Validate volume label against path traversal and separator characters."""
    if not label:
        raise ValueError("Device volume label must not be empty.")
    cleaned = label.strip()
    if (
        not cleaned
        or ".." in cleaned
        or "/" in cleaned
        or "\\" in cleaned
        or ":" in cleaned
        or not DEVICE_LABEL_RE.fullmatch(cleaned)
    ):
        raise ValueError(f"Unsafe device volume label: {label!r}")
    return cleaned


def _configure_kernel32(kernel32: object) -> None:
    """Declare explicit ctypes signatures on Win32 kernel32 volume functions."""
    try:
        kernel32.GetLogicalDrives.argtypes = []  # type: ignore[attr-defined]
        kernel32.GetLogicalDrives.restype = ctypes.c_ulong  # type: ignore[attr-defined]
        kernel32.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]  # type: ignore[attr-defined]
        kernel32.GetDriveTypeW.restype = ctypes.c_uint  # type: ignore[attr-defined]
        kernel32.GetVolumeInformationW.argtypes = [  # type: ignore[attr-defined]
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_ulong,
        ]
        kernel32.GetVolumeInformationW.restype = ctypes.c_int  # type: ignore[attr-defined]
        kernel32.CreateFileW.argtypes = [  # type: ignore[attr-defined]
            ctypes.c_wchar_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_void_p,
        ]
        kernel32.CreateFileW.restype = ctypes.c_void_p  # type: ignore[attr-defined]
        kernel32.DeviceIoControl.argtypes = [  # type: ignore[attr-defined]
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.c_void_p,
        ]
        kernel32.DeviceIoControl.restype = ctypes.c_int  # type: ignore[attr-defined]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]  # type: ignore[attr-defined]
        kernel32.CloseHandle.restype = ctypes.c_int  # type: ignore[attr-defined]
    except Exception:
        pass


class DeviceSource:
    """Manages audio file discovery and safe handling on removable hardware recorders."""

    def __init__(self, root_path: Path, volume_label: str = "KT5000") -> None:
        self._raw_root = root_path
        self.root_path = root_path if is_symlink_or_reparse(root_path) else root_path.resolve()
        self.volume_label = volume_label

    def discover(self, subfolder: Optional[str] = "RECORDED") -> list[AudioFile]:
        """Scan device folder for recordings."""
        if is_symlink_or_reparse(self._raw_root) or is_symlink_or_reparse(self.root_path):
            return []
        if not self.root_path.is_dir():
            return []
        target = self.root_path
        if subfolder:
            if "/" in subfolder or "\\" in subfolder or ".." in subfolder:
                raise ValueError(f"Unsafe device subfolder: {subfolder!r}")
            candidate = self.root_path / subfolder
            if not is_symlink_or_reparse(candidate) and candidate.is_dir():
                resolved_cand = candidate.resolve()
                if resolved_cand.is_relative_to(self.root_path):
                    target = resolved_cand

        paths = scan_audio_directory(target, recursive=True)
        return [AudioFile.from_path(p) for p in paths]

    def safe_eject(self) -> bool:
        """Safely eject the removable volume."""
        return eject_volume(self.root_path)


def _win32_find_mounted_device(label: str) -> Optional[Path]:
    """Find mounted removable volume root matching label using Win32 kernel32 APIs (zero PowerShell/WMI)."""
    try:
        valid_label = validate_device_label(label)
    except ValueError:
        return None
    target = valid_label.lower()
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        _configure_kernel32(kernel32)
        bitmask = int(kernel32.GetLogicalDrives())
        matches: list[str] = []
        for idx in range(26):
            if not (bitmask & (1 << idx)):
                continue
            letter = chr(ord("A") + idx)
            root = f"{letter}:\\"
            drive_type = int(kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)))
            if drive_type != DRIVE_REMOVABLE:
                continue
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
    root = f"{drive}\\"
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
        _configure_kernel32(kernel32)
        if int(kernel32.GetDriveTypeW(ctypes.c_wchar_p(root))) != DRIVE_REMOVABLE:
            return False
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
    try:
        valid_label = validate_device_label(label)
    except ValueError:
        return None
    if sys.platform == "win32":
        return _win32_find_mounted_device(valid_label)
    elif sys.platform == "darwin":
        vol = Path("/Volumes") / valid_label
        if not is_symlink_or_reparse(vol) and vol.is_dir():
            resolved = vol.resolve()
            if resolved.is_relative_to(Path("/Volumes").resolve()):
                return resolved
    elif sys.platform.startswith("linux"):
        for base in (Path("/media"), Path("/mnt")):
            if is_symlink_or_reparse(base) or not base.is_dir():
                continue
            base_resolved = base.resolve()
            direct = base / valid_label
            if not is_symlink_or_reparse(direct) and direct.is_dir():
                resolved = direct.resolve()
                if resolved.is_relative_to(base_resolved):
                    return resolved
            try:
                children = [c for c in base.iterdir() if not is_symlink_or_reparse(c) and c.is_dir()]
            except OSError:
                continue
            for child in children:
                candidate = child / valid_label
                if not is_symlink_or_reparse(candidate) and candidate.is_dir():
                    resolved = candidate.resolve()
                    if resolved.is_relative_to(base_resolved):
                        return resolved

    return None


def eject_volume(path: Path) -> bool:
    """Safely eject a mounted removable volume across operating systems."""
    if is_symlink_or_reparse(path):
        return False
    if sys.platform == "win32":
        return _win32_eject_volume(path)
    elif sys.platform == "darwin":
        try:
            res = subprocess.run(
                ["diskutil", "eject", "--", str(path.resolve())],
                capture_output=True,
                timeout=15,
            )
            return res.returncode == 0
        except Exception:
            return False
    elif sys.platform.startswith("linux"):
        try:
            res = subprocess.run(
                ["umount", "--", str(path.resolve())],
                capture_output=True,
                timeout=15,
            )
            return res.returncode == 0
        except Exception:
            return False

    return False
