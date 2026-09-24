"""Command line interface for Legends Ambient Intelligence."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Optional

from . import __version__
from .archiver import Archiver
from .config import (
    get_default_archive_root,
    get_default_device_label,
    get_default_model_name,
)
from .distill.concepts import extract_distilled_candidates
from .distill.obsidian_export import generate_obsidian_note
from .distill.prompt_recovery import analyze_prompt_recovery
from .doctor import Doctor
from .ingest.device_source import DeviceSource, find_mounted_device
from .ingest.local_source import LocalDirectorySource
from .ingest.sources import AudioFile, scan_audio_directory
from .transcribe.engine import Transcriber, TranscriptionResult
from .transcribe.mock_backend import MockTranscriber
from .transcribe.parakeet_backend import ParakeetTranscriber
from .transcribe.whisper_backend import WhisperTranscriber
from .transcribe.writers import write_transcript_artifacts, write_transcript_index


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="legends-ambient",
        description="Legends Ambient Intelligence: audio capture, deduplicated archive, ASR, and distillation.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=get_default_archive_root(),
        help="Root directory for deduplicated audio archives.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # doctor
    p_doc = subparsers.add_parser("doctor", help="Check system readiness and dependencies offline.")
    p_doc.add_argument("--device-label", default=get_default_device_label())
    p_doc.add_argument("--json", action="store_true", help="Output results in JSON format.")

    # status
    p_status = subparsers.add_parser("status", help="Show archive state, known hashes, and device discovery.")
    p_status.add_argument("--device-label", default=get_default_device_label())

    # ingest
    p_ingest = subparsers.add_parser("ingest", help="Discover, hash, and archive new audio files safely.")
    p_ingest.add_argument("--source", type=Path, help="Local directory of audio files to ingest.")
    p_ingest.add_argument("--device", action="store_true", help="Auto-detect mounted USB recorder.")
    p_ingest.add_argument("--device-label", default=get_default_device_label(), help="Volume label of USB recorder.")
    p_ingest.add_argument("--slug", default="creative-sketchpad", help="Descriptive slug for this ingest session.")
    p_ingest.add_argument("--what-if", action="store_true", help="Preview new files without copying.")
    p_ingest.add_argument("--eject", action="store_true", help="Safely eject the USB recorder when finished.")

    # transcribe
    p_trans = subparsers.add_parser("transcribe", help="Transcribe an ingested package or audio file.")
    p_trans.add_argument("target", type=Path, help="Directory containing raw audio or single audio file.")
    p_trans.add_argument("--backend", choices=["whisper", "parakeet", "mock"], default="whisper")
    p_trans.add_argument("--model", default=get_default_model_name(), help="Model name or size.")

    # recover
    p_rec = subparsers.add_parser("recover", help="Analyze prompt continuation and split rollover boundaries.")
    p_rec.add_argument("--source", type=Path, help="Directory of audio recordings.")
    p_rec.add_argument("--device", action="store_true", help="Use mounted hardware recorder.")
    p_rec.add_argument("--device-label", default=get_default_device_label())
    p_rec.add_argument("--transcript", type=Path, help="Path to latest transcript text for continuation check.")
    p_rec.add_argument("--latest-tail", type=int, default=15, help="Minutes of latest recording tail.")
    p_rec.add_argument("--predecessor-tail", type=int, default=5, help="Minutes of predecessor tail.")

    # distill
    p_dist = subparsers.add_parser("distill", help="Extract concepts and export to an Obsidian note.")
    p_dist.add_argument("transcript", type=Path, help="Path to transcript TXT or JSON.")
    p_dist.add_argument("--vault", type=Path, help="Destination Obsidian vault directory.")
    p_dist.add_argument("--slug", help="Note filename/title slug.")

    return parser


def cmd_doctor(args: argparse.Namespace) -> int:
    doc = Doctor(archive_root=args.archive_root, device_label=args.device_label)
    results = doc.run_all()
    if args.json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        print("Legends Ambient Intelligence: Doctor")
        print("-------------------------------------")
        for r in results:
            print(f"[{r.status:4s}] {r.name:18s} {r.detail}")
    failures = sum(1 for r in results if r.status == "FAIL")
    return 1 if failures > 0 else 0


def cmd_status(args: argparse.Namespace) -> int:
    archiver = Archiver(archive_root=args.archive_root)
    known = archiver.get_known_hashes()
    device = find_mounted_device(args.device_label)

    print("Legends Ambient Intelligence: Status")
    print(f"Archive root:       {args.archive_root}")
    print(f"Archived hashes:    {len(known)}")
    print(f"Device label check: {args.device_label}")
    print(f"Device mounted:     {device or 'None detected'}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    archiver = Archiver(archive_root=args.archive_root)
    discovered_files: list[AudioFile] = []
    eject_fn = None

    if args.source:
        local_src = LocalDirectorySource(args.source)
        if not local_src.exists():
            print(f"Error: Source directory does not exist: {args.source}", file=sys.stderr)
            return 1
        discovered_files = local_src.discover()
    elif args.device or not args.source:
        mount = find_mounted_device(args.device_label)
        if not mount:
            print(f"Error: No mounted USB device found with label '{args.device_label}'.", file=sys.stderr)
            print("Specify a directory with --source to ingest computer mic or local recordings.", file=sys.stderr)
            return 1
        dev_src = DeviceSource(mount, volume_label=args.device_label)
        discovered_files = dev_src.discover()
        if args.eject:
            eject_fn = dev_src.safe_eject

    receipt = archiver.archive(
        files=discovered_files,
        slug=args.slug,
        what_if=args.what_if,
    )

    if eject_fn and not args.what_if:
        ejected = eject_fn()
        receipt.device_ejected = ejected

    print(json.dumps(asdict(receipt), indent=2))

    if receipt.device_ejected:
        print("\nNotice: Removable device safely unmounted. Safe to unplug.")

    return 0


def cmd_transcribe(args: argparse.Namespace) -> int:
    target = args.target.resolve()
    if not target.exists():
        print(f"Error: Target path does not exist: {target}", file=sys.stderr)
        return 1

    transcriber: Transcriber
    if args.backend == "mock":
        transcriber = MockTranscriber()
    elif args.backend == "parakeet":
        transcriber = ParakeetTranscriber(model_name=args.model)
    else:
        transcriber = WhisperTranscriber(model_name=args.model)

    availability = getattr(transcriber, "is_available", None)
    if callable(availability) and not availability():
        print(f"Error: Backend '{args.backend}' is not available in this environment.", file=sys.stderr)
        if args.backend == "whisper":
            print("Install faster-whisper or the whisper CLI to enable it.", file=sys.stderr)
        elif args.backend == "parakeet":
            print("Parakeet requires NVIDIA NeMo and a CUDA-capable GPU.", file=sys.stderr)
        return 1

    files_to_transcribe: list[Path] = []
    if target.is_file():
        files_to_transcribe = [target]
        output_dir = target.parent / "transcripts"
    else:
        raw_dir = target / "raw" if (target / "raw").is_dir() else target
        files_to_transcribe = scan_audio_directory(raw_dir)
        output_dir = target / "transcripts"

    if not files_to_transcribe:
        print("No audio files found to transcribe.")
        return 0

    print(f"Transcribing {len(files_to_transcribe)} recording(s) using backend '{args.backend}'...")
    results: list[TranscriptionResult] = []
    for f in files_to_transcribe:
        print(f"  -> {f.name}...")
        try:
            res = transcriber.transcribe(f)
        except Exception as e:
            print(f"Error: Transcription failed for {f.name}: {e}", file=sys.stderr)
            return 1
        results.append(res)
        write_transcript_artifacts(res, output_dir)

    write_transcript_index(results, output_dir / "index.md")
    print(f"Done. Artifacts written to {output_dir}")
    return 0


def cmd_recover(args: argparse.Namespace) -> int:
    audio_files: list[AudioFile] = []
    if args.source:
        local_src = LocalDirectorySource(args.source)
        audio_files = local_src.discover()
    elif args.device or not args.source:
        mount = find_mounted_device(args.device_label)
        if not mount:
            print(f"Error: Device with label '{args.device_label}' not found.", file=sys.stderr)
            return 1
        dev_src = DeviceSource(mount, volume_label=args.device_label)
        audio_files = dev_src.discover()

    if not audio_files:
        print("No audio recordings found for prompt recovery analysis.")
        return 1

    transcript_text: Optional[str] = None
    if args.transcript and args.transcript.is_file():
        transcript_text = args.transcript.read_text(encoding="utf-8")

    plan = analyze_prompt_recovery(
        audio_files=audio_files,
        latest_transcript_text=transcript_text,
        latest_tail_minutes=args.latest_tail,
        predecessor_tail_minutes=args.predecessor_tail,
    )

    print(json.dumps(asdict(plan), indent=2))
    return 0


def cmd_distill(args: argparse.Namespace) -> int:
    transcript_path = args.transcript.resolve()
    if not transcript_path.is_file():
        print(f"Error: Transcript file not found: {transcript_path}", file=sys.stderr)
        return 1

    text = ""
    duration = 0.0
    model = "unknown"
    language = "en"

    if transcript_path.suffix.lower() == ".json":
        try:
            data = json.loads(transcript_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
            print(f"Error: Cannot parse transcript JSON {transcript_path}: {e}", file=sys.stderr)
            return 1
        if not isinstance(data, dict):
            print(f"Error: Transcript JSON must be an object: {transcript_path}", file=sys.stderr)
            return 1
        text = data.get("text", "")
        if not isinstance(text, str):
            text = str(text)
        try:
            duration = float(data.get("duration_seconds", 0.0))
        except (TypeError, ValueError):
            print(f"Error: Invalid duration_seconds in {transcript_path}.", file=sys.stderr)
            return 1
        model = data.get("model", "unknown")
        language = data.get("language", "en")
    else:
        try:
            text = transcript_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as e:
            print(f"Error: Cannot read transcript file {transcript_path}: {e}", file=sys.stderr)
            return 1

    candidate = extract_distilled_candidates(text)
    result = TranscriptionResult(
        audio_path="",
        filename=transcript_path.stem,
        duration_seconds=duration,
        language=language,
        text=text,
        model=model,
    )

    try:
        content, written = generate_obsidian_note(
            candidate=candidate,
            result=result,
            vault_path=args.vault,
            note_slug=args.slug,
        )
    except (OSError, ValueError) as e:
        print(f"Error: Cannot write Obsidian note: {e}", file=sys.stderr)
        return 1

    if written:
        print(f"Exported distilled note to: {written}")
    else:
        print(content)

    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return cmd_doctor(args)
    elif args.command == "status":
        return cmd_status(args)
    elif args.command == "ingest":
        return cmd_ingest(args)
    elif args.command == "transcribe":
        return cmd_transcribe(args)
    elif args.command == "recover":
        return cmd_recover(args)
    elif args.command == "distill":
        return cmd_distill(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
