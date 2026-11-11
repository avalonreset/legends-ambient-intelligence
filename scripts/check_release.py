#!/usr/bin/env python3
"""Release readiness gate for legends-ambient-intelligence."""
from __future__ import annotations

import hashlib
import json
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
    "MANIFEST.in",
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

TEXT_EXTS = {".py", ".md", ".toml", ".json", ".yml", ".yaml", ".cff", ".txt", ".in"}

FORBIDDEN_EXTS = {".ps1", ".bat", ".cmd", ".vbs", ".ahk", ".pem", ".key", ".p12", ".pfx"}

FORBIDDEN_PATTERNS = [
    r"(?i)[a-z]:\\users\\(?!public\b|default\b|someone\b|you\b|<)",
    r"CREATE_NO_WINDOW",
    r"0x08000000",
    r"(?i)-WindowStyle\s+Hidden",
    r"(?i)-ExecutionPolicy\s+Bypass",
    r"(?i)CryptUnprotectData",
    r"(?i)GetAsyncKeyState",
    r"(?i)IndexedDB",
    r"AKIA[0-9A-Z]{16}",
    r"ghp_[A-Za-z0-9]{36}",
    r"github_pat_[A-Za-z0-9_]{20,}",
]

MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def check_png_chunks(path: Path, issues: list[str]) -> None:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        issues.append(f"{path.name}: invalid PNG header")
        return
    offset = 8
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8].decode("latin1", errors="replace")
        if chunk_type in {"tEXt", "zTXt", "iTXt", "eXIf", "caBX"}:
            issues.append(f"{path.name}: forbidden metadata chunk {chunk_type}")
        offset += 12 + length


def check_webp_chunks(path: Path, issues: list[str]) -> None:
    data = path.read_bytes()
    for marker in (b"EXIF", b"XMP ", b"c2pa"):
        if marker in data:
            label = marker.decode("ascii", errors="replace").strip()
            issues.append(f"{path.name}: forbidden metadata marker {label}")


def check_markdown_links(md_path: Path, text: str, issues: list[str]) -> None:
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in MD_LINK_RE.finditer(line):
            target = match.group(1).strip()
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            clean = target.split("#", 1)[0].split("?", 1)[0].strip()
            if not clean:
                continue
            resolved = (md_path.parent / clean).resolve()
            if not resolved.exists():
                rel_md = md_path.relative_to(ROOT).as_posix()
                issues.append(f"Broken relative link in {rel_md}: {target}")


def check_assets_manifest(expected_version: str | None, issues: list[str]) -> None:
    manifest_path = ROOT / "assets/manifest.json"
    if not manifest_path.is_file():
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(f"Invalid assets/manifest.json: {exc}")
        return

    if expected_version and manifest.get("version") != expected_version:
        issues.append(
            f"assets/manifest.json version {manifest.get('version')!r} != {expected_version!r}"
        )

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        issues.append("assets/manifest.json must contain a non-empty 'files' list")
        return

    for entry in files:
        rel_path = entry.get("path", "")
        asset_file = ROOT / rel_path
        if not asset_file.is_file():
            issues.append(f"Manifest asset missing on disk: {rel_path}")
            continue
        raw = asset_file.read_bytes()
        actual_sha = hashlib.sha256(raw).hexdigest()
        if entry.get("bytes") != len(raw):
            issues.append(
                f"Manifest byte size mismatch for {rel_path}: {entry.get('bytes')} != {len(raw)}"
            )
        if entry.get("sha256") != actual_sha:
            issues.append(
                f"Manifest sha256 mismatch for {rel_path}: {entry.get('sha256')} != {actual_sha}"
            )


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
    recipe = (ROOT / "docs/AGENT-RECIPE.md").read_text(encoding="utf-8")

    m_py = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
    m_init = re.search(r'^__version__\s*=\s*"([^"]+)"', init_py, re.M)
    m_cit = re.search(r'^version:\s*"?([^"\n]+)"?', citation, re.M)
    m_chg = re.search(r"^##\s+\[?v?(\d+\.\d+\.\d+)\]?", changelog, re.M)
    m_rec = re.search(r"\(`v(\d+\.\d+\.\d+)`\)", recipe)

    versions = {
        "pyproject.toml": m_py.group(1) if m_py else None,
        "__init__.py": m_init.group(1) if m_init else None,
        "CITATION.cff": m_cit.group(1).strip() if m_cit else None,
        "CHANGELOG.md": m_chg.group(1) if m_chg else None,
        "docs/AGENT-RECIPE.md": m_rec.group(1) if m_rec else None,
    }
    if len(set(versions.values())) != 1 or None in versions.values():
        issues.append(f"Version mismatch across files: {versions}")

    expected_version = versions["pyproject.toml"]
    check_assets_manifest(expected_version, issues)

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
            if path.suffix.lower() in FORBIDDEN_EXTS:
                issues.append(f"Forbidden file extension in repo: {rel}")
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
                    check_markdown_links(path, text, issues)
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
