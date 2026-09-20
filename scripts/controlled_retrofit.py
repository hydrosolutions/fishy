#!/usr/bin/env python3
"""Build a snapshot-gated doctrine retrofit without writing live checkouts.

controlled retrofit : RetrofitRequest × RepositoryInventory × PreRetrofitSnapshot → RetrofitEvidence
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import NewType, Protocol, cast

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.inventory_repositories import (
    CLAUDE_POINTER,
    GitRepository,
    InstructionLayout,
    SearchRoot,
    classify_layout,
    discover_repositories,
)
from scripts.sync_doctrine import (
    BEGIN_TOKEN,
    END_MARKER,
    CurrentDoctrine,
    SyncOutcome,
    check_doctrine,
    parse_doctrine_block,
    read_instruction_file,
    sync_doctrine,
)

RepositoryName = NewType("RepositoryName", str)
SOURCE_STAMP = "59e37fd6b3dbab27530822e6956da51bb7ae76b637e3638530f99a8b4db9038d"
COMMIT_SUBJECT = "chore: sync doctrine from pyplate doctrine-sync milestone 5"
EXPECTED_EXCLUSIONS_SHA256 = "f7d9b4ab25c2db91eaa81c155debc92a1604cc92cb8da6ff54adfcfdb2af9590"
EXCLUDED_DIRECTORY_NAMES = frozenset(
    {".git", ".pce-cache", ".uv-cache", ".venv", "__pycache__", "build", "dist", "node_modules"}
)


class RetrofitRefusalError(RuntimeError):
    """A controlled precondition failed."""


class LandingMode(Enum):
    """An authorized publication route."""

    DIRECT_MAIN = "direct-main"
    PULL_REQUEST = "pull-request"


class PairAuthority(Enum):
    """The selected file in a substantive pair."""

    AGENTS = "AGENTS.md"
    CLAUDE = "CLAUDE.md"


@dataclass(frozen=True)
class Target:
    """One explicitly authorized target."""

    name: RepositoryName
    mode: LandingMode
    authority: PairAuthority | None
    version_mandate: str | None


@dataclass(frozen=True)
class RetrofitRequest:
    """Parsed manifest authority."""

    approved_names: tuple[RepositoryName, ...]
    excluded_names: frozenset[RepositoryName]
    targets: tuple[Target, ...]


@dataclass(frozen=True)
class SnapshotRecord:
    """One live checkout identity and observed state."""

    name: str
    path: str
    git_common_directory: str
    branch: str | None
    head_sha: str
    porcelain_status: str
    untracked_files: tuple[str, ...]
    tracked_content_sha256: str
    content_sha256: str


@dataclass(frozen=True)
class PreRetrofitSnapshot:
    """The state captured before any retrofit commit."""

    captured_at: datetime
    repositories: tuple[SnapshotRecord, ...]


def run_git(repository: Path, *arguments: str) -> str:
    """Run one read-only Git query and return stdout."""
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def parse_utc(value: object) -> datetime:
    """Parse the only timestamp representation accepted at the boundary."""
    if not isinstance(value, str) or value[-1:] != "Z":
        raise RetrofitRefusalError("snapshot captured_at is not aware UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise RetrofitRefusalError("snapshot captured_at is not aware UTC") from error
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        raise RetrofitRefusalError("snapshot captured_at is not aware UTC")
    return parsed


def exclusions_digest(names: frozenset[RepositoryName]) -> str:
    """Hash one canonical set without embedding its members in source."""
    return hashlib.sha256("\0".join(sorted(names)).encode()).hexdigest()


def parse_manifest(path: Path) -> RetrofitRequest:
    """Parse raw manifest JSON once into domain carriers."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RetrofitRefusalError(f"manifest is unreadable: {path}") from error
    if not isinstance(raw, dict) or set(raw) != {"approved_names", "excluded_names", "targets"}:
        raise RetrofitRefusalError("manifest keys do not match the required schema")
    approved_raw = raw["approved_names"]
    excluded_raw = raw["excluded_names"]
    targets_raw = raw["targets"]
    if not all(isinstance(item, list) for item in (approved_raw, excluded_raw, targets_raw)):
        raise RetrofitRefusalError("manifest lists have invalid types")
    if not all(isinstance(name, str) and name for name in approved_raw + excluded_raw):
        raise RetrofitRefusalError("repository names must be non-empty strings")
    approved = tuple(RepositoryName(name) for name in approved_raw)
    excluded = frozenset(RepositoryName(name) for name in excluded_raw)
    if len(approved) != len(set(approved)):
        raise RetrofitRefusalError("approved_names contains a duplicate")
    if len(excluded) != len(excluded_raw) or exclusions_digest(excluded) != EXPECTED_EXCLUSIONS_SHA256:
        raise RetrofitRefusalError("excluded_names is not exactly the required nine-name set")
    if set(approved) & excluded:
        raise RetrofitRefusalError("approved_names overlaps excluded_names")
    targets: list[Target] = []
    for item in targets_raw:
        if not isinstance(item, dict) or set(item) != {"name", "mode", "authority", "version_mandate"}:
            raise RetrofitRefusalError("target keys do not match the required schema")
        try:
            name = RepositoryName(item["name"])
            mode = LandingMode(item["mode"])
            authority = PairAuthority(item["authority"]) if item["authority"] is not None else None
        except (TypeError, ValueError) as error:
            raise RetrofitRefusalError("target contains an invalid enum or name") from error
        mandate = item["version_mandate"]
        if name not in approved:
            raise RetrofitRefusalError("target is absent from approved_names")
        if mandate is not None and (not isinstance(mandate, str) or not mandate):
            raise RetrofitRefusalError("version_mandate must be null or a non-empty string")
        if (mode is LandingMode.DIRECT_MAIN) != (authority is None):
            raise RetrofitRefusalError("target authority is incompatible with its mode")
        targets.append(Target(name, mode, authority, mandate))
    if len({target.name for target in targets}) != len(targets):
        raise RetrofitRefusalError("targets contains a duplicate")
    return RetrofitRequest(approved, excluded, tuple(targets))


