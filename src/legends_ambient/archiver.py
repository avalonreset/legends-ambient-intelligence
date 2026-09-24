"""Content-addressable deduplication and archive packaging."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Optional, Sequence

from .ingest.sources import AudioFile, compute_file_sha256


@dataclass
class IngestReceipt:
    """Receipt summarizing an archive ingestion pass."""

    status: str
    archive_root: str
    ingest_dir: Optional[str]
    total_scanned: int
    already_archived: int
    new_archived: int
    new_bytes: int
    manifest_path: Optional[str]
    device_ejected: bool = False
    source_mutated: bool = False


class Archiver:
    """Manages content-addressable audio archiving and deduplication."""

    def __init__(self, archive_root: Path) -> None:
        self.archive_root = archive_root.resolve()

    def get_known_hashes(self) -> set[str]:
        """Collect all existing SHA-256 hashes from previously archived manifests."""
        known: set[str] = set()
        if not self.archive_root.is_dir():
            return known

        for manifest_path in self.archive_root.glob("**/manifest.json"):
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                for rec in data.get("recordings", []):
                    sha = rec.get("sha256")
                    if sha:
                        known.add(sha.upper())
            except Exception:
                continue

        return known

    def archive(
        self,
        files: Sequence[AudioFile],
        slug: str = "creative-sketchpad",
        what_if: bool = False,
    ) -> IngestReceipt:
        """Deduplicate and archive a collection of audio files."""
        known = self.get_known_hashes()
        new_files = [f for f in files if f.sha256.upper() not in known]

        if not new_files:
            return IngestReceipt(
                status="no-new-recordings",
                archive_root=str(self.archive_root),
                ingest_dir=None,
                total_scanned=len(files),
                already_archived=len(files),
                new_archived=0,
                new_bytes=0,
                manifest_path=None,
            )

        now = datetime.now(timezone.utc)
        safe_slug = "".join(c if c.isalnum() else "-" for c in slug.lower()).strip("-") or "ingest"
        date_dir = self.archive_root / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d")
        ingest_dir = date_dir / safe_slug

        counter = 1
        while ingest_dir.exists():
            counter += 1
            ingest_dir = date_dir / f"{safe_slug}-{counter:02d}"

        if what_if:
            total_bytes = sum(f.size_bytes for f in new_files)
            return IngestReceipt(
                status="dry-run",
                archive_root=str(self.archive_root),
                ingest_dir=str(ingest_dir),
                total_scanned=len(files),
                already_archived=len(files) - len(new_files),
                new_archived=len(new_files),
                new_bytes=total_bytes,
                manifest_path=None,
            )

        raw_dir = ingest_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        manifest_recordings: list[dict] = []
        checksum_lines: list[str] = []
        total_bytes = 0
        used_names: set[str] = set()
        manifest_path = ingest_dir / "manifest.json"
        sums_path = ingest_dir / "SHA256SUMS.txt"

        try:
            for audio in new_files:
                dest_name = audio.filename
                if dest_name in used_names:
                    stem = Path(audio.filename).stem
                    suffix = Path(audio.filename).suffix
                    short_hash = audio.sha256[:8].lower()
                    dest_name = f"{stem}-{short_hash}{suffix}"
                    dup_counter = 1
                    while dest_name in used_names:
                        dup_counter += 1
                        dest_name = f"{stem}-{short_hash}-{dup_counter}{suffix}"
                used_names.add(dest_name)

                dest_file = raw_dir / dest_name
                shutil.copy2(audio.path, dest_file)
                verified_hash = compute_file_sha256(dest_file)
                if verified_hash != audio.sha256:
                    raise ValueError(
                        f"Integrity check failed copying {audio.filename}: expected {audio.sha256}, got {verified_hash}"
                    )

                total_bytes += audio.size_bytes
                manifest_recordings.append({
                    "filename": audio.filename,
                    "sha256": audio.sha256,
                    "size_bytes": audio.size_bytes,
                    "last_modified": audio.last_modified_iso,
                    "recording_start": audio.recording_start_iso,
                    "relative_path": f"raw/{dest_name}",
                })
                checksum_lines.append(f"{audio.sha256}  raw/{dest_name}")

            manifest = {
                "version": "1.0.0",
                "created_at": now.isoformat(),
                "slug": slug,
                "recordings_count": len(manifest_recordings),
                "total_bytes": total_bytes,
                "recordings": manifest_recordings,
            }

            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            sums_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
        except Exception:
            shutil.rmtree(ingest_dir, ignore_errors=True)
            raise

        return IngestReceipt(
            status="archived",
            archive_root=str(self.archive_root),
            ingest_dir=str(ingest_dir),
            total_scanned=len(files),
            already_archived=len(files) - len(new_files),
            new_archived=len(new_files),
            new_bytes=total_bytes,
            manifest_path=str(manifest_path),
            source_mutated=False,
        )
