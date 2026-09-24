"""Lost prompt recovery across recording splits and rollover boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Optional, Sequence

from ..ingest.sources import AudioFile

CONTINUATION_PATTERN = re.compile(
    r"^(and|but|because|then|also|which|that|or|nor|yet)\b",
    re.IGNORECASE,
)


@dataclass
class RecoveryClip:
    order: int
    role: str
    source_path: str
    tail_seconds: int
    output_base: str


@dataclass
class PromptRecoveryPlan:
    status: str
    reason: str
    latest_file: str
    predecessor_file: Optional[str]
    rollover_detected: bool
    boundary_gap_seconds: Optional[float]
    starts_mid_thought: bool
    clip_plan: list[RecoveryClip]


def analyze_prompt_recovery(
    audio_files: Sequence[AudioFile],
    latest_transcript_text: Optional[str] = None,
    latest_tail_minutes: int = 15,
    predecessor_tail_minutes: int = 5,
    rollover_tolerance_seconds: float = 2.0,
) -> PromptRecoveryPlan:
    """Analyze audio files to determine if thought continuation across a split occurred."""
    if not audio_files:
        raise ValueError("No audio files provided for prompt recovery analysis.")

    # Sort files by recording start if available, else by last modified
    sorted_files = sorted(
        audio_files,
        key=lambda f: f.recording_start_iso or f.last_modified_iso,
    )
    latest = sorted_files[-1]
    predecessor = sorted_files[-2] if len(sorted_files) > 1 else None

    rollover_detected = False
    boundary_gap_seconds = None

    if predecessor and latest.recording_start_iso:
        try:
            latest_start = datetime.fromisoformat(latest.recording_start_iso)
            pred_mtime = datetime.fromisoformat(predecessor.last_modified_iso)
            latest_ts = latest_start.replace(tzinfo=timezone.utc).timestamp() if latest_start.tzinfo is None else latest_start.timestamp()
            pred_ts = pred_mtime.replace(tzinfo=timezone.utc).timestamp() if pred_mtime.tzinfo is None else pred_mtime.timestamp()
            gap = abs(latest_ts - pred_ts)
            boundary_gap_seconds = round(gap, 3)
            rollover_detected = boundary_gap_seconds <= rollover_tolerance_seconds
        except (ValueError, TypeError):
            boundary_gap_seconds = None
            rollover_detected = False

    starts_mid_thought = False
    if latest_transcript_text:
        cleaned = latest_transcript_text.strip()
        starts_mid_thought = bool(CONTINUATION_PATTERN.search(cleaned))

    include_predecessor = predecessor is not None and (rollover_detected or starts_mid_thought)

    safe_latest_tail = max(0, latest_tail_minutes)
    safe_predecessor_tail = max(0, predecessor_tail_minutes)

    clip_plan: list[RecoveryClip] = []
    if include_predecessor and predecessor:
        clip_plan.append(
            RecoveryClip(
                order=1,
                role="predecessor-tail",
                source_path=str(predecessor.path),
                tail_seconds=safe_predecessor_tail * 60,
                output_base=f"previous-tail-{safe_predecessor_tail}min",
            )
        )

    clip_plan.append(
        RecoveryClip(
            order=len(clip_plan) + 1,
            role="latest-tail",
            source_path=str(latest.path),
            tail_seconds=safe_latest_tail * 60,
            output_base=f"tail-{safe_latest_tail}min",
        )
    )

    if rollover_detected:
        reason = "predecessor-close-time-matches-latest-filename-start"
    elif starts_mid_thought and predecessor:
        reason = "latest-exact-asr-starts-with-continuation-cue"
    elif not predecessor:
        reason = "no-predecessor-found"
    else:
        reason = "no-rollover-or-continuation-evidence"

    return PromptRecoveryPlan(
        status="include-predecessor-tail" if include_predecessor else "latest-only",
        reason=reason,
        latest_file=latest.filename,
        predecessor_file=predecessor.filename if predecessor else None,
        rollover_detected=rollover_detected,
        boundary_gap_seconds=boundary_gap_seconds,
        starts_mid_thought=starts_mid_thought,
        clip_plan=clip_plan,
    )
