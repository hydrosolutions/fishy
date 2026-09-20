#!/usr/bin/env python3
"""Discover repository layouts and apply doctrine operations to eligible targets.

fleet doctrine application : FleetOperation × StampedDoctrine × SearchRoots → ordered set of RepositoryResult
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import NewType

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.sync_doctrine import (
    BEGIN_TOKEN,
    END_MARKER,
    CurrentDoctrine,
    DoctrineBlockError,
    LocalDoctrineConflictError,
    LocallyEditedDoctrine,
    StaleDoctrine,
    SyncOutcome,
    UnstampedDoctrine,
    check_doctrine,
    parse_doctrine_block,
    sync_doctrine,
)

CLAUDE_POINTER = "See [AGENTS.md](./AGENTS.md).\n"
PRUNED_DIRECTORY_NAMES = frozenset({".git", ".pce-cache", ".uv-cache", ".venv", "node_modules"})

SearchRoot = NewType("SearchRoot", Path)


class InstructionLayout(Enum):
    """The exhaustive instruction-file layouts known before doctrine checking."""

    EXACTLY_ONE_WELL_FORMED_DOCTRINE_BLOCK = "exactly-one-well-formed-doctrine-block"
    AGENTS_ONLY_MARKERLESS = "AGENTS.md-only markerless"
    SUBSTANTIVE_DUPLICATED_PAIR = "substantive duplicated AGENTS.md/CLAUDE.md pair"
    CLAUDE_ONLY = "CLAUDE.md-only"
    NO_INSTRUCTION_FILE = "no instruction file"
    MALFORMED_OR_AMBIGUOUS = "malformed/ambiguous"


class FleetStatus(Enum):
    """Every successful, non-clean, unsupported, or failed fleet result."""

    UPDATED = "UPDATED"
    UNCHANGED = "UNCHANGED"
    CURRENT = "CURRENT"
    STALE = "STALE"
    LOCALLY_EDITED = "LOCALLY_EDITED"
    UNSTAMPED = "UNSTAMPED"
    MISSING = "MISSING"
    MALFORMED = "MALFORMED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED_LAYOUT = "UNSUPPORTED_LAYOUT"
    CONFLICT = "CONFLICT"
    ERROR = "ERROR"


class FleetOperation(Enum):
    """The two explicit doctrine operations accepted at the composition root."""

    CHECK = "check"
    SYNC = "sync"


@dataclass(frozen=True)
class GitRepository:
    """One selected worktree and the common directory identifying its repository."""

    worktree: Path
    common_directory: Path


@dataclass(frozen=True)
class InventoryRecord:
    """One repository's resolved path and instruction layout."""

    repository: Path
    layout: InstructionLayout


@dataclass(frozen=True)
class RepositoryResult:
    """One isolated repository's layout, operation status, and actionable detail."""

    repository: Path
    layout: InstructionLayout | None
    status: FleetStatus
    detail: str


def _git_path(candidate: Path, argument: str) -> Path:
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(candidate), "rev-parse", argument],
        check=True,
        capture_output=True,
        text=True,
    )
    path = Path(result.stdout.strip())
    if not path.is_absolute():
        path = candidate / path
    return path.resolve()


def discover_repositories(search_roots: tuple[SearchRoot, ...]) -> tuple[GitRepository, ...]:
    """Discover worktrees, then retain one path for each Git common directory."""
    candidates: set[Path] = set()
    for search_root in search_roots:
        for directory, directory_names, file_names in os.walk(search_root):
            if ".git" in directory_names or ".git" in file_names:
                candidates.add(Path(directory).resolve())
                directory_names.clear()
            else:
                directory_names[:] = [name for name in directory_names if name not in PRUNED_DIRECTORY_NAMES]

    repositories_by_common_directory: dict[Path, GitRepository] = {}
    for candidate in sorted(candidates):
        worktree = _git_path(candidate, "--show-toplevel")
        common_directory = _git_path(candidate, "--git-common-dir")
        repository = GitRepository(worktree, common_directory)
        selected = repositories_by_common_directory.get(common_directory)
        repository_rank = (repository.worktree != common_directory.parent, repository.worktree)
        selected_rank = (
            (selected.worktree != common_directory.parent, selected.worktree) if selected is not None else None
        )
        if selected_rank is None or repository_rank < selected_rank:
            repositories_by_common_directory[common_directory] = repository

    return tuple(sorted(repositories_by_common_directory.values(), key=lambda item: item.worktree))


