"""Sidecar artifact writers for transcripts (TXT, JSON, SRT, VTT, words, index)."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Sequence

from ..ingest.sources import is_symlink_or_reparse
from .engine import TranscriptionResult

_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _safe_file_slug(raw_slug: str) -> str:
    """Sanitize a filename stem so it is safe to use as a single filename across OSes."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", raw_slug.strip()).strip(".-")
    if not cleaned:
        return "transcript"
    stem = cleaned.split(".", 1)[0].upper()
    if stem in _WINDOWS_RESERVED_NAMES:
        cleaned = f"file-{cleaned}"
    return cleaned[:120]


def _split_timestamp(seconds: float) -> tuple[int, int, int, int]:
    """Split seconds into (hours, minutes, seconds, millis) with rounding carry."""
    total_ms = int(round(max(0.0, seconds) * 1000))
    hrs, rem = divmod(total_ms, 3600000)
    mins, rem = divmod(rem, 60000)
    secs, millis = divmod(rem, 1000)
    return hrs, mins, secs, millis


def format_timestamp_srt(seconds: float) -> str:
    """Format seconds into SRT timestamp (HH:MM:SS,mmm)."""
    hrs, mins, secs, millis = _split_timestamp(seconds)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def format_timestamp_vtt(seconds: float) -> str:
    """Format seconds into WebVTT timestamp (HH:MM:SS.mmm)."""
    hrs, mins, secs, millis = _split_timestamp(seconds)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"


def write_transcript_artifacts(
    result: TranscriptionResult,
    output_dir: Path,
    *,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Write sidecar artifacts (.txt, .json, .srt, .vtt, .words.json) for a result."""
    if is_symlink_or_reparse(output_dir):
        raise ValueError(f"Refusing symlinked transcript output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_dir = output_dir.resolve()
    base_name = _safe_file_slug(Path(result.filename).stem)
    paths: dict[str, Path] = {}

    txt_path = output_dir / f"{base_name}.txt"
    json_path = output_dir / f"{base_name}.json"
    srt_path = output_dir / f"{base_name}.srt"
    vtt_path = output_dir / f"{base_name}.vtt"
    words_path = output_dir / f"{base_name}.words.json"

    for target in (txt_path, json_path, srt_path, vtt_path, words_path):
        if is_symlink_or_reparse(target):
            raise ValueError(f"Refusing symlinked transcript artifact path: {target}")
        if not target.resolve().is_relative_to(resolved_dir):
            raise ValueError(f"Transcript artifact path escapes output_dir: {target}")
        if target.exists() and not overwrite:
            raise FileExistsError(
                f"Refusing to overwrite existing transcript artifact without --overwrite: {target}"
            )

    # TXT
    txt_path.write_text(result.text.strip() + "\n", encoding="utf-8")
    paths["txt"] = txt_path

    # JSON
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
    srt_lines: list[str] = []
    for idx, seg in enumerate(result.segments, start=1):
        srt_lines.append(str(idx))
        srt_lines.append(f"{format_timestamp_srt(seg.start)} --> {format_timestamp_srt(seg.end)}")
        srt_lines.append(seg.text.strip())
        srt_lines.append("")
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    paths["srt"] = srt_path

    # VTT
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
    words_path.write_text(json.dumps(all_words, indent=2) + "\n", encoding="utf-8")
    paths["words"] = words_path

    return paths


def write_transcript_index(
    results: Sequence[TranscriptionResult],
    output_file: Path,
    *,
    overwrite: bool = False,
) -> None:
    """Write markdown index table of transcript results."""
    if is_symlink_or_reparse(output_file) or is_symlink_or_reparse(output_file.parent):
        raise ValueError(f"Refusing symlinked transcript index path: {output_file}")
    if output_file.exists() and not overwrite:
        raise FileExistsError(
            f"Refusing to overwrite existing transcript index without --overwrite: {output_file}"
        )
    lines: list[str] = [
        "# Transcript index",
        "",
        "Raw local ASR transcript artifacts for this ingest pass.",
        "",
        "| Recording | Duration (s) | Segments | Words | Artifacts |",
        "|---|---:|---:|---:|---|",
    ]

    for r in results:
        base = _safe_file_slug(Path(r.filename).stem)
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