def resolve_approved(repositories: tuple[GitRepository, ...], request: RetrofitRequest) -> tuple[GitRepository, ...]:
    """Resolve every manifest name by exact basename over merged discovery."""
    resolved: list[GitRepository] = []
    for approved_name in request.approved_names:
        matches = tuple(repository for repository in repositories if repository.worktree.name == approved_name)
        if len(matches) != 1:
            raise RetrofitRefusalError(f"{approved_name}: expected exactly one repository, found {len(matches)}")
        resolved.append(matches[0])
    if {RepositoryName(item.worktree.name) for item in resolved} & request.excluded_names:
        raise RetrofitRefusalError("resolved approved repositories overlap excluded_names")
    return tuple(resolved)


class ByteDigest(Protocol):
    """The narrow hash authority needed by length-prefix encoding."""

    def update(self, value: bytes, /) -> object:
        """Consume bytes."""


def add_field(digest: ByteDigest, value: bytes) -> None:
    """Add one unambiguous length-prefixed field to a digest."""
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def content_digest(root: Path, tracked_only: bool) -> str:
    """Hash selected working-tree bytes while pruning the pinned set at every depth."""
    selected: set[str] | None = None
    if tracked_only:
        output = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        ).stdout
        selected = {value.decode() for value in output.split(b"\0") if value}

    def refuse_unreadable(error: OSError) -> None:
        unreadable = Path(error.filename) if error.filename is not None else root
        try:
            relative = unreadable.relative_to(root).as_posix()
        except ValueError:
            relative = str(unreadable)
        raise RetrofitRefusalError(f"unreadable working-tree entry: {relative}") from error

    paths: list[Path] = []
    for directory, directory_names, file_names in os.walk(
        root, topdown=True, onerror=refuse_unreadable, followlinks=False
    ):
        directory_names[:] = sorted(name for name in directory_names if name not in EXCLUDED_DIRECTORY_NAMES)
        base = Path(directory)
        included_files = [name for name in file_names if name not in EXCLUDED_DIRECTORY_NAMES]
        for name in sorted(directory_names + included_files):
            relative = (base / name).relative_to(root)
            if selected is None or relative.as_posix() in selected:
                paths.append(relative)
    digest = hashlib.sha256()
    for relative in sorted(paths, key=lambda item: item.as_posix()):
        path = root / relative
        try:
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                kind, payload = b"L", os.readlink(path).encode()
            elif stat.S_ISDIR(metadata.st_mode):
                kind, payload = b"D", b""
            elif stat.S_ISREG(metadata.st_mode):
                kind, payload = b"F", path.read_bytes()
            elif stat.S_ISFIFO(metadata.st_mode):
                kind, payload = b"P", b""
            elif stat.S_ISSOCK(metadata.st_mode):
                kind, payload = b"S", b""
            elif stat.S_ISBLK(metadata.st_mode):
                kind, payload = b"B", b""
            elif stat.S_ISCHR(metadata.st_mode):
                kind, payload = b"C", b""
            else:
                raise RetrofitRefusalError(f"unsupported working-tree entry: {relative.as_posix()}")
        except OSError as error:
            raise RetrofitRefusalError(f"unreadable working-tree entry: {relative.as_posix()}") from error
        for field in (kind, relative.as_posix().encode(), oct(metadata.st_mode & 0o7777).encode(), payload):
            add_field(digest, field)
    return digest.hexdigest()


