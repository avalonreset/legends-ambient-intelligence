#!/usr/bin/env python3
"""Release readiness gate for legends-ambient-intelligence."""
from __future__ import annotations

import os
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    "NOTICE",
    "THIRD_PARTY_NOTICES.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SUPPORT.md",
    "CITATION.cff",
    "AGENTS.md",
    "docs/AGENT-RECIPE.md",
    ".legends-module",
    "skills/cto-legends/SKILL.md",
    "assets/banner.png",
    "assets/banner.webp",
    "assets/preview.png",
    "assets/social-preview.png",
    "assets/manifest.json",
]

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

TEXT_EXTS = {".py", ".md", ".toml", ".json", ".yml", ".yaml", ".cff", ".txt"}

FORBIDDEN_PATTERNS = [
    r"(?i)[a-z]:\\users\\(?!public\b|default\b|someone\b|you\b|<)",
    r"CREATE_NO_WINDOW",
    r"0x08000000",
    r"(?i)-WindowStyle\s+Hidden",
    r"(?i)-ExecutionPolicy\s+Bypass",
    r"(?i)CryptUnprotectData",
    r"(?i)GetAsyncKeyState",
    r"(?i)IndexedDB",
]


def check_png_chunks(path: Path, issues: list[str]) -> None:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        issues.append(f"{path.name}: invalid PNG header")
        return
    offset = 8
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8].decode("latin1", errors="replace")
        if chunk_type in {"tEXt", "zTXt", "iTXt", "eXIf"}:
            issues.append(f"{path.name}: forbidden metadata chunk {chunk_type}")
        offset += 12 + length


def check_webp_chunks(path: Path, issues: list[str]) -> None:
    data = path.read_bytes()
    for marker in (b"EXIF", b"XMP "):
        if marker in data:
            label = marker.decode("ascii").strip()
            issues.append(f"{path.name}: forbidden metadata marker {label}")


def main() -> int:
    issues: list[str] = []

    for rel in REQUIRED_FILES:
        if not (ROOT / rel).is_file():
            issues.append(f"Missing required file: {rel}")

    if (ROOT / ".legends-module").is_file():
        mod = (ROOT / ".legends-module").read_text(encoding="utf-8").strip()
        if mod != "legends-ambient-intelligence":
            issues.append(f".legends-module mismatch: {mod!r}")

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    init_py = (ROOT / "src/legends_ambient/__init__.py").read_text(encoding="utf-8")
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    m_py = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
    m_init = re.search(r'^__version__\s*=\s*"([^"]+)"', init_py, re.M)
    m_cit = re.search(r'^version:\s*"?([^"\n]+)"?', citation, re.M)
    m_chg = re.search(r"^##\s+\[?v?(\d+\.\d+\.\d+)\]?", changelog, re.M)

    versions = {
        "pyproject.toml": m_py.group(1) if m_py else None,
        "__init__.py": m_init.group(1) if m_init else None,
        "CITATION.cff": m_cit.group(1).strip() if m_cit else None,
        "CHANGELOG.md": m_chg.group(1) if m_chg else None,
    }
    if len(set(versions.values())) != 1 or None in versions.values():
        issues.append(f"Version mismatch across files: {versions}")

    skill_files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info")
        ]
        for fn in filenames:
            path = Path(dirpath) / fn
            rel = path.relative_to(ROOT).as_posix()
            if fn == "SKILL.md":
                skill_files.append(rel)
            if path.suffix.lower() in {".ps1", ".bat", ".cmd", ".vbs", ".ahk"}:
                issues.append(f"Forbidden script extension in repo: {rel}")
            if path.suffix.lower() in TEXT_EXTS:
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    issues.append(f"Non-UTF-8 file: {rel}")
                    continue
                if "\ufffd" in text:
                    issues.append(f"Replacement character U+FFFD in {rel}")
                if path.suffix.lower() == ".md":
                    if "\u2014" in text or "\u2013" in text:
                        issues.append(f"Em/en-dash found in markdown file: {rel}")
                if rel != "scripts/check_release.py":
                    for pat in FORBIDDEN_PATTERNS:
                        if re.search(pat, text):
                            issues.append(f"Forbidden pattern {pat!r} matched in {rel}")

    if skill_files != ["skills/cto-legends/SKILL.md"]:
        issues.append(f"One-Skill Rule violation: found SKILL.md at {skill_files}")

    for png in ("assets/banner.png", "assets/preview.png", "assets/social-preview.png"):
        p = ROOT / png
        if p.is_file():
            check_png_chunks(p, issues)
    webp = ROOT / "assets/banner.webp"
    if webp.is_file():
        check_webp_chunks(webp, issues)

    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1

    print("Release checks: PASS (0 issues)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