def _normalized_substantive_body(text: str) -> str:
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def classify_layout(repository: GitRepository) -> InstructionLayout:
    """Classify instruction-file layout without determining doctrine status."""
    agents_path = repository.worktree / "AGENTS.md"
    claude_path = repository.worktree / "CLAUDE.md"
    agents_exists = agents_path.is_file()
    claude_exists = claude_path.is_file()

    if not agents_exists and not claude_exists:
        return InstructionLayout.NO_INSTRUCTION_FILE
    if not agents_exists:
        return InstructionLayout.CLAUDE_ONLY

    agents_text = agents_path.read_text(encoding="utf-8")
    claude_text = claude_path.read_text(encoding="utf-8") if claude_exists else None
    if claude_text is not None and claude_text != CLAUDE_POINTER:
        if claude_text.strip().startswith("See [AGENTS.md]("):
            return InstructionLayout.MALFORMED_OR_AMBIGUOUS
        agents_body = _normalized_substantive_body(agents_text)
        claude_body = _normalized_substantive_body(claude_text)
        carries_marker = any(
            marker in text for marker in (BEGIN_TOKEN, END_MARKER) for text in (agents_text, claude_text)
        )
        if not carries_marker and agents_body and claude_body:
            return InstructionLayout.SUBSTANTIVE_DUPLICATED_PAIR
        return InstructionLayout.MALFORMED_OR_AMBIGUOUS

    carries_begin = BEGIN_TOKEN in agents_text
    carries_end = END_MARKER in agents_text
    if not carries_begin and not carries_end:
        return InstructionLayout.AGENTS_ONLY_MARKERLESS
    try:
        parse_doctrine_block(agents_text, agents_path)
    except DoctrineBlockError:
        return InstructionLayout.MALFORMED_OR_AMBIGUOUS
    return InstructionLayout.EXACTLY_ONE_WELL_FORMED_DOCTRINE_BLOCK


def inventory_records(repositories: tuple[GitRepository, ...]) -> tuple[InventoryRecord, ...]:
    """Classify discovered repositories in deterministic path order."""
    return tuple(InventoryRecord(repository.worktree, classify_layout(repository)) for repository in repositories)


def render_inventory(records: tuple[InventoryRecord, ...]) -> str:
    """Render deterministic, human-inspectable layout-only inventory JSON."""
    payload = {
        "repositories": [{"repository": str(record.repository), "layout": record.layout.value} for record in records]
    }
    return json.dumps(payload, indent=2) + "\n"


def _checked_status(source_path: Path, target_path: Path) -> tuple[FleetStatus, str]:
    doctrine_status = check_doctrine(source_path, target_path)
    if isinstance(doctrine_status, CurrentDoctrine):
        return (
            FleetStatus.CURRENT,
            f"installed source-sha256={doctrine_status.source_stamp}; "
            f"available source-sha256={doctrine_status.source_stamp}",
        )
    if isinstance(doctrine_status, StaleDoctrine):
        return (
            FleetStatus.STALE,
            f"installed source-sha256={doctrine_status.installed_source_stamp}; "
            f"available source-sha256={doctrine_status.available_source_stamp}",
        )
    if isinstance(doctrine_status, LocallyEditedDoctrine):
        return (
            FleetStatus.LOCALLY_EDITED,
            f"marker source-sha256={doctrine_status.marker_source_stamp}; "
            f"content source-sha256={doctrine_status.content_source_stamp}; "
            f"available source-sha256={doctrine_status.available_source_stamp}",
        )
    if isinstance(doctrine_status, UnstampedDoctrine):
        return (
            FleetStatus.UNSTAMPED,
            f"target carries no source stamp; available source-sha256={doctrine_status.available_source_stamp}",
        )
    raise AssertionError(f"unhandled doctrine status: {doctrine_status!r}")


def _non_writing_result(repository: GitRepository, layout: InstructionLayout) -> RepositoryResult:
    """Return the explicit refusal for one repository that is not write-eligible."""
    if layout is InstructionLayout.AGENTS_ONLY_MARKERLESS:
        status, detail = FleetStatus.UNSTAMPED, "AGENTS.md has no content-stamped doctrine block"
    elif layout is InstructionLayout.NO_INSTRUCTION_FILE:
        status, detail = FleetStatus.MISSING, "repository has no root instruction file"
    elif layout is InstructionLayout.CLAUDE_ONLY:
        status, detail = FleetStatus.UNSUPPORTED_LAYOUT, "CLAUDE.md-only layout is outside doctrine-sync scope"
    elif layout is InstructionLayout.SUBSTANTIVE_DUPLICATED_PAIR:
        status, detail = FleetStatus.AMBIGUOUS, "AGENTS.md and CLAUDE.md are both substantive"
    else:
        agents_text = (repository.worktree / "AGENTS.md").read_text(encoding="utf-8")
        if BEGIN_TOKEN in agents_text or END_MARKER in agents_text:
            status = FleetStatus.MALFORMED
            detail = "AGENTS.md has a partial, duplicate, or malformed doctrine marker"
        else:
            status = FleetStatus.AMBIGUOUS
            detail = "instruction files do not select one safe AGENTS.md target"
    return RepositoryResult(repository.worktree, layout, status, detail)


