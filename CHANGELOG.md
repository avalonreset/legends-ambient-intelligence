# Changelog

All notable changes to `legends-ambient-intelligence` will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning.

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
