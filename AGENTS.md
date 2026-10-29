# Legends Ambient Intelligence: Agent Rules

These rules apply to any agent working inside the `legends-ambient-intelligence` repository.

## 1. Product Identity and Language

- The official product name is **Legends Ambient Intelligence** (`legends-ambient-intelligence`).
- Do not use the deprecated name "life logger" or "Legends Life Logger".
- Hardware devices (such as the KT5000 or generic USB recorders) are input capture ears, not the product brand.
- Hard rule: zero em dashes (Unicode U+2014) or punctuation en dashes in copy, documentation, or code comments. Use colons, hyphens, periods, or commas instead.

## 2. Audio Safety and Ingestion Doctrine

- Never delete original files from recording media or source input folders. Ingest is strictly non-destructive.
- Deduplication is content-addressable: compute SHA-256 hashes and verify against existing archive manifests.
- Removable devices must be safely ejected after ingestion before instructing the user to disconnect hardware.

## 3. Architecture and Packaging

- The core package (`src/legends_ambient/`) relies on Python 3.11+ standard library for discovery, hashing, archiving, prompt recovery, and Obsidian formatting.
- ASR engines are pluggable. Whisper (`faster-whisper` or CLI) is the portable standard; NeMo Parakeet is supported for high-throughput GPU systems; `MockTranscriber` is provided for offline testing.
- Unit tests in `tests/` must execute quickly and pass completely offline without external network calls, GPU requirements, or connected hardware.