def _check_one(repository: GitRepository, source_path: Path) -> RepositoryResult:
    layout = classify_layout(repository)
    if layout in {
        InstructionLayout.EXACTLY_ONE_WELL_FORMED_DOCTRINE_BLOCK,
        InstructionLayout.AGENTS_ONLY_MARKERLESS,
    }:
        status, detail = _checked_status(source_path, repository.worktree / "AGENTS.md")
        return RepositoryResult(repository.worktree, layout, status, detail)
    result = _non_writing_result(repository, layout)
    if result.status is FleetStatus.UNSUPPORTED_LAYOUT:
        return RepositoryResult(
            result.repository,
            result.layout,
            result.status,
            "CLAUDE.md-only layout is outside doctrine-check scope",
        )
    return result


def _sync_one(repository: GitRepository, source_path: Path) -> RepositoryResult:
    layout = classify_layout(repository)
    if layout is not InstructionLayout.EXACTLY_ONE_WELL_FORMED_DOCTRINE_BLOCK:
        return _non_writing_result(repository, layout)
    sync_result = sync_doctrine(source_path, repository.worktree / "AGENTS.md")
    status = FleetStatus.UPDATED if sync_result.outcome is SyncOutcome.UPDATED else FleetStatus.UNCHANGED
    return RepositoryResult(
        repository.worktree,
        layout,
        status,
        f"source-sha256={sync_result.source_stamp}",
    )


def apply_inventory_records(
    repositories: tuple[GitRepository, ...], source_path: Path, operation: FleetOperation
) -> tuple[RepositoryResult, ...]:
    """Apply one operation with exactly one per-repository failure-isolation point."""
    results: list[RepositoryResult] = []
    for repository in repositories:
        try:
            if operation is FleetOperation.CHECK:
                result = _check_one(repository, source_path)
            else:
                result = _sync_one(repository, source_path)
        except LocalDoctrineConflictError as error:
            result = RepositoryResult(
                repository.worktree,
                InstructionLayout.EXACTLY_ONE_WELL_FORMED_DOCTRINE_BLOCK,
                FleetStatus.CONFLICT,
                str(error),
            )
        except Exception as error:
            result = RepositoryResult(
                repository.worktree,
                None,
                FleetStatus.ERROR,
                f"{type(error).__name__}: {error}",
            )
        results.append(result)
    return tuple(results)


def check_inventory_records(repositories: tuple[GitRepository, ...], source_path: Path) -> tuple[RepositoryResult, ...]:
    """Check every repository through the shared application path."""
    return apply_inventory_records(repositories, source_path, FleetOperation.CHECK)


def sync_inventory_records(repositories: tuple[GitRepository, ...], source_path: Path) -> tuple[RepositoryResult, ...]:
    """Sync every write-eligible repository through the shared application path."""
    return apply_inventory_records(repositories, source_path, FleetOperation.SYNC)


def render_checked_inventory(records: tuple[RepositoryResult, ...]) -> str:
    """Render the inventory enriched with deterministic doctrine-operation results."""
    payload = {
        "repositories": [
            {
                "repository": str(record.repository),
                "layout": record.layout.value if record.layout is not None else None,
                "status": record.status.value,
                "detail": record.detail,
            }
            for record in records
        ]
    }
    return json.dumps(payload, indent=2) + "\n"


def _search_roots(arguments: list[str]) -> tuple[SearchRoot, ...]:
    resolved_roots: list[SearchRoot] = []
    for argument in arguments:
        path = Path(argument).resolve(strict=True)
        if not path.is_dir():
            raise NotADirectoryError(path)
        resolved_roots.append(SearchRoot(path))
    return tuple(resolved_roots)


def main(argv: list[str] | None = None) -> int:
    """Parse search roots and grant inventory-write authority at the composition root."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    operation = None
    if arguments[:1] == ["--check"]:
        operation = FleetOperation.CHECK
        arguments = arguments[1:]
    elif arguments[:1] == ["--sync"]:
        operation = FleetOperation.SYNC
        arguments = arguments[1:]
    if not arguments or arguments[0].startswith("-"):
        print("Usage: inventory_repositories.py [--check | --sync] SEARCH_ROOT [SEARCH_ROOT ...]", file=sys.stderr)
        return 64

    repositories = discover_repositories(_search_roots(arguments))
    inventory_path = Path(__file__).resolve().parents[1] / "scratchpad" / "repository-inventory.json"
    if operation is None:
        inventory_path.write_text(render_inventory(inventory_records(repositories)), encoding="utf-8")
        print(f"WROTE: {inventory_path}")
        return 0

    source_path = Path(__file__).resolve().parents[1] / "AGENTS.md"
    records = apply_inventory_records(repositories, source_path, operation)
    inventory_path.write_text(render_checked_inventory(records), encoding="utf-8")
    for record in records:
        print(f"{record.status.value}: {record.repository}: {record.detail}")
    print(f"WROTE: {inventory_path}")
    clean_statuses = {
        FleetOperation.CHECK: {FleetStatus.CURRENT},
        FleetOperation.SYNC: {FleetStatus.UPDATED, FleetStatus.UNCHANGED},
    }
    return 0 if all(record.status in clean_statuses[operation] for record in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
