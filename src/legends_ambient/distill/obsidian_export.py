"""Markdown formatting and export for Obsidian vaults."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .concepts import DistilledCandidate
from ..transcribe.engine import TranscriptionResult


def generate_obsidian_note(
    candidate: DistilledCandidate,
    result: TranscriptionResult,
    vault_path: Optional[Path] = None,
    note_slug: Optional[str] = None,
) -> tuple[str, Optional[Path]]:
    """Format a distilled transcript into an Obsidian-compatible markdown note."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    slug = note_slug or Path(result.filename).stem

    lines: list[str] = [
        "---",
        "type: ambient-distill",
        f"title: \"Ambient Note: {slug}\"",
        f"source_audio: \"{result.filename}\"",
        f"duration_seconds: {result.duration_seconds:.2f}",
        f"created: \"{now}\"",
        "tags: [ambient, audio, voice-sketchpad, legends]",
        "---",
        "",
        f"# Ambient Note: {slug}",
        "",
        f"> {candidate.summary}",
        "",
        "## Key takeaways",
        "",
    ]

    if candidate.raw_takeaways:
        for item in candidate.raw_takeaways:
            lines.append(f"- {item}")
    else:
        lines.append("- No explicit takeaways extracted.")

    lines.extend([
        "",
        "## Action candidates",
        "",
    ])

    if candidate.action_items:
        for action in candidate.action_items:
            lines.append(f"- [ ] {action}")
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
        f"- Audio source: `{result.filename}`",
        f"- Measured duration: {result.duration_seconds:.2f} seconds",
        f"- Language: {result.language}",
        f"- ASR Model: {result.model}",
        "",
    ])

    content = "\n".join(lines)
    written_path: Optional[Path] = None

    if vault_path:
        dest_dir = vault_path.resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        written_path = dest_dir / f"{slug}.md"
        written_path.write_text(content, encoding="utf-8")

    return content, written_path
