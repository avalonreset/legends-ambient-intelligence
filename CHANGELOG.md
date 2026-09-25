# Changelog

All notable changes to `legends-ambient-intelligence` will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning.

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
