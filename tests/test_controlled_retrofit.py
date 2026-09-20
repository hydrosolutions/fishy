"""controlled retrofit proofs : TemporaryRepositories × PinnedCLI → SafetyAssertions."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

PIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PIN_ROOT / "scripts" / "controlled_retrofit.py"
PRIVATE_FLEET_ROOT = "/Users/nico" + "laslazaro/Desktop/work"
EXCLUDED = [
    "camels-us",
    "pydrology",
    "coach",
    "hydrocast",
    "new-gen-2d",
    "stopwatch-deprecated",
    "watershed-retrieve",
    "temenos",
    "RivRetrieve",
]
SOURCE_STAMP = "59e37fd6b3dbab27530822e6956da51bb7ae76b637e3638530f99a8b4db9038d"
SOURCE_BLOCK = f"""<!-- BEGIN SYNCED DOCTRINE; source-sha256={SOURCE_STAMP} -->
Four rules. They are one design stance seen four ways: a module means one thing, receives exactly what it needs, in types that cannot lie, and dies rather than guess.

1. **A module means one thing.**
2. **It receives exactly what it needs.**
3. **Its types cannot lie.**
4. **It dies rather than guess.**
<!-- END SYNCED DOCTRINE -->"""


def git(repository: Path, *arguments: str, environment: dict[str, str] | None = None) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def initialize(repository: Path, files: dict[str, str] | None = None) -> None:
    repository.mkdir(parents=True)
    git(repository, "init", "-b", "main")
    git(repository, "config", "user.name", "Fixture Author")
    git(repository, "config", "user.email", "fixture@example.invalid")
    for name, content in (files or {"AGENTS.md": "local\n"}).items():
        path = repository / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "fixture")


def write_manifest(path: Path, approved: list[str], targets: list[dict[str, object]] | None = None) -> None:
    path.write_text(
        json.dumps(
            {"approved_names": approved, "excluded_names": EXCLUDED, "targets": targets or []},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def cli(
    exec_root: Path,
    command: str,
    manifest: Path,
    snapshot: Path,
    fleet: Path,
    *extra: str,
    environment: dict[str, str] | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    process_environment = os.environ.copy() if environment is None else environment.copy()
    process_environment["GIT_CONFIG_GLOBAL"] = os.devnull
    return subprocess.run(
        [
            sys.executable,
            str(exec_root / "scripts" / "controlled_retrofit.py"),
            command,
            "--manifest",
            str(manifest),
            "--snapshot",
            str(snapshot),
            "--search-root",
            str(fleet),
            *extra,
        ],
        env=process_environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def encoded_digest(entries: list[tuple[bytes, str, int, bytes]]) -> str:
    digest = hashlib.sha256()
    for kind, relative, mode, payload in entries:
        for field in (kind, relative.encode(), oct(mode).encode(), payload):
            digest.update(len(field).to_bytes(8, "big"))
            digest.update(field)
    return digest.hexdigest()


@pytest.fixture
def exec_root(tmp_path: Path) -> Path:
    root = tmp_path / "exec"
    (root / "scripts").mkdir(parents=True)
    for relative in (
        "scripts/controlled_retrofit.py",
        "scripts/inventory_repositories.py",
        "scripts/sync_doctrine.py",
        "AGENTS.md",
    ):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PIN_ROOT / relative, destination)
    return root


def test_executor_tree_imports_only_copied_modules(exec_root: Path) -> None:
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import scripts.inventory_repositories as i, scripts.sync_doctrine as s; "
            "print(i.__file__); print(s.__file__)",
        ],
        cwd=exec_root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert probe.stdout == (
        f"{exec_root / 'scripts/inventory_repositories.py'}\n{exec_root / 'scripts/sync_doctrine.py'}\n"
    )


def test_adjacent_name_snapshot_uses_exact_basename(exec_root: Path, tmp_path: Path) -> None:
    fleet = tmp_path / "fleet"
    initialize(fleet / "stopwatch")
    initialize(fleet / "stopwatch-deprecated")
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    write_manifest(manifest, ["stopwatch"])
    result = cli(exec_root, "snapshot", manifest, snapshot, fleet)
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == f"WROTE: {snapshot.resolve()}\n"
    payload = json.loads(snapshot.read_text())
    assert [(item["name"], item["path"]) for item in payload["repositories"]] == [
        ("stopwatch", str((fleet / "stopwatch").resolve()))
    ]


def test_duplicate_exact_name_refuses_before_output(exec_root: Path, tmp_path: Path) -> None:
    fleet = tmp_path / "fleet"
    initialize(fleet / "one" / "stopwatch")
    initialize(fleet / "two" / "stopwatch")
    initialize(fleet / "stopwatch-deprecated")
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    write_manifest(manifest, ["stopwatch"])
    result = cli(exec_root, "snapshot", manifest, snapshot, fleet)
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == "REFUSED: stopwatch: expected exactly one repository, found 2\n"
    assert not snapshot.exists()


def test_prefix_sibling_is_not_a_match(exec_root: Path, tmp_path: Path) -> None:
    fleet = tmp_path / "fleet"
    initialize(fleet / "pourpoint-web-app")
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    write_manifest(manifest, ["pourpoint"])
    result = cli(exec_root, "snapshot", manifest, snapshot, fleet)
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == "REFUSED: pourpoint: expected exactly one repository, found 0\n"
    assert not snapshot.exists()


def test_exclusion_set_must_be_exact(exec_root: Path, tmp_path: Path) -> None:
    fleet = tmp_path / "fleet"
    initialize(fleet / "safe")
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    write_manifest(manifest, ["safe"])
    payload = json.loads(manifest.read_text())
    payload["excluded_names"] = payload["excluded_names"][:-1]
    manifest.write_text(json.dumps(payload) + "\n")
    result = cli(exec_root, "snapshot", manifest, snapshot, fleet)
    assert result.returncode == 2
    assert result.stderr == "REFUSED: excluded_names is not exactly the required nine-name set\n"
    assert not snapshot.exists()


def test_snapshot_fields_and_digest_changes(exec_root: Path, tmp_path: Path) -> None:
    fleet = tmp_path / "fleet"
    repository = fleet / "anvil"
    initialize(repository, {"AGENTS.md": "tracked\n"})
    (repository / "dirty.txt").write_text("private dirty bytes\n")
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    write_manifest(manifest, ["anvil"])
    first = cli(exec_root, "snapshot", manifest, snapshot, fleet)
    assert first.returncode == 0
    record = json.loads(snapshot.read_text())["repositories"][0]
    assert record["path"] == str(repository.resolve())
    assert record["git_common_directory"] == str((repository / ".git").resolve())
    assert record["branch"] == "main"
    assert len(record["head_sha"]) == 40
    assert record["porcelain_status"] == "?? dirty.txt\n"
    assert record["untracked_files"] == ["dirty.txt"]
    assert all(len(record[key]) == 64 for key in ("tracked_content_sha256", "content_sha256"))
    old = record["tracked_content_sha256"]
    (repository / "AGENTS.md").write_text("changed\n")
    assert cli(exec_root, "snapshot", manifest, snapshot, fleet).returncode == 0
    assert json.loads(snapshot.read_text())["repositories"][0]["tracked_content_sha256"] != old


def test_snapshot_records_fifo_without_reading_and_detects_changes(exec_root: Path, tmp_path: Path) -> None:
    fleet = tmp_path / "fleet"
    repository = fleet / "anvil"
    initialize(repository)
    state = repository / "state"
    state.mkdir()
    fifo = state / "pipeline-completions.fifo"
    os.mkfifo(fifo)
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    write_manifest(manifest, ["anvil"])

    result = cli(exec_root, "snapshot", manifest, snapshot, fleet, timeout=5)
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == f"WROTE: {snapshot.resolve()}\n"
    fifo_record = json.loads(snapshot.read_text())["repositories"][0]
    assert fifo_record["content_sha256"] == encoded_digest(
        [
            (b"F", "AGENTS.md", (repository / "AGENTS.md").lstat().st_mode & 0o7777, b"local\n"),
            (b"D", "state", state.lstat().st_mode & 0o7777, b""),
            (b"P", "state/pipeline-completions.fifo", fifo.lstat().st_mode & 0o7777, b""),
        ]
    )

    fifo_digest = fifo_record["content_sha256"]
    fifo.unlink()
    removed = cli(exec_root, "snapshot", manifest, snapshot, fleet, timeout=5)
    assert (removed.returncode, removed.stdout, removed.stderr) == (0, f"WROTE: {snapshot.resolve()}\n", "")
    removed_record = json.loads(snapshot.read_text())["repositories"][0]
    assert removed_record["content_sha256"] != fifo_digest

    os.mkfifo(fifo)
    restored = cli(exec_root, "snapshot", manifest, snapshot, fleet, timeout=5)
    assert (restored.returncode, restored.stdout, restored.stderr) == (0, f"WROTE: {snapshot.resolve()}\n", "")
    assert json.loads(snapshot.read_text())["repositories"][0]["content_sha256"] == fifo_digest
    fifo.unlink()
    fifo.write_bytes(b"")
    regular = cli(exec_root, "snapshot", manifest, snapshot, fleet, timeout=5)
    assert (regular.returncode, regular.stdout, regular.stderr) == (0, f"WROTE: {snapshot.resolve()}\n", "")
    regular_record = json.loads(snapshot.read_text())["repositories"][0]
    assert regular_record["content_sha256"] != fifo_digest


def test_digest_prunes_exact_names_at_every_depth(exec_root: Path, tmp_path: Path) -> None:
    fleet = tmp_path / "fleet"
    repository = fleet / "anvil"
    initialize(repository)
    for relative in (
        ".pce-cache/x",
        ".uv-cache/x",
        ".venv/x",
        "__pycache__/x",
        "build/x",
        "dist/x",
        "node_modules/x",
        "deep/.git/x",
        "linked/.git",
    ):
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("before")
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    write_manifest(manifest, ["anvil"])
    assert cli(exec_root, "snapshot", manifest, snapshot, fleet).returncode == 0
    before = json.loads(snapshot.read_text())["repositories"][0]["content_sha256"]
    for path in repository.rglob("x"):
        path.write_text("after")
    assert cli(exec_root, "snapshot", manifest, snapshot, fleet).returncode == 0
    after = json.loads(snapshot.read_text())["repositories"][0]["content_sha256"]
    assert after == before


def test_apply_refuses_absent_snapshot_before_fetch(exec_root: Path, tmp_path: Path) -> None:
    fleet = tmp_path / "fleet"
    initialize(fleet / "anvil")
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "absent.json"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    write_manifest(manifest, ["anvil"])
    result = cli(
        exec_root,
        "apply",
        manifest,
        snapshot,
        fleet,
        "--source",
        str(exec_root / "AGENTS.md"),
        "--evidence-dir",
        str(evidence),
    )
    assert result.returncode == 2
    assert result.stderr == "REFUSED: snapshot is absent or unreadable\n"


def test_apply_refuses_stale_time_derived_from_evidence(exec_root: Path, tmp_path: Path) -> None:
    fleet = tmp_path / "fleet"
    initialize(fleet / "anvil")
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    write_manifest(manifest, ["anvil"])
    assert cli(exec_root, "snapshot", manifest, snapshot, fleet).returncode == 0
    future = (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    (evidence / "prior.json").write_text(
        json.dumps({"generated_commit_sha": "a" * 40, "generated_commit_time": future})
    )
    result = cli(
        exec_root,
        "apply",
        manifest,
        snapshot,
        fleet,
        "--source",
        str(exec_root / "AGENTS.md"),
        "--evidence-dir",
        str(evidence),
    )
    assert result.returncode == 2
    assert result.stderr == "REFUSED: snapshot was captured at or after the earliest retrofit commit\n"


def test_apply_refuses_missing_commit_time_derivation(exec_root: Path, tmp_path: Path) -> None:
    fleet = tmp_path / "fleet"
    initialize(fleet / "anvil")
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    write_manifest(manifest, ["anvil"])
    assert cli(exec_root, "snapshot", manifest, snapshot, fleet).returncode == 0
    (evidence / "prior.json").write_text(json.dumps({"generated_commit_sha": "a" * 40}))
    result = cli(
        exec_root,
        "apply",
        manifest,
        snapshot,
        fleet,
        "--source",
        str(exec_root / "AGENTS.md"),
        "--evidence-dir",
        str(evidence),
    )
    assert result.returncode == 2
    assert result.stderr == "REFUSED: could not derive earliest retrofit commit time from evidence\n"


def test_apply_refuses_unreadable_evidence_path(exec_root: Path, tmp_path: Path) -> None:
    fleet = tmp_path / "fleet"
    initialize(fleet / "anvil")
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    write_manifest(manifest, ["anvil"])
    assert cli(exec_root, "snapshot", manifest, snapshot, fleet).returncode == 0
    missing = tmp_path / "missing-evidence"
    result = cli(
        exec_root,
        "apply",
        manifest,
        snapshot,
        fleet,
        "--source",
        str(exec_root / "AGENTS.md"),
        "--evidence-dir",
        str(missing),
    )
    assert result.returncode == 2
    assert result.stderr == "REFUSED: evidence directory is unreadable\n"


def test_markerless_and_merged_types_are_exact(exec_root: Path) -> None:
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; from scripts.controlled_retrofit import insert_markerless, verify_merged_sync; "
            "p=Path('target.md'); p.write_text('# Project\\n\\nLocal gotcha.\\n'); "
            "insert_markerless(Path('AGENTS.md'),p); verify_merged_sync(Path('AGENTS.md'),p); print(p.read_text())",
        ],
        cwd=exec_root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert probe.stdout == "# Project\n\nLocal gotcha.\n\n" + SOURCE_BLOCK + "\n\n"


def test_partial_marker_refuses_without_writing(exec_root: Path) -> None:
    target = exec_root / "partial.md"
    original = "local\n<!-- BEGIN SYNCED DOCTRINE; broken -->\n"
    target.write_text(original)
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; from scripts.controlled_retrofit import insert_markerless; "
            "insert_markerless(Path('AGENTS.md'),Path('partial.md'))",
        ],
        cwd=exec_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 1
    assert target.read_text() == original


def clone_with_origin(tmp_path: Path, name: str, files: dict[str, str]) -> tuple[Path, Path]:
    seed = tmp_path / f"{name}-seed"
    initialize(seed, files)
    bare = tmp_path / f"{name}-origin.git"
    git(seed, "clone", "--bare", str(seed), str(bare))
    fleet = tmp_path / "fleet"
    fleet.mkdir(exist_ok=True)
    live = fleet / name
    subprocess.run(["git", "clone", str(bare), str(live)], check=True, capture_output=True)
    git(live, "config", "user.name", "Fixture Author")
    git(live, "config", "user.email", "fixture@example.invalid")
    return live, bare


def test_direct_main_uses_fetched_detached_worktree(exec_root: Path, tmp_path: Path) -> None:
    live, bare = clone_with_origin(tmp_path, "anvil", {"AGENTS.md": "# Local\n"})
    git(live, "switch", "-c", "feature/live")
    (live / "local.txt").write_text("local only\n")
    git(live, "add", "local.txt")
    git(live, "commit", "-m", "local only")
    local_sha = git(live, "rev-parse", "HEAD").strip()
    (live / "dirty.txt").write_text("dirty\n")
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    write_manifest(
        manifest,
        ["anvil"],
        [{"name": "anvil", "mode": "direct-main", "authority": None, "version_mandate": None}],
    )
    assert cli(exec_root, "snapshot", manifest, snapshot, live.parent).returncode == 0
    before = git(live, "status", "--porcelain=v1", "--untracked-files=all")
    result = cli(
        exec_root,
        "apply",
        manifest,
        snapshot,
        live.parent,
        "--source",
        str(exec_root / "AGENTS.md"),
        "--evidence-dir",
        str(evidence),
    )
    assert result.returncode == 0, result.stderr
    origin_main = git(bare, "rev-parse", "main").strip()
    assert git(bare, "show", "-s", "--format=%s", origin_main).strip() == (
        "chore: sync doctrine from pyplate doctrine-sync milestone 5"
    )
    assert (
        subprocess.run(
            ["git", "-C", str(bare), "merge-base", "--is-ancestor", local_sha, origin_main], check=False
        ).returncode
        != 0
    )
    assert git(live, "rev-parse", "HEAD").strip() == local_sha
    assert git(live, "status", "--porcelain=v1", "--untracked-files=all") == before
    assert git(live, "worktree", "list", "--porcelain").count("worktree ") == 1
    assert git(live, "tag", "--points-at", origin_main) == ""
    assert list(evidence.glob("*.json")) == [evidence / "anvil.json"]
    proof = json.loads((evidence / "anvil.json").read_text())
    assert list(proof) == [
        "name",
        "mode",
        "live_path",
        "worktree_path",
        "live_before",
        "live_after",
        "fetched_origin_main_sha",
        "target_before_sha256",
        "target_after_sha256",
        "generated_commit_sha",
        "generated_commit_time",
        "generated_commit_parent_sha",
        "changed_paths",
        "diff",
        "check_status",
        "first_resync_status",
        "second_resync_status",
        "publication_destination",
    ]
    assert proof["live_before"] == proof["live_after"]
    assert proof["generated_commit_parent_sha"] == proof["fetched_origin_main_sha"]
    assert proof["generated_commit_time"].endswith("Z")
    assert proof["changed_paths"] == ["AGENTS.md"]
    assert proof["check_status"] == "CURRENT"
    assert (proof["first_resync_status"], proof["second_resync_status"]) == ("UNCHANGED", "UNCHANGED")


def test_pull_request_uses_new_branch_and_fake_gh(exec_root: Path, tmp_path: Path) -> None:
    live, bare = clone_with_origin(
        tmp_path,
        "pair",
        {"AGENTS.md": "# Agents\n\nLocal rule.\n", "CLAUDE.md": "# Claude\n\nLocal rule.\n"},
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "gh-argv.json"
    fake_gh = fake_bin / "gh"
    fake_gh.write_text(f"#!/bin/sh\nprintf '%s\\n' gh \"$@\" > {log}\n")
    fake_gh.chmod(fake_gh.stat().st_mode | stat.S_IXUSR)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    body_template = str(tmp_path / "milestone-5-pair-collapse-pr-{name}.md")
    body_file = Path(body_template.replace("{name}", "pair"))
    body_file.write_text("Pinned pull-request body.\n", encoding="utf-8")
    write_manifest(
        manifest,
        ["pair"],
        [{"name": "pair", "mode": "pull-request", "authority": "CLAUDE.md", "version_mandate": None}],
    )
    assert cli(exec_root, "snapshot", manifest, snapshot, live.parent).returncode == 0
    original_main = git(bare, "rev-parse", "main").strip()
    result = cli(
        exec_root,
        "apply",
        manifest,
        snapshot,
        live.parent,
        "--source",
        str(exec_root / "AGENTS.md"),
        "--evidence-dir",
        str(evidence),
        "--pr-body-template",
        body_template,
        environment=environment,
    )
    assert result.returncode == 0, result.stderr
    assert git(bare, "rev-parse", "main").strip() == original_main
    branch = "pyplate-doctrine-sync-milestone-5/pair"
    generated = git(bare, "rev-parse", branch).strip()
    assert generated
    agents = git(bare, "show", f"{generated}:AGENTS.md")
    assert agents.startswith("# Claude\n\nLocal rule.\n\n")
    assert agents.count(SOURCE_BLOCK) == 1
    assert git(bare, "show", f"{generated}:CLAUDE.md") == "See [AGENTS.md](./AGENTS.md).\n"
    assert log.read_text().splitlines() == [
        "gh",
        "pr",
        "create",
        "--head",
        branch,
        "--base",
        "main",
        "--title",
        "chore: sync doctrine from pyplate doctrine-sync milestone 5",
        "--body-file",
        str(body_file.resolve()),
    ]
    assert "--fill" not in log.read_text().splitlines()


def test_snapshot_refuses_incomplete_and_ordered_identity_mismatch(exec_root: Path, tmp_path: Path) -> None:
    fleet = tmp_path / "fleet"
    initialize(fleet / "one")
    initialize(fleet / "two")
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    write_manifest(manifest, ["one", "two"])
    assert cli(exec_root, "snapshot", manifest, snapshot, fleet).returncode == 0
    payload = json.loads(snapshot.read_text())
    payload["repositories"].reverse()
    snapshot.write_text(json.dumps(payload) + "\n")
    result = cli(
        exec_root,
        "apply",
        manifest,
        snapshot,
        fleet,
        "--source",
        str(exec_root / "AGENTS.md"),
        "--evidence-dir",
        str(evidence),
    )
    assert result.returncode == 2
    assert result.stderr == "REFUSED: snapshot repository identities do not match resolved repositories\n"
    del payload["repositories"][0]["content_sha256"]
    snapshot.write_text(json.dumps(payload) + "\n")
    result = cli(
        exec_root,
        "apply",
        manifest,
        snapshot,
        fleet,
        "--source",
        str(exec_root / "AGENTS.md"),
        "--evidence-dir",
        str(evidence),
    )
    assert result.returncode == 2
    assert result.stderr == "REFUSED: snapshot is incomplete\n"


def test_approved_excluded_overlap_refuses(exec_root: Path, tmp_path: Path) -> None:
    fleet = tmp_path / "fleet"
    initialize(fleet / "temenos")
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    write_manifest(manifest, ["temenos"])
    result = cli(exec_root, "snapshot", manifest, snapshot, fleet)
    assert result.returncode == 2
    assert result.stderr == "REFUSED: approved_names overlaps excluded_names\n"
    assert not snapshot.exists()


def write_git_wrapper(path: Path, body: str) -> None:
    path.write_text(f"#!{sys.executable}\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def publication_logging_environment(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    fake_bin = tmp_path / "publication-bin"
    fake_bin.mkdir()
    push_log = tmp_path / "push-invoked"
    gh_log = tmp_path / "gh-invoked"
    real_git = shutil.which("git")
    assert real_git is not None
    write_git_wrapper(
        fake_bin / "git",
        "import pathlib, subprocess, sys\n"
        f"real={real_git!r}; log=pathlib.Path({str(push_log)!r})\n"
        "args=sys.argv[1:]\n"
        "if 'push' in args: log.write_text('push invoked\\n')\n"
        "raise SystemExit(subprocess.run([real,*args]).returncode)\n",
    )
    fake_gh = fake_bin / "gh"
    fake_gh.write_text(f"#!/bin/sh\nprintf 'gh invoked\\n' > {gh_log}\n", encoding="utf-8")
    fake_gh.chmod(fake_gh.stat().st_mode | stat.S_IXUSR)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    return environment, push_log, gh_log


def invoke_pr_body_validation(
    exec_root: Path,
    tmp_path: Path,
    template: str | None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    fleet = tmp_path / "fleet"
    initialize(fleet / "pair", {"AGENTS.md": "Agents\n", "CLAUDE.md": "Claude\n"})
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    write_manifest(
        manifest,
        ["pair"],
        [{"name": "pair", "mode": "pull-request", "authority": "AGENTS.md", "version_mandate": None}],
    )
    assert cli(exec_root, "snapshot", manifest, snapshot, fleet).returncode == 0
    environment, push_log, gh_log = publication_logging_environment(tmp_path)
    extra = ("--pr-body-template", template) if template is not None else ()
    result = cli(
        exec_root,
        "apply",
        manifest,
        snapshot,
        fleet,
        "--source",
        str(exec_root / "AGENTS.md"),
        "--evidence-dir",
        str(evidence),
        *extra,
        environment=environment,
    )
    return result, push_log, gh_log


def assert_no_publication(push_log: Path, gh_log: Path) -> None:
    assert not push_log.exists()
    assert not gh_log.exists()


def test_pull_request_refuses_without_body_template_before_publication(exec_root: Path, tmp_path: Path) -> None:
    result, push_log, gh_log = invoke_pr_body_validation(exec_root, tmp_path, None)
    assert result.returncode == 2
    assert result.stderr == "REFUSED: pull-request targets require --pr-body-template\n"
    assert_no_publication(push_log, gh_log)


def test_pull_request_refuses_missing_body_file_before_publication(exec_root: Path, tmp_path: Path) -> None:
    template = str(tmp_path / "body-{name}.md")
    result, push_log, gh_log = invoke_pr_body_validation(exec_root, tmp_path, template)
    missing = Path(template.replace("{name}", "pair")).resolve()
    assert result.returncode == 2
    assert result.stderr == f"REFUSED: pair: pull-request body file is absent or unreadable: {missing}\n"
    assert_no_publication(push_log, gh_log)


def test_pull_request_refuses_empty_body_file_before_publication(exec_root: Path, tmp_path: Path) -> None:
    template = str(tmp_path / "body-{name}.md")
    empty = Path(template.replace("{name}", "pair"))
    empty.write_bytes(b"")
    result, push_log, gh_log = invoke_pr_body_validation(exec_root, tmp_path, template)
    assert result.returncode == 2
    assert result.stderr == f"REFUSED: pair: pull-request body file is empty: {empty.resolve()}\n"
    assert_no_publication(push_log, gh_log)


def test_pull_request_refuses_body_template_without_placeholder(exec_root: Path, tmp_path: Path) -> None:
    template = str(tmp_path / "body.md")
    Path(template).write_text("Pinned body.\n", encoding="utf-8")
    result, push_log, gh_log = invoke_pr_body_validation(exec_root, tmp_path, template)
    assert result.returncode == 2
    assert result.stderr == "REFUSED: --pr-body-template must contain {name}\n"
    assert_no_publication(push_log, gh_log)


def test_writable_path_sabotage_refuses_without_publication(exec_root: Path, tmp_path: Path) -> None:
    live, bare = clone_with_origin(tmp_path, "anvil", {"AGENTS.md": "# Local\n"})
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    write_manifest(
        manifest,
        ["anvil"],
        [{"name": "anvil", "mode": "direct-main", "authority": None, "version_mandate": None}],
    )
    assert cli(exec_root, "snapshot", manifest, snapshot, live.parent).returncode == 0
    original_main = git(bare, "rev-parse", "main").strip()
    before = git(live, "status", "--porcelain=v1", "--untracked-files=all")
    fake_bin = tmp_path / "sabotage-bin"
    fake_bin.mkdir()
    real_git = shutil.which("git")
    assert real_git is not None
    write_git_wrapper(
        fake_bin / "git",
        "import pathlib, subprocess, sys\n"
        f"real={real_git!r}\n"
        "args=sys.argv[1:]\n"
        "if 'status' in args and '--untracked-files=all' in args and '-C' in args:\n"
        " p=pathlib.Path(args[args.index('-C')+1]);\n"
        " if p.name.startswith('retrofit-'): (p/'README.md').write_text('sabotage\\n')\n"
        "raise SystemExit(subprocess.run([real,*args]).returncode)\n",
    )
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    result = cli(
        exec_root,
        "apply",
        manifest,
        snapshot,
        live.parent,
        "--source",
        str(exec_root / "AGENTS.md"),
        "--evidence-dir",
        str(evidence),
        environment=environment,
    )
    assert result.returncode == 2
    assert result.stderr == "REFUSED: generated diff contains a forbidden path\n"
    assert git(bare, "rev-parse", "main").strip() == original_main
    assert git(live, "status", "--porcelain=v1", "--untracked-files=all") == before
    assert not list(evidence.iterdir())


def test_remote_advance_refuses_before_publication(exec_root: Path, tmp_path: Path) -> None:
    live, bare = clone_with_origin(tmp_path, "anvil", {"AGENTS.md": "# Local\n"})
    advance = tmp_path / "advance"
    subprocess.run(["git", "clone", str(bare), str(advance)], check=True, capture_output=True)
    git(advance, "config", "user.name", "Fixture Author")
    git(advance, "config", "user.email", "fixture@example.invalid")
    (advance / "advance.txt").write_text("advance\n")
    git(advance, "add", "advance.txt")
    git(advance, "commit", "-m", "advance")
    advance_sha = git(advance, "rev-parse", "HEAD").strip()
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    write_manifest(
        manifest,
        ["anvil"],
        [{"name": "anvil", "mode": "direct-main", "authority": None, "version_mandate": None}],
    )
    assert cli(exec_root, "snapshot", manifest, snapshot, live.parent).returncode == 0
    fake_bin = tmp_path / "advance-bin"
    fake_bin.mkdir()
    count = tmp_path / "fetch-count"
    real_git = shutil.which("git")
    assert real_git is not None
    write_git_wrapper(
        fake_bin / "git",
        "import pathlib, subprocess, sys\n"
        f"real={real_git!r}; count=pathlib.Path({str(count)!r}); advance={str(advance)!r}\n"
        "args=sys.argv[1:]\n"
        "if args[-3:]==['fetch','origin','main']:\n"
        " n=int(count.read_text())+1 if count.exists() else 1; count.write_text(str(n))\n"
        " if n==2: subprocess.run([real,'-C',advance,'push','origin','HEAD:refs/heads/main'],check=True)\n"
        "raise SystemExit(subprocess.run([real,*args]).returncode)\n",
    )
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    result = cli(
        exec_root,
        "apply",
        manifest,
        snapshot,
        live.parent,
        "--source",
        str(exec_root / "AGENTS.md"),
        "--evidence-dir",
        str(evidence),
        environment=environment,
    )
    assert result.returncode == 2
    assert result.stderr == "REFUSED: origin/main advanced before publication\n"
    assert git(bare, "rev-parse", "main").strip() == advance_sha
    assert not list(evidence.iterdir())


def invoke_churning_retrofit(
    exec_root: Path,
    tmp_path: Path,
    mode: str,
    churn: str,
) -> tuple[subprocess.CompletedProcess[str], Path, Path, Path, Path, str, str]:
    files = (
        {"AGENTS.md": "# Local\n"}
        if mode == "direct-main"
        else {"AGENTS.md": "# Agents\n\nLocal rule.\n", "CLAUDE.md": "# Claude\n\nLocal rule.\n"}
    )
    live, bare = clone_with_origin(tmp_path, "anvil", files)
    manifest, snapshot = tmp_path / "manifest.json", tmp_path / "snapshot.json"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    write_manifest(
        manifest,
        ["anvil"],
        [
            {
                "name": "anvil",
                "mode": mode,
                "authority": None if mode == "direct-main" else "AGENTS.md",
                "version_mandate": None,
            }
        ],
    )
    assert cli(exec_root, "snapshot", manifest, snapshot, live.parent).returncode == 0
    original_main = git(bare, "rev-parse", "main").strip()
    fake_bin = tmp_path / "churn-bin"
    fake_bin.mkdir()
    event_log = tmp_path / "publication-events"
    gh_log = tmp_path / "gh-invoked"
    real_git = shutil.which("git")
    assert real_git is not None
    churn_statement = (
        "(live/'build.log').write_text('untracked churn\\n')"
        if churn == "untracked"
        else "(live/'AGENTS.md').write_text((live/'AGENTS.md').read_text()+'tracked churn\\n')"
    )
    write_git_wrapper(
        fake_bin / "git",
        "import pathlib, subprocess, sys\n"
        f"real={real_git!r}; live=pathlib.Path({str(live)!r}); log=pathlib.Path({str(event_log)!r})\n"
        "args=sys.argv[1:]\n"
        "result=subprocess.run([real,*args])\n"
        f"if result.returncode==0 and 'commit' in args: {churn_statement}; "
        "log.write_text('churn\\n')\n"
        "if result.returncode==0 and 'push' in args: log.write_text(log.read_text()+'push\\n')\n"
        "raise SystemExit(result.returncode)\n",
    )
    fake_gh = fake_bin / "gh"
    fake_gh.write_text(f"#!/bin/sh\nprintf 'gh invoked\n' > {gh_log}\n", encoding="utf-8")
    fake_gh.chmod(fake_gh.stat().st_mode | stat.S_IXUSR)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    extra: tuple[str, ...] = ()
    publication_ref = "main"
    if mode == "pull-request":
        body_template = str(tmp_path / "body-{name}.md")
        Path(body_template.replace("{name}", "anvil")).write_text("Pinned body.\n", encoding="utf-8")
        extra = ("--pr-body-template", body_template)
        publication_ref = "pyplate-doctrine-sync-milestone-5/anvil"
    result = cli(
        exec_root,
        "apply",
        manifest,
        snapshot,
        live.parent,
        "--source",
        str(exec_root / "AGENTS.md"),
        "--evidence-dir",
        str(evidence),
        *extra,
        environment=environment,
    )
    return result, bare, evidence, event_log, gh_log, original_main, publication_ref


@pytest.mark.parametrize("mode", ["direct-main", "pull-request"])
def test_untracked_churn_does_not_refuse_after_publication(exec_root: Path, tmp_path: Path, mode: str) -> None:
    result, bare, evidence, event_log, gh_log, original_main, publication_ref = invoke_churning_retrofit(
        exec_root, tmp_path, mode, "untracked"
    )

    assert result.returncode == 0, result.stderr
    assert "live checkout changed during retrofit" not in result.stderr
    assert event_log.read_text() == "churn\npush\n"
    assert git(bare, "rev-parse", publication_ref).strip() != original_main
    assert gh_log.exists() is (mode == "pull-request")
    proof = json.loads((evidence / "anvil.json").read_text())
    record_keys = [
        "name",
        "path",
        "git_common_directory",
        "branch",
        "head_sha",
        "porcelain_status",
        "untracked_files",
        "tracked_content_sha256",
        "content_sha256",
    ]
    assert list(proof["live_before"]) == record_keys
    assert list(proof["live_after"]) == record_keys
    assert proof["live_before"]["branch"] == proof["live_after"]["branch"]
    assert proof["live_before"]["head_sha"] == proof["live_after"]["head_sha"]
    assert proof["live_before"]["tracked_content_sha256"] == proof["live_after"]["tracked_content_sha256"]
    assert proof["live_before"]["porcelain_status"] != proof["live_after"]["porcelain_status"]
    assert proof["live_before"]["content_sha256"] != proof["live_after"]["content_sha256"]
    assert proof["live_after"]["untracked_files"] == ["build.log"]


@pytest.mark.parametrize("mode", ["direct-main", "pull-request"])
def test_tracked_churn_still_refuses_after_publication(exec_root: Path, tmp_path: Path, mode: str) -> None:
    result, bare, _, event_log, gh_log, original_main, publication_ref = invoke_churning_retrofit(
        exec_root, tmp_path, mode, "tracked"
    )

    assert result.returncode == 2
    assert result.stderr == "REFUSED: anvil: live checkout changed during retrofit\n"
    assert event_log.read_text() == "churn\npush\n"
    assert git(bare, "rev-parse", publication_ref).strip() != original_main
    assert gh_log.exists() is (mode == "pull-request")


def test_source_fence() -> None:
    source = SCRIPT.read_text()
    assert SCRIPT.stat().st_mode & stat.S_IXUSR
    assert source.count("repository.worktree.name == approved_name") == 1
    for forbidden in (
        "startswith(",
        "endswith(",
        "fnmatch",
        "glob(",
        "rglob(",
        "re.compile",
        PRIVATE_FLEET_ROOT,
        "stopwatch-deprecated",
        "temenos",
        "RivRetrieve",
    ):
        assert forbidden not in source
    assert "discover_repositories" in source
    assert "classify_layout" in source
    assert "check_doctrine" in source
    assert "sync_doctrine" in source