def snapshot_record(name: RepositoryName, repository: GitRepository) -> SnapshotRecord:
    """Capture one checkout without writing it."""
    branch_result = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "-C",
            str(repository.worktree),
            "symbolic-ref",
            "--quiet",
            "--short",
            "HEAD",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    untracked = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "-C",
            str(repository.worktree),
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        check=True,
        capture_output=True,
    ).stdout
    return SnapshotRecord(
        name=name,
        path=str(repository.worktree.resolve()),
        git_common_directory=str(repository.common_directory.resolve()),
        branch=branch_result.stdout.strip() if branch_result.returncode == 0 else None,
        head_sha=run_git(repository.worktree, "rev-parse", "HEAD").strip(),
        porcelain_status=run_git(repository.worktree, "status", "--porcelain=v1", "--untracked-files=all"),
        untracked_files=tuple(sorted(value.decode() for value in untracked.split(b"\0") if value)),
        tracked_content_sha256=content_digest(repository.worktree, True),
        content_sha256=content_digest(repository.worktree, False),
    )


def stable_triple(record: SnapshotRecord) -> tuple[str | None, str, str]:
    """Return the branch, commit, and tracked-content identity of one snapshot."""
    return record.branch, record.head_sha, record.tracked_content_sha256


def write_snapshot(path: Path, resolved: tuple[GitRepository, ...], request: RetrofitRequest) -> None:
    """Write the deterministic private snapshot."""
    captured = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    records = []
    for name, repository in zip(request.approved_names, resolved, strict=True):
        record = snapshot_record(name, repository)
        records.append({**asdict(record), "untracked_files": list(record.untracked_files)})
    path.write_text(
        json.dumps({"schema_version": 1, "captured_at": captured, "repositories": records}, indent=2) + "\n",
        encoding="utf-8",
    )


