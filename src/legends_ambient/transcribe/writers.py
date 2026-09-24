"""Sidecar artifact writers for transcripts (TXT, JSON, SRT, VTT, words, index)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from .engine import TranscriptionResult


def format_timestamp_srt(seconds: float) -> str:
    """Format seconds into SRT timestamp (HH:MM:SS,mmm)."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def format_timestamp_vtt(seconds: float) -> str:
    """Format seconds into WebVTT timestamp (HH:MM:SS.mmm)."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"


def write_transcript_artifacts(
    result: TranscriptionResult,
    output_dir: Path,
) -> dict[str, Path]:
    """Write sidecar artifacts (.txt, .json, .srt, .vtt, .words.json) for a result."""
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = Path(result.filename).stem
    paths: dict[str, Path] = {}

    # TXT
    txt_path = output_dir / f"{base_name}.txt"
    txt_path.write_text(result.text.strip() + "\n", encoding="utf-8")
    paths["txt"] = txt_path

    # JSON
    json_path = output_dir / f"{base_name}.json"
    data = {
        "audio_path": result.audio_path,
        "filename": result.filename,
        "duration_seconds": result.duration_seconds,
        "language": result.language,
        "model": result.model,
        "text": result.text,
        "segments": [
            {
                "id": s.id,
                "start": s.start,
                "end": s.end,
                "text": s.text,
            }
            for s in result.segments
        ],
    }
    json_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    paths["json"] = json_path

    # SRT
    srt_path = output_dir / f"{base_name}.srt"
    srt_lines: list[str] = []
    for idx, seg in enumerate(result.segments, start=1):
        srt_lines.append(str(idx))
        srt_lines.append(f"{format_timestamp_srt(seg.start)} --> {format_timestamp_srt(seg.end)}")
        srt_lines.append(seg.text.strip())
        srt_lines.append("")
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    paths["srt"] = srt_path

    # VTT
    vtt_path = output_dir / f"{base_name}.vtt"
    vtt_lines: list[str] = ["WEBVTT", ""]
    for seg in result.segments:
        vtt_lines.append(f"{format_timestamp_vtt(seg.start)} --> {format_timestamp_vtt(seg.end)}")
        vtt_lines.append(seg.text.strip())
        vtt_lines.append("")
    vtt_path.write_text("\n".join(vtt_lines), encoding="utf-8")
    paths["vtt"] = vtt_path

    # words.json
    all_words: list[dict] = []
    for seg in result.segments:
        for w in seg.words:
            all_words.append({
                "word": w.word,
                "start": w.start,
                "end": w.end,
                "confidence": w.confidence,
            })
    words_path = output_dir / f"{base_name}.words.json"
    words_path.write_text(json.dumps(all_words, indent=2) + "\n", encoding="utf-8")
    paths["words"] = words_path

    return paths


def write_transcript_index(
    results: Sequence[TranscriptionResult],
    output_file: Path,
) -> None:
    """Write markdown index table of transcript results."""
    lines: list[str] = [
        "# Transcript index",
        "",
        "Raw local ASR transcript artifacts for this ingest pass.",
        "",
        "| Recording | Duration (s) | Segments | Words | Artifacts |",
        "|---|---:|---:|---:|---|",
    ]

    for r in results:
        base = Path(r.filename).stem
        links = (
            f"[TXT]({base}.txt) . "
            f"[SRT]({base}.srt) . "
            f"[VTT]({base}.vtt) . "
            f"[JSON]({base}.json) . "
            f"[words]({base}.words.json)"
        )
        lines.append(f"| `{base}` | {r.duration_seconds:.2f} | {len(r.segments)} | {r.total_words} | {links} |")

    lines.extend([
        "",
        "Raw ASR output is immutable evidence. Distilled notes and prompt extracts are separate downstream derivatives.",
        "",
    ])
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(lines), encoding="utf-8")
