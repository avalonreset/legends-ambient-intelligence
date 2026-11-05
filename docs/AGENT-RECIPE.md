# Legends Ambient Intelligence Agent Recipe

Deterministic operator procedure for `legends-ambient-intelligence` (`v0.1.3`). Loaded by `cto-legends handoff legends-ambient-intelligence`. Do not register a separate per-module skill.

## 1. Readiness & Diagnostics

Verify package and environment readiness offline before running ingestion, transcription, or distillation:

```bash
legends-ambient doctor --offline --json
```

- `legends-ambient doctor` (or `lai doctor`) executes 100% offline, checking Python 3.11+, archive root writability, optional `ffmpeg`/`ffprobe` binaries, optional `faster-whisper`/`whisper` or NVIDIA NeMo Parakeet ASR engines, and mounted USB voice recorder volumes.
- Check known SHA-256 archive state and mounted hardware volumes with:

```bash
legends-ambient status
```

## 2. Complete CLI Command Surface

| Command | Purpose | Mutates Local State / Network |
| --- | --- | --- |
| `legends-ambient [--archive-root <dir>] doctor [--offline] [--device-label <label>] [--json] [--text]` | Run offline readiness checks across Python, archive storage, audio tools, ASR backends, and USB hardware | Read-only (ensures archive root dir exists) |
| `legends-ambient [--archive-root <dir>] status [--device-label <label>]` | Show archive root, count of deduplicated SHA-256 hashes, and USB volume mount state | Read-only |
| `legends-ambient [--archive-root <dir>] ingest (--source <dir> \| --device) [--device-label <label>] [--slug <slug>] [--what-if] [--eject]` | Non-destructively discover audio files, deduplicate by SHA-256 against archive manifests, copy new files into a dated package (`manifest.json`, `SHA256SUMS.txt`), and optionally dismount USB media | Writes archive package (`--what-if` is read-only) |
| `legends-ambient [--archive-root <dir>] transcribe <target_dir_or_file> [--backend whisper\|parakeet\|mock] [--model <name>]` | Transcribe an archived session package or single audio file into `transcripts/` (`TXT`, `JSON`, `SRT`, `VTT`, `words.json`, and `index.md`) | Writes transcript sidecars |
| `legends-ambient [--archive-root <dir>] recover (--source <dir> \| --device) [--device-label <label>] [--transcript <file>] [--latest-tail 15] [--predecessor-tail 5]` | Analyze split-file rollover boundaries and mid-thought continuation words (`and`, `but`, `because`, `then`) to produce a prompt-recovery plan | Read-only (emits JSON plan) |
| `legends-ambient [--archive-root <dir>] distill <transcript.json_or_txt> [--vault <obsidian_dir>] [--slug <note_slug>]` | Extract action items, decisions, and recurring themes from a transcript and format or write an Obsidian Markdown note with audio provenance | Writes `.md` note if `--vault` is given, else stdout |

## 3. Standard Operating Procedure

1. **Readiness check**: Run `legends-ambient doctor --offline --json`.
2. **Non-destructive ingestion**:
   - Preview first with `legends-ambient ingest --source <dir> --what-if` (or `--device --what-if`).
   - Archive new recordings with `legends-ambient ingest --source <dir> --slug <session-slug>` (add `--device --eject` when ingesting from a USB voice recorder so the volume is cleanly locked, dismounted, and ejected before unplugging).
3. **Offline transcription**:
   - Run `legends-ambient transcribe <package_dir> --backend whisper` (or `--backend parakeet` on CUDA systems, `--backend mock` for deterministic tests).
4. **Rollover recovery & vault distillation**:
   - If a thought spans 15-minute recorder split files, run `legends-ambient recover --source <dir> --transcript <latest.txt>`.
   - Export structured notes to Obsidian with `legends-ambient distill <transcript.json> --vault <vault_dir> --slug <note-slug>`.

## 4. EDR and Security Guardrails

- **No hidden consoles or PowerShell/WMI subprocesses**: Never spawn `powershell.exe`, `wmic.exe`, `cmd.exe`, hidden console windows, or execution-policy bypass shell wrappers. On Windows, USB volume discovery and safe ejection use direct Win32 `kernel32` volume APIs (`GetLogicalDrives`, `GetVolumeInformationW`, `DeviceIoControl`) in `src/legends_ambient/ingest/device_source.py`.
- **Non-destructive media doctrine**: Never delete, truncate, or modify original recordings on USB hardware recorders or source folders.
- **No credential or browser harvesting**: Never access browser profile databases, DPAPI stores, or third-party credential stores. All transcription and distillation run locally offline.
