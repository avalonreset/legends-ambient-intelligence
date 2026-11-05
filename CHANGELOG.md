# Changelog

All notable changes to `legends-ambient-intelligence` will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning.

## [0.1.3] - 2026-11-05

### Added
- Added `docs/AGENT-RECIPE.md` with complete CLI reference and Windows Defender / EDR security guardrails, and expanded security guardrails in `AGENTS.md`.
- Added `--offline` and `--text` flags to `legends-ambient doctor`.
- Added `THIRD_PARTY_NOTICES.md`, `assets/manifest.json`, and `scripts/check_release.py`.

### Removed
- Removed legacy `bin/lai.ps1` wrapper and `LEGENDS.md` shim in favor of the standard `legends-ambient` / `lai` entrypoints and `docs/AGENT-RECIPE.md`.

## [0.1.2] - 2026-11-04

### Changed
- Replace Windows `powershell` / WMI `Win32_Volume` subprocess calls in `find_mounted_device()` and `eject_volume()` with direct Win32 `kernel32` APIs (`GetLogicalDrives`, `GetVolumeInformationW`, and `DeviceIoControl` `FSCTL_LOCK_VOLUME` / `FSCTL_DISMOUNT_VOLUME` / `IOCTL_STORAGE_EJECT_MEDIA`) via `ctypes`, eliminating PowerShell/WMI process spawning and fixing volume dismount exit-status checking.

## [0.1.1] - 2026-10-29

### Changed
- Raise minimum supported Python runtime to Python 3.11 (`requires-python = ">=3.11"`) across package metadata, offline `doctor` checks, and CI.
- Harden GitHub Actions workflows with 40-character commit SHA action pins, explicit `contents: read` permissions, and `pip>=26.2.2` before package installation.

## [0.1.0] - 2026-09-25 - Router-native reset

### Changed
- Reset to the router-native generation: `cto-legends` is the only registered skill, this repo vendors a pinned copy at `skills/cto-legends/SKILL.md` (router commit `6975dcbf073e5eec7a30ce6a04a6975238c61158`).
- Removed the per-module skill surface: `skills/legends-ambient-intelligence/` and its `src/` and `build/` mirrors, plus `bin/setup-multi-agent.ps1`.
- Added the contract agent block to `README.md`, `.legends-module`, and contract CI.

## [0.1.0] - 2026-09-24

### Added
- Initial public modular release of `legends-ambient-intelligence`.
- Dual-input ingestion supporting local directories (computer mic captures, voice memo drops) and removable hardware voice recorders (KT5000 / USB mass storage).
- Content-addressable SHA-256 deduplication and dated package archiving (`manifest.json`, `SHA256SUMS.txt`).
- Non-destructive ingestion doctrine ensuring source recording media are never deleted.
- Automatic USB volume detection and safe dismount/ejection.
- Pluggable ASR engine supporting local Whisper (`faster-whisper` and CLI), NVIDIA NeMo Parakeet, and deterministic offline mock.
- Full sidecar transcript generation: TXT, JSON, SRT, VTT, and word-level timestamps (`words.json`).
- Lost prompt recovery algorithm detecting split rollover boundaries and mid-thought continuation cues (`and`, `but`, `because`, `then`).
- Knowledge distillation engine extracting candidate action items, decisions, and top themes.
- Direct Obsidian markdown vault export linking audio evidence, duration, and provenance.
- Offline `doctor` command checking Python environment, audio binaries (ffmpeg/ffprobe), and ASR availability.
- Sanitized, portable agent skill for Grok, Codex, Gemini, Claude, and Cursor.
