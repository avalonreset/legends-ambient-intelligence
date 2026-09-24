---
name: legends-ambient-intelligence
description: >
  Ambient audio capture, content-addressable archiving, local ASR, prompt
  continuation recovery, and Obsidian distillation for the Legends ecosystem.
  Use when the user mentions ambient intelligence, voice sketchpad, audio ingest,
  local audio transcription, prompt recovery, or processing voice memos.
---

# Legends Ambient Intelligence

Legends Ambient Intelligence turns passive background voice recording and ambient audio into structured, source-cited knowledge.

- Ingest from local computer microphone folders, voice memo drops, or dedicated hardware USB recorders.
- Content-addressable SHA-256 deduplication ensures recordings are never ingested twice.
- Safe archive preserving original files on the recording medium.
- Local transcription using portable Whisper or high-throughput NeMo Parakeet.
- Prompt continuation recovery across file rollover boundaries.
- Direct structured export to Obsidian vaults.

## Quick reference

```sh
# 1. Check system readiness and audio tools offline
legends-ambient doctor

# 2. Ingest from a local mic recording folder
legends-ambient ingest --source ./recordings --slug sketchpad-session

# 3. Or ingest from a mounted USB hardware recorder (e.g. KT5000)
legends-ambient ingest --device --eject --slug daily-sketchpad

# 4. Transcribe the ingested audio batch
legends-ambient transcribe ~/.legends-ambient/archive/2026/09/24/daily-sketchpad --backend whisper

# 5. Recover lost prompt continuation across file splits
legends-ambient recover --source ./recordings

# 6. Distill transcript into an Obsidian vault note
legends-ambient distill ./transcripts/recording.json --vault ~/Documents/ObsidianVault/Notes
```

## Agent operating rules

1. **Non-destructive capture:** Never delete files from a physical recording device or input source. The archiver copies files and verifies checksums; source originals remain untouched.
2. **Safe device ejection:** When ingesting from a mounted USB recorder or wearable device, safe eject is triggered before prompting the user to unplug the device.
3. **No raw transcript dumps:** Do not paste raw, multi-hour transcripts directly into user chat or knowledge vaults. Use `distill` to extract key takeaways, decisions, action candidates, and audio provenance.
4. **Offline doctor first:** Before running large batch jobs, run `legends-ambient doctor` to verify local tools (ffmpeg, ffprobe, and ASR backends) without making external network calls.
