"""Command proofs for content-stamped, conflict-safe doctrine synchronization."""

import hashlib
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
SCRIPT = REPO_ROOT / "scripts" / "sync_doctrine.py"
AGENTS = REPO_ROOT / "AGENTS.md"
SOURCE_STAMP = "59e37fd6b3dbab27530822e6956da51bb7ae76b637e3638530f99a8b4db9038d"
SOURCE_BODY = """Four rules. They are one design stance seen four ways: a module means one thing, receives exactly what it needs, in types that cannot lie, and dies rather than guess.

1. **A module means one thing.**
2. **It receives exactly what it needs.**
3. **Its types cannot lie.**
4. **It dies rather than guess.**
"""
SOURCE_BLOCK = f"""<!-- BEGIN SYNCED DOCTRINE; source-sha256={SOURCE_STAMP} -->
{SOURCE_BODY}<!-- END SYNCED DOCTRINE -->"""
STALE_STAMP = "276add6ad3059d4de66db2250890ce61c7cda02a9c4da8622abf51afd2d7054a"
STALE_TARGET = f"""# Local instructions

<!-- BEGIN SYNCED DOCTRINE; source-sha256={STALE_STAMP} -->
Four rules. This fixture is a clean older source.

1. **A module means one thing.**
2. **It receives exactly what it needs.**
3. **Its types cannot lie.**
4. **It dies rather than guess.**
<!-- END SYNCED DOCTRINE -->

Project-local note.
"""
UPDATED_TARGET = f"""# Local instructions

{SOURCE_BLOCK}

Project-local note.
"""
LOCALLY_EDITED_TARGET = f"""# Local instructions

<!-- BEGIN SYNCED DOCTRINE; source-sha256={STALE_STAMP} -->
Four rules. This fixture is a locally edited older source.

1. **A module means one thing.**
2. **It receives exactly what it needs.**
3. **Its types cannot lie.**
4. **It dies rather than guess.**
<!-- END SYNCED DOCTRINE -->

Project-local note.
"""
EDITED_STAMP = "e7107a175f6aa7daf3d1ab9953bdfc5fa01b7bde885324f060bd73951e75abbb"
UNSTAMPED_TARGET = """# Project Instructions

## 2. Design Doctrine

Four rules. This markerless fixture carries no source stamp.
"""
NETWORK_GUARD = """import sys


def deny_network(event, _args):
    if event.startswith("socket."):
        raise RuntimeError("network access denied by acceptance test")


sys.addaudithook(deny_network)
"""


