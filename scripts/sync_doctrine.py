#!/usr/bin/env python3
"""Synchronize or classify a content-stamped doctrine block without overwriting local edits.

sync_doctrine : StampedDoctrine × InstructionFile → SyncOutcome
check_doctrine : StampedDoctrine × InstructionFile → DoctrineStatus
"""

from __future__ import annotations

import hashlib
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

BEGIN_TOKEN = "<!-- BEGIN SYNCED DOCTRINE;"
END_MARKER = "<!-- END SYNCED DOCTRINE -->"
BEGIN_RE = re.compile(
    r"^<!-- BEGIN SYNCED DOCTRINE; source-sha256=([0-9a-f]{64}) -->$",
    re.MULTILINE,
)
END_RE = re.compile(rf"^{re.escape(END_MARKER)}$", re.MULTILINE)


class SyncOutcome(Enum):
    """The two successful filesystem outcomes."""

    UPDATED = "UPDATED"
    UNCHANGED = "UNCHANGED"


@dataclass(frozen=True)
class StampedDoctrine:
    """One well-formed doctrine block and its claimed content stamp."""

    start: int
    end: int
    body: str
    source_stamp: str
    rendered: str


@dataclass(frozen=True)
class SyncResult:
    """A successful sync outcome and the source stamp that produced it."""

    outcome: SyncOutcome
    source_stamp: str


@dataclass(frozen=True)
class CurrentDoctrine:
    """A clean target carrying the available source stamp."""

    source_stamp: str


@dataclass(frozen=True)
class StaleDoctrine:
    """A clean target carrying a different source stamp."""

    installed_source_stamp: str
    available_source_stamp: str


@dataclass(frozen=True)
class LocallyEditedDoctrine:
    """A target whose body differs from its claimed source stamp."""

    marker_source_stamp: str
    content_source_stamp: str
    available_source_stamp: str


@dataclass(frozen=True)
class UnstampedDoctrine:
    """A markerless target and the source stamp it could install."""

    available_source_stamp: str


type DoctrineStatus = CurrentDoctrine | StaleDoctrine | LocallyEditedDoctrine | UnstampedDoctrine


class DoctrineBlockError(RuntimeError):
    """The instruction file does not contain exactly one usable block."""


class LocalDoctrineConflictError(RuntimeError):
    """The content no longer agrees with the stamp stored beside it."""


