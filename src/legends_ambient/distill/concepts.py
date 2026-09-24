"""Extraction of key ideas, decisions, and action items from ambient transcripts."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Sequence


@dataclass
class DistilledCandidate:
    summary: str
    action_items: list[str] = field(default_factory=list)
    key_themes: list[str] = field(default_factory=list)
    raw_takeaways: list[str] = field(default_factory=list)


ACTION_CUES = re.compile(
    r"\b(need to|have to|should|must|remember to|make sure to|action item|todo)\b",
    re.IGNORECASE,
)
DECISION_CUES = re.compile(
    r"\b(decided|decision|going with|we will|i will|approved|chosen)\b",
    re.IGNORECASE,
)


def extract_distilled_candidates(text: str) -> DistilledCandidate:
    """Extract action items, themes, and candidate ideas from transcript text."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    action_items: list[str] = []
    takeaways: list[str] = []

    for s in sentences:
        clean = s.strip()
        if not clean:
            continue
        if ACTION_CUES.search(clean):
            action_items.append(clean)
        elif DECISION_CUES.search(clean) or len(clean.split()) > 6:
            if len(takeaways) < 10:
                takeaways.append(clean)

    # Word frequency for top themes
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    stop_words = {
        "this", "that", "with", "from", "have", "were", "what", "when", "where",
        "about", "would", "could", "should", "there", "their", "which", "going",
        "really", "think", "know", "just", "like", "because",
    }
    counts: dict[str, int] = {}
    for w in words:
        if w not in stop_words:
            counts[w] = counts.get(w, 0) + 1

    top_themes = [
        w for w, _ in sorted(counts.items(), key=lambda item: -item[1])[:5]
    ]

    summary = (
        sentences[0].strip()
        if sentences
        else "Ambient capture recording."
    )

    return DistilledCandidate(
        summary=summary,
        action_items=action_items[:8],
        key_themes=top_themes,
        raw_takeaways=takeaways[:8],
    )