def run_sync(
    target: Path,
    *options: str,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the public command exactly as a user runs it."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *options, str(target)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_repository_artifact_is_exact_and_executable() -> None:
    agents_text = AGENTS.read_text(encoding="utf-8")
    assert hashlib.sha256(SOURCE_BODY.encode("utf-8")).hexdigest() == SOURCE_STAMP
    assert agents_text.count("<!-- BEGIN SYNCED DOCTRINE;") == 1
    assert agents_text.count("<!-- END SYNCED DOCTRINE -->") == 1
    assert SOURCE_BLOCK in agents_text
    assert SCRIPT.stat().st_mode & stat.S_IXUSR

    block_end = agents_text.index("<!-- END SYNCED DOCTRINE -->")
    language_local_bodies = (
        "Before implementing a module, state in one line what it computes",
        "All wiring happens at the composition root",
        "Convert raw input (CLI args, YAML, NetCDF attributes)",
        "Crash early on broken assumptions",
        "Prefer library-specific assertions over manual element-wise checks",
    )
    for body_start in language_local_bodies:
        assert agents_text.index(body_start) > block_end


def test_clean_stamped_block_updates(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text(STALE_TARGET, encoding="utf-8")

    result = run_sync(target)

    assert result.returncode == 0
    assert result.stdout == f"UPDATED: {target}: source-sha256={SOURCE_STAMP}\n"
    assert result.stderr == ""
    assert target.read_text(encoding="utf-8") == UPDATED_TARGET


def test_second_run_is_a_no_op(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text(UPDATED_TARGET, encoding="utf-8")
    before = target.stat()

    result = run_sync(target)

    after = target.stat()
    assert result.returncode == 0
    assert result.stdout == f"UNCHANGED: {target}: source-sha256={SOURCE_STAMP}\n"
    assert result.stderr == ""
    assert target.read_text(encoding="utf-8") == UPDATED_TARGET
    assert after.st_mtime_ns == before.st_mtime_ns


def test_missing_block_fails_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    original = "Project-local instructions only.\n"
    target.write_text(original, encoding="utf-8")

    result = run_sync(target)

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == (
        f"ERROR: {target}: expected exactly one well-formed synced doctrine block; no changes written\n"
    )
    assert target.read_text(encoding="utf-8") == original


def test_locally_edited_block_names_conflict_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text(LOCALLY_EDITED_TARGET, encoding="utf-8")

    result = run_sync(target)

    assert result.returncode == 3
    assert result.stdout == ""
    assert result.stderr == (
        f"CONFLICT: {target}: doctrine block was edited locally: marker "
        f"source-sha256={STALE_STAMP}, content source-sha256={EDITED_STAMP}; "
        "no changes written\n"
    )
    assert target.read_text(encoding="utf-8") == LOCALLY_EDITED_TARGET


def test_check_classifies_current_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text(UPDATED_TARGET, encoding="utf-8")
    before = target.stat()

    result = run_sync(target, "--check")

    after = target.stat()
    assert result.returncode == 0
    assert result.stdout == (
        f"CURRENT: {target}: installed source-sha256={SOURCE_STAMP}, available source-sha256={SOURCE_STAMP}\n"
    )
    assert result.stderr == ""
    assert target.read_text(encoding="utf-8") == UPDATED_TARGET
    assert after.st_mtime_ns == before.st_mtime_ns


def test_check_classifies_stale_and_names_stamp_gap_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text(STALE_TARGET, encoding="utf-8")
    before = target.stat()

    result = run_sync(target, "--check")

    after = target.stat()
    assert result.returncode == 1
    assert result.stdout == (
        f"STALE: {target}: installed source-sha256={STALE_STAMP}, available source-sha256={SOURCE_STAMP}\n"
    )
    assert result.stderr == ""
    assert target.read_text(encoding="utf-8") == STALE_TARGET
    assert after.st_mtime_ns == before.st_mtime_ns


def test_check_classifies_local_edit_and_names_all_stamps_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text(LOCALLY_EDITED_TARGET, encoding="utf-8")
    before = target.stat()

    result = run_sync(target, "--check")

    after = target.stat()
    assert result.returncode == 3
    assert result.stdout == (
        f"LOCALLY_EDITED: {target}: marker source-sha256={STALE_STAMP}, "
        f"content source-sha256={EDITED_STAMP}, available source-sha256={SOURCE_STAMP}\n"
    )
    assert result.stderr == ""
    assert target.read_text(encoding="utf-8") == LOCALLY_EDITED_TARGET
    assert after.st_mtime_ns == before.st_mtime_ns


def test_check_classifies_markerless_target_offline_with_empty_home(tmp_path: Path) -> None:
    target = tmp_path / "metis" / "AGENTS.md"
    target.parent.mkdir()
    target.write_text(UNSTAMPED_TARGET, encoding="utf-8")
    before = target.stat()

    empty_home = tmp_path / "empty-home"
    empty_home.mkdir()
    guard_directory = tmp_path / "network-guard"
    guard_directory.mkdir()
    (guard_directory / "sitecustomize.py").write_text(NETWORK_GUARD, encoding="utf-8")
    environment = os.environ.copy()
    environment["HOME"] = str(empty_home)
    environment["PYTHONPATH"] = str(guard_directory)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"

    result = run_sync(target, "--check", environment=environment)

    after = target.stat()
    assert list(empty_home.iterdir()) == []
    assert result.returncode == 1
    assert result.stdout == (
        f"UNSTAMPED: {target}: target carries no source stamp; available source-sha256={SOURCE_STAMP}\n"
    )
    assert result.stderr == ""
    assert target.read_text(encoding="utf-8") == UNSTAMPED_TARGET
    assert after.st_mtime_ns == before.st_mtime_ns
    assert "installed source-sha256=" not in result.stdout
    diagnostic = result.stdout.split(str(target), maxsplit=1)[1]
    assert "older" not in diagnostic