def content_stamp(body: str) -> str:
    """Return the lowercase SHA-256 of the body's exact UTF-8 bytes."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def read_instruction_file(path: Path) -> str:
    """Read one existing UTF-8 instruction file or fail without creating it."""
    if not path.is_file():
        raise DoctrineBlockError(f"{path}: instruction file does not exist")
    return path.read_text(encoding="utf-8")


def parse_doctrine_block(text: str, path: Path) -> StampedDoctrine:
    """Parse exactly one begin/body/end region from an instruction file."""
    begins = list(BEGIN_RE.finditer(text))
    ends = list(END_RE.finditer(text))
    if text.count(BEGIN_TOKEN) != 1 or text.count(END_MARKER) != 1 or len(begins) != 1 or len(ends) != 1:
        raise DoctrineBlockError(f"{path}: expected exactly one well-formed synced doctrine block")

    begin = begins[0]
    end = ends[0]
    if begin.end() >= end.start() or text[begin.end() : begin.end() + 1] != "\n":
        raise DoctrineBlockError(f"{path}: expected exactly one well-formed synced doctrine block")

    body_start = begin.end() + 1
    body = text[body_start : end.start()]
    return StampedDoctrine(
        start=begin.start(),
        end=end.end(),
        body=body,
        source_stamp=begin.group(1),
        rendered=text[begin.start() : end.end()],
    )


def require_unedited(block: StampedDoctrine, path: Path) -> None:
    """Refuse a block whose actual bytes disagree with its stored stamp."""
    actual_stamp = content_stamp(block.body)
    if actual_stamp != block.source_stamp:
        raise LocalDoctrineConflictError(
            f"{path}: doctrine block was edited locally: marker "
            f"source-sha256={block.source_stamp}, content "
            f"source-sha256={actual_stamp}"
        )


def sync_doctrine(source_path: Path, target_path: Path) -> SyncResult:
    """Copy a clean source block over a clean target block, or do no write."""
    source_text = read_instruction_file(source_path)
    source = parse_doctrine_block(source_text, source_path)
    require_unedited(source, source_path)

    target_text = read_instruction_file(target_path)
    target = parse_doctrine_block(target_text, target_path)
    require_unedited(target, target_path)

    if target.rendered == source.rendered:
        return SyncResult(SyncOutcome.UNCHANGED, source.source_stamp)

    updated_text = target_text[: target.start] + source.rendered + target_text[target.end :]
    target_path.write_text(updated_text, encoding="utf-8")
    return SyncResult(SyncOutcome.UPDATED, source.source_stamp)


def check_doctrine(source_path: Path, target_path: Path) -> DoctrineStatus:
    """Classify a target against the source without writing either file."""
    source_text = read_instruction_file(source_path)
    source = parse_doctrine_block(source_text, source_path)
    require_unedited(source, source_path)

    target_text = read_instruction_file(target_path)
    if BEGIN_TOKEN not in target_text and END_MARKER not in target_text:
        return UnstampedDoctrine(source.source_stamp)

    target = parse_doctrine_block(target_text, target_path)
    actual_stamp = content_stamp(target.body)
    if actual_stamp != target.source_stamp:
        return LocallyEditedDoctrine(
            target.source_stamp,
            actual_stamp,
            source.source_stamp,
        )
    if target.source_stamp == source.source_stamp:
        return CurrentDoctrine(source.source_stamp)
    return StaleDoctrine(target.source_stamp, source.source_stamp)


def print_check_result(result: DoctrineStatus, target_path: Path) -> int:
    """Print one actionable status and return its process exit status."""
    if isinstance(result, UnstampedDoctrine):
        print(
            f"UNSTAMPED: {target_path}: target carries no source stamp; "
            f"available source-sha256={result.available_source_stamp}"
        )
        return 1
    if isinstance(result, LocallyEditedDoctrine):
        print(
            f"LOCALLY_EDITED: {target_path}: marker "
            f"source-sha256={result.marker_source_stamp}, content "
            f"source-sha256={result.content_source_stamp}, available "
            f"source-sha256={result.available_source_stamp}"
        )
        return 3
    if isinstance(result, CurrentDoctrine):
        print(
            f"CURRENT: {target_path}: installed source-sha256={result.source_stamp}, "
            f"available source-sha256={result.source_stamp}"
        )
        return 0

    print(
        f"STALE: {target_path}: installed source-sha256={result.installed_source_stamp}, "
        f"available source-sha256={result.available_source_stamp}"
    )
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    """Resolve the template source and target paths at the composition root."""
    args = list(sys.argv[1:] if argv is None else argv)
    check_only = args[:1] == ["--check"]
    if check_only:
        args = args[1:]
    if len(args) > 1:
        print("Usage: sync_doctrine.py [--check] [AGENTS.md]", file=sys.stderr)
        return 64

    source_path = Path(__file__).resolve().parents[1] / "AGENTS.md"
    target_path = Path(args[0]) if args else Path("AGENTS.md")
    try:
        if check_only:
            return print_check_result(check_doctrine(source_path, target_path), target_path)
        result = sync_doctrine(source_path, target_path)
    except DoctrineBlockError as error:
        print(f"ERROR: {error}; no changes written", file=sys.stderr)
        return 2
    except LocalDoctrineConflictError as error:
        print(f"CONFLICT: {error}; no changes written", file=sys.stderr)
        return 3

    print(f"{result.outcome.value}: {target_path}: source-sha256={result.source_stamp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
