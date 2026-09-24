"""Markdown formatting and export for Obsidian vaults."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .concepts import DistilledCandidate
from ..transcribe.engine import TranscriptionResult


def _one_line(text: str) -> str:
    """Collapse whitespace and newlines so markdown list items stay on one line."""
    return " ".join(text.split())


def _safe_file_slug(raw_slug: str) -> str:
    """Sanitize a note slug so it is safe to use as a single filename."""
    cleaned = raw_slug.replace("/", "-").replace("\\", "-").strip()
    if not cleaned.strip(".-"):
        return "ambient-note"
    return cleaned


def generate_obsidian_note(
    candidate: DistilledCandidate,
    result: TranscriptionResult,
    vault_path: Optional[Path] = None,
    note_slug: Optional[str] = None,
) -> tuple[str, Optional[Path]]:
    """Format a distilled transcript into an Obsidian-compatible markdown note."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_slug = note_slug or Path(result.filename).stem or "ambient-note"
    file_slug = _safe_file_slug(raw_slug)
    display_slug = _one_line(raw_slug).replace('"', "'")
    display_source = _one_line(result.filename).replace('"', "'")

    lines: list[str] = [
        "---",
        "type: ambient-distill",
        f"title: \"Ambient Note: {display_slug}\"",
        f"source_audio: \"{display_source}\"",
        f"duration_seconds: {result.duration_seconds:.2f}",
        f"created: \"{now}\"",
        "tags: [ambient, audio, voice-sketchpad, legends]",
        "---",
        "",
        f"# Ambient Note: {display_slug}",
        "",
        f"> {_one_line(candidate.summary)}",
        "",
        "## Key takeaways",
        "",
    ]

    if candidate.raw_takeaways:
        for item in candidate.raw_takeaways:
            lines.append(f"- {_one_line(item)}")
    else:
        lines.append("- No explicit takeaways extracted.")

    lines.extend([
        "",
        "## Action candidates",
        "",
    ])

    if candidate.action_items:
        for action in candidate.action_items:
            lines.append(f"- [ ] {_one_line(action)}")
    else:
        lines.append("- No immediate action items detected.")

    if candidate.key_themes:
        lines.extend([
            "",
            "## Themes",
            "",
            ", ".join(f"`{t}`" for t in candidate.key_themes),
        ])

    lines.extend([
        "",
        "## Source evidence & provenance",
        "",
        f"- Audio source: `{display_source}`",
        f"- Measured duration: {result.duration_seconds:.2f} seconds",
        f"- Language: {result.language}",
        f"- ASR Model: {result.model}",
        "",
    ])

    content = "\n".join(lines)
    written_path: Optional[Path] = None

    if vault_path:
        dest_dir = vault_path.resolve()
        if dest_dir.exists() and not dest_dir.is_dir():
            raise ValueError(f"Vault path is not a directory: {vault_path}")
        dest_dir.mkdir(parents=True, exist_ok=True)
        written_path = dest_dir / f"{file_slug}.md"
        written_path.write_text(content, encoding="utf-8")

    return content, written_path