def read_snapshot(path: Path) -> PreRetrofitSnapshot:
    """Read a complete snapshot or refuse."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RetrofitRefusalError("snapshot is absent or unreadable") from error
    if not isinstance(raw, dict) or set(raw) != {"schema_version", "captured_at", "repositories"}:
        raise RetrofitRefusalError("snapshot is incomplete")
    if raw["schema_version"] != 1 or not isinstance(raw["repositories"], list):
        raise RetrofitRefusalError("snapshot is incomplete")
    expected = set(SnapshotRecord.__dataclass_fields__)
    records: list[SnapshotRecord] = []
    for unknown_item in raw["repositories"]:
        if not isinstance(unknown_item, dict) or set(unknown_item) != expected:
            raise RetrofitRefusalError("snapshot is incomplete")
        item = cast(dict[str, object], unknown_item)
        strings = (
            "name",
            "path",
            "git_common_directory",
            "head_sha",
            "porcelain_status",
            "tracked_content_sha256",
            "content_sha256",
        )
        if not all(isinstance(item[key], str) for key in strings):
            raise RetrofitRefusalError("snapshot is incomplete")
        branch = item["branch"]
        untracked = item["untracked_files"]
        if (branch is not None and not isinstance(branch, str)) or not isinstance(untracked, list):
            raise RetrofitRefusalError("snapshot is incomplete")
        if not all(isinstance(value, str) for value in untracked):
            raise RetrofitRefusalError("snapshot is incomplete")
        records.append(
            SnapshotRecord(
                name=cast(str, item["name"]),
                path=cast(str, item["path"]),
                git_common_directory=cast(str, item["git_common_directory"]),
                branch=branch,
                head_sha=cast(str, item["head_sha"]),
                porcelain_status=cast(str, item["porcelain_status"]),
                untracked_files=tuple(cast(list[str], untracked)),
                tracked_content_sha256=cast(str, item["tracked_content_sha256"]),
                content_sha256=cast(str, item["content_sha256"]),
            )
        )
    return PreRetrofitSnapshot(parse_utc(raw["captured_at"]), tuple(records))


def derive_earliest_retrofit_time(evidence_directory: Path) -> datetime | None:
    """Derive temporal authority from all recorded commits, never a CLI flag."""
    if not evidence_directory.is_dir() or not os.access(evidence_directory, os.R_OK | os.X_OK):
        raise RetrofitRefusalError("evidence directory is unreadable")
    times: list[datetime] = []
    for path in sorted(item for item in evidence_directory.iterdir() if item.suffix == ".json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RetrofitRefusalError("could not derive earliest retrofit commit time from evidence") from error
        if not isinstance(item, dict):
            raise RetrofitRefusalError("could not derive earliest retrofit commit time from evidence")
        if "generated_commit_sha" in item:
            if "generated_commit_time" not in item:
                raise RetrofitRefusalError("could not derive earliest retrofit commit time from evidence")
            times.append(parse_utc(item["generated_commit_time"]))
    return min(times) if times else None


def require_fresh_snapshot(
    snapshot: PreRetrofitSnapshot,
    resolved: tuple[GitRepository, ...],
    request: RetrofitRequest,
    earliest_commit_time: datetime | None,
) -> None:
    """Refuse stale identities, tracked state, or capture time before any fetch."""
    identities = tuple((item.name, item.path, item.git_common_directory) for item in snapshot.repositories)
    expected = tuple(
        (str(name), str(repository.worktree.resolve()), str(repository.common_directory.resolve()))
        for name, repository in zip(request.approved_names, resolved, strict=True)
    )
    if identities != expected:
        raise RetrofitRefusalError("snapshot repository identities do not match resolved repositories")
    if earliest_commit_time is not None and snapshot.captured_at >= earliest_commit_time:
        raise RetrofitRefusalError("snapshot was captured at or after the earliest retrofit commit")
    for stored, name, repository in zip(snapshot.repositories, request.approved_names, resolved, strict=True):
        live = snapshot_record(name, repository)
        if (stored.branch, stored.head_sha, stored.tracked_content_sha256) != (
            live.branch,
            live.head_sha,
            live.tracked_content_sha256,
        ):
            raise RetrofitRefusalError(f"{name}: live tracked state differs from the pre-retrofit snapshot")


def insert_markerless(source_path: Path, target_path: Path) -> None:
    """Append exactly one clean source block to a markerless instruction file."""
    source = parse_doctrine_block(read_instruction_file(source_path), source_path)
    target = read_instruction_file(target_path)
    if BEGIN_TOKEN in target or END_MARKER in target:
        raise RetrofitRefusalError(f"{target_path}: target is not markerless")
    separator = "\n" if target[-1:] == "\n" else "\n\n"
    target_path.write_text(target + separator + source.rendered + "\n", encoding="utf-8")


def verify_merged_sync(source_path: Path, target_path: Path) -> None:
    """Pin the merged result types and exact source stamp."""
    if check_doctrine(source_path, target_path) != CurrentDoctrine(source_stamp=SOURCE_STAMP):
        raise RetrofitRefusalError("merged check did not return the pinned CurrentDoctrine")
    before = (target_path.read_bytes(), target_path.stat().st_mtime_ns)
    for _ in range(2):
        result = sync_doctrine(source_path, target_path)
        if result.outcome is not SyncOutcome.UNCHANGED or result.source_stamp != SOURCE_STAMP:
            raise RetrofitRefusalError("merged resync did not return the pinned SyncResult")
    if (target_path.read_bytes(), target_path.stat().st_mtime_ns) != before:
        raise RetrofitRefusalError("UNCHANGED resync changed bytes or mtime")


def delete_mandate(text: str, mandate: str | None) -> str:
    """Delete only one exact authorized substring."""
    if mandate is None:
        return text
    if text.count(mandate) != 1:
        raise RetrofitRefusalError("version mandate does not occur exactly once")
    return text.replace(mandate, "", 1)


def resolve_pr_body_files(targets: tuple[Target, ...], template: str | None) -> dict[RepositoryName, Path]:
    """Resolve readable, non-empty PR bodies for every pull-request target."""
    if template is not None and "{name}" not in template:
        raise RetrofitRefusalError("--pr-body-template must contain {name}")
    pull_request_targets = tuple(target for target in targets if target.mode is LandingMode.PULL_REQUEST)
    if pull_request_targets and template is None:
        raise RetrofitRefusalError("pull-request targets require --pr-body-template")
    rendered_template = cast(str, template)
    resolved: dict[RepositoryName, Path] = {}
    for target in pull_request_targets:
        path = Path(rendered_template.replace("{name}", str(target.name))).resolve()
        try:
            body = path.read_bytes()
        except OSError as error:
            raise RetrofitRefusalError(
                f"{target.name}: pull-request body file is absent or unreadable: {path}"
            ) from error
        if not body:
            raise RetrofitRefusalError(f"{target.name}: pull-request body file is empty: {path}")
        resolved[target.name] = path
    return resolved


def transform(source_path: Path, worktree: Path, target: Target) -> None:
    """Perform only the mode-bounded instruction transformation."""
    common = Path(run_git(worktree, "rev-parse", "--git-common-dir").strip())
    if not common.is_absolute():
        common = worktree / common
    repository = GitRepository(worktree, common.resolve())
    layout = classify_layout(repository)
    agents = worktree / "AGENTS.md"
    claude = worktree / "CLAUDE.md"
    if target.mode is LandingMode.DIRECT_MAIN:
        if layout is not InstructionLayout.AGENTS_ONLY_MARKERLESS:
            raise RetrofitRefusalError("direct-main target does not have markerless AGENTS.md-only layout")
        agents.write_text(delete_mandate(read_instruction_file(agents), target.version_mandate), encoding="utf-8")
    else:
        if layout is not InstructionLayout.SUBSTANTIVE_DUPLICATED_PAIR or target.authority is None:
            raise RetrofitRefusalError("pull-request target does not have an authorized substantive pair")
        selected = agents if target.authority is PairAuthority.AGENTS else claude
        agents.write_text(delete_mandate(read_instruction_file(selected), target.version_mandate), encoding="utf-8")
        claude.write_text(CLAUDE_POINTER, encoding="utf-8")
    insert_markerless(source_path, agents)


def apply_target(
    source_path: Path,
    evidence_directory: Path,
    repository: GitRepository,
    target: Target,
    stored: SnapshotRecord,
    pr_body_file: Path | None,
) -> tuple[str, tuple[str, ...]]:
    """Generate, verify, publish, and clean one isolated target."""
    if target.mode is LandingMode.PULL_REQUEST and pr_body_file is None:
        raise RetrofitRefusalError("pull-request targets require --pr-body-template")
    live_before = snapshot_record(target.name, repository)
    if stable_triple(stored) != stable_triple(live_before):
        raise RetrofitRefusalError(f"{target.name}: live tracked state differs from the pre-retrofit snapshot")
    run_git(repository.worktree, "fetch", "origin", "main")
    base = run_git(repository.worktree, "rev-parse", "refs/remotes/origin/main").strip()
    temporary = Path(tempfile.mkdtemp(prefix=f"retrofit-{target.name}-", dir=repository.worktree.parent))
    temporary.rmdir()
    added = False
    try:
        run_git(repository.worktree, "worktree", "add", "--detach", str(temporary), base)
        added = True
        if run_git(temporary, "rev-parse", "HEAD").strip() != base:
            raise RetrofitRefusalError("temporary worktree did not start at fetched origin/main")
        target_before = content_digest(temporary, False)
        transform(source_path, temporary, target)
        target_after = content_digest(temporary, False)
        status = run_git(temporary, "status", "--porcelain=v1", "--untracked-files=all")
        paths = tuple(line[3:] for line in status.splitlines())
        allowed = {"AGENTS.md"} if target.mode is LandingMode.DIRECT_MAIN else {"AGENTS.md", "CLAUDE.md"}
        if not paths or not set(paths) <= allowed:
            raise RetrofitRefusalError("generated diff contains a forbidden path")
        run_git(temporary, "add", "--", *paths)
        run_git(temporary, "commit", "-m", COMMIT_SUBJECT)
        generated = run_git(temporary, "rev-parse", "HEAD").strip()
        if run_git(temporary, "rev-parse", "HEAD^").strip() != base:
            raise RetrofitRefusalError("generated commit parent is not fetched origin/main")
        verify_merged_sync(source_path, temporary / "AGENTS.md")
        run_git(repository.worktree, "fetch", "origin", "main")
        if run_git(repository.worktree, "rev-parse", "refs/remotes/origin/main").strip() != base:
            raise RetrofitRefusalError("origin/main advanced before publication")
        branch = f"pyplate-doctrine-sync-milestone-5/{target.name}"
        if target.mode is LandingMode.PULL_REQUEST:
            active = subprocess.run(
                ["git", "-C", str(temporary), "ls-remote", "--exit-code", "--heads", "origin", f"refs/heads/{branch}"],
                check=False,
                capture_output=True,
                text=True,
            )
            if active.returncode != 2:
                raise RetrofitRefusalError("pull-request destination branch already exists")
        raw_commit_time = run_git(temporary, "show", "-s", "--format=%cI", generated).strip()
        commit_time = (
            datetime.fromisoformat(raw_commit_time).astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        )
        publication = "refs/heads/main" if target.mode is LandingMode.DIRECT_MAIN else f"refs/heads/{branch}"
        evidence = {
            "name": str(target.name),
            "mode": target.mode.value,
            "live_path": str(repository.worktree),
            "worktree_path": str(temporary),
            "live_before": asdict(live_before),
            "live_after": asdict(snapshot_record(target.name, repository)),
            "fetched_origin_main_sha": base,
            "target_before_sha256": target_before,
            "target_after_sha256": target_after,
            "generated_commit_sha": generated,
            "generated_commit_time": commit_time,
            "generated_commit_parent_sha": run_git(temporary, "rev-parse", "HEAD^").strip(),
            "changed_paths": list(paths),
            "diff": run_git(temporary, "show", "--format=", "--binary", "HEAD"),
            "check_status": "CURRENT",
            "first_resync_status": "UNCHANGED",
            "second_resync_status": "UNCHANGED",
            "publication_destination": publication,
        }
        (evidence_directory / f"{target.name}.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        if target.mode is LandingMode.DIRECT_MAIN:
            run_git(temporary, "push", "origin", f"{generated}:refs/heads/main")
        else:
            run_git(temporary, "push", "origin", f"{generated}:refs/heads/{branch}")
            body_file = cast(Path, pr_body_file)
            subprocess.run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--head",
                    branch,
                    "--base",
                    "main",
                    "--title",
                    COMMIT_SUBJECT,
                    "--body-file",
                    str(body_file),
                ],
                cwd=temporary,
                check=True,
            )
        return base, paths
    finally:
        if added:
            run_git(repository.worktree, "worktree", "remove", "--force", str(temporary))
            run_git(repository.worktree, "worktree", "prune")
        elif temporary.exists():
            shutil.rmtree(temporary)
        if stable_triple(snapshot_record(target.name, repository)) != stable_triple(live_before):
            raise RetrofitRefusalError(f"{target.name}: live checkout changed during retrofit")


def parser() -> argparse.ArgumentParser:
    """Construct the explicit, path-only CLI."""
    root = argparse.ArgumentParser(add_help=False)
    commands = root.add_subparsers(dest="command", required=True)
    for command in ("snapshot", "apply"):
        child = commands.add_parser(command, add_help=False)
        child.add_argument("--manifest", required=True)
        child.add_argument("--snapshot", required=True)
        child.add_argument("--search-root", action="append", required=True)
        if command == "apply":
            child.add_argument("--source", required=True)
            child.add_argument("--evidence-dir", required=True)
            child.add_argument("--pr-body-template")
    return root


def main(argv: list[str] | None = None) -> int:
    """Resolve all raw paths and grant only the selected command authority."""
    try:
        try:
            arguments = parser().parse_args(argv)
        except SystemExit:
            return 64
        manifest_path = Path(arguments.manifest).resolve(strict=True)
        snapshot_path = Path(arguments.snapshot).resolve()
        roots = tuple(SearchRoot(Path(item).resolve(strict=True)) for item in arguments.search_root)
        request = parse_manifest(manifest_path)
        resolved = resolve_approved(discover_repositories(roots), request)
        if arguments.command == "snapshot":
            write_snapshot(snapshot_path, resolved, request)
            print(f"WROTE: {snapshot_path}")
            return 0
        pr_body_files = resolve_pr_body_files(request.targets, arguments.pr_body_template)
        evidence_directory = Path(arguments.evidence_dir).resolve()
        earliest = derive_earliest_retrofit_time(evidence_directory)
        snapshot = read_snapshot(snapshot_path)
        require_fresh_snapshot(snapshot, resolved, request, earliest)
        source_path = Path(arguments.source).resolve(strict=True)
        by_name = {item.name: item for item in snapshot.repositories}
        for target in request.targets:
            repository = next(item for item in resolved if item.worktree.name == target.name)
            parent, paths = apply_target(
                source_path,
                evidence_directory,
                repository,
                target,
                by_name[target.name],
                pr_body_files.get(target.name),
            )
            print(
                f"VERIFIED: {target.name}: parent={parent}; paths={','.join(paths)}; "
                "check=CURRENT; resync=UNCHANGED,UNCHANGED"
            )
        print(f"COMPLETE: {len(request.targets)} repositories")
        return 0
    except RetrofitRefusalError as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
