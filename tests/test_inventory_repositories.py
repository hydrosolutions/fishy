"""Repository inventory : SearchRoots → ReadOnlyOrderedInstructionLayouts."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_SCRIPT = PROJECT_ROOT / "scripts" / "inventory_repositories.py"
sys.path.insert(0, str(PROJECT_ROOT))
inventory = importlib.import_module("scripts.inventory_repositories")
STAMP = "cfd29db69c9f21a2dec10da834c6e34e166af6ad66b8ce407b255c54258641ab"
STAMPED_AGENTS = f"""# Stamped

<!-- BEGIN SYNCED DOCTRINE; source-sha256={STAMP} -->
fixture doctrine
<!-- END SYNCED DOCTRINE -->
"""
CLAUDE_POINTER = "See [AGENTS.md](./AGENTS.md).\n"
MARKERLESS_AGENTS = "# Markerless\n\nLocal instructions.\n"
DUPLICATED_AGENTS = "# Project instructions\n\nShared substantive rule.\n"
DUPLICATED_CLAUDE = "# Claude instructions\n\nShared substantive rule.\n"
CLAUDE_ONLY = "# Claude only\n\nLegacy instructions.\n"
MALFORMED_AGENTS = f"""# Broken

<!-- BEGIN SYNCED DOCTRINE; source-sha256={"0" * 64} -->
body
"""
LINKED_AGENTS = "# Linked\n\nLocal instructions.\n"
OLD_STAMP = "c418b17d169850dfba092e0f396e860bcfbfd4c74d5ef08966e5135ca7bc5b1f"
EDITED_STAMP = "361605c98baa9b7f326d5314170c29d539f0aef3ddc37dc46501734f19718922"
STALE_AGENTS = f"""# Stale

<!-- BEGIN SYNCED DOCTRINE; source-sha256={OLD_STAMP} -->
old doctrine
<!-- END SYNCED DOCTRINE -->
"""
EDITED_AGENTS = f"""# Edited

<!-- BEGIN SYNCED DOCTRINE; source-sha256={STAMP} -->
edited doctrine
<!-- END SYNCED DOCTRINE -->
"""
UPDATED_AGENTS = STAMPED_AGENTS.replace("# Stamped", "# Stale")


def run_git(repository: Path, *arguments: str) -> None:
    """Run one local-only fixture Git command."""
    subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def initialize_repository(repository: Path, files: dict[str, str]) -> None:
    """Create one Git worktree with the exact authored instruction bytes."""
    repository.mkdir(parents=True)
    run_git(repository, "init", "-q")
    for relative_path, content in files.items():
        path = repository / relative_path
        path.write_text(content, encoding="utf-8")


def filesystem_snapshot(repository: Path) -> dict[str, tuple[str, bytes]]:
    """Capture every directory, regular-file byte string, and symlink target."""
    snapshot: dict[str, tuple[str, bytes]] = {}
    for path in sorted(repository.rglob("*")):
        relative_path = path.relative_to(repository).as_posix()
        if path.is_symlink():
            snapshot[relative_path] = ("symlink", os.readlink(path).encode())
        elif path.is_file():
            snapshot[relative_path] = ("file", path.read_bytes())
        elif path.is_dir():
            snapshot[relative_path] = ("directory", b"")
    return snapshot


def test_discovery_classifies_two_owner_shapes_without_mutating_any_repository(tmp_path: Path) -> None:
    owners = tmp_path / "owners"
    alice = owners / "alice"
    hydrosolutions = owners / "hydrosolutions"
    stamped = alice / "stamped"
    markerless = alice / "markerless"
    duplicated = hydrosolutions / "duplicated"
    claude_only = hydrosolutions / "claude-only"
    no_instruction = hydrosolutions / "none"
    malformed = hydrosolutions / "malformed"
    linked_source = alice / "linked-source"
    linked_copy = alice / "aaa-linked-copy"

    initialize_repository(stamped, {"AGENTS.md": STAMPED_AGENTS, "CLAUDE.md": CLAUDE_POINTER})
    initialize_repository(markerless, {"AGENTS.md": MARKERLESS_AGENTS})
    initialize_repository(
        duplicated,
        {"AGENTS.md": DUPLICATED_AGENTS, "CLAUDE.md": DUPLICATED_CLAUDE},
    )
    initialize_repository(claude_only, {"CLAUDE.md": CLAUDE_ONLY})
    initialize_repository(no_instruction, {})
    initialize_repository(malformed, {"AGENTS.md": MALFORMED_AGENTS})
    initialize_repository(linked_source, {"AGENTS.md": LINKED_AGENTS})
    run_git(linked_source, "add", "AGENTS.md")
    run_git(
        linked_source,
        "-c",
        "user.name=InventoryTest",
        "-c",
        "user.email=inventory@example.invalid",
        "commit",
        "-q",
        "-m",
        "initial",
    )
    linked_copy.parent.mkdir(parents=True, exist_ok=True)
    run_git(linked_source, "worktree", "add", "-q", str(linked_copy))

    scanned_worktrees = (
        stamped,
        markerless,
        duplicated,
        claude_only,
        no_instruction,
        malformed,
        linked_source,
        linked_copy,
    )
    before = {path: filesystem_snapshot(path) for path in scanned_worktrees}

    repositories = inventory.discover_repositories(
        (inventory.SearchRoot(alice.resolve()), inventory.SearchRoot(hydrosolutions.resolve()))
    )
    records = inventory.inventory_records(repositories)
    rendered = inventory.render_inventory(records)

    after = {path: filesystem_snapshot(path) for path in scanned_worktrees}
    assert after == before
    assert len(scanned_worktrees) == 8
    assert len(records) == 7
    assert linked_copy.is_dir()
    assert linked_copy.resolve() < linked_source.resolve()
    assert {record.repository.parent.name for record in records} == {"alice", "hydrosolutions"}
    assert all(not (path / "repository-inventory.json").exists() for path in scanned_worktrees)

    expected = f"""{{
  "repositories": [
    {{
      "repository": "{linked_source.resolve()}",
      "layout": "AGENTS.md-only markerless"
    }},
    {{
      "repository": "{markerless.resolve()}",
      "layout": "AGENTS.md-only markerless"
    }},
    {{
      "repository": "{stamped.resolve()}",
      "layout": "exactly-one-well-formed-doctrine-block"
    }},
    {{
      "repository": "{claude_only.resolve()}",
      "layout": "CLAUDE.md-only"
    }},
    {{
      "repository": "{duplicated.resolve()}",
      "layout": "substantive duplicated AGENTS.md/CLAUDE.md pair"
    }},
    {{
      "repository": "{malformed.resolve()}",
      "layout": "malformed/ambiguous"
    }},
    {{
      "repository": "{no_instruction.resolve()}",
      "layout": "no instruction file"
    }}
  ]
}}
"""
    assert rendered == expected


def test_check_reports_every_status_and_preserves_every_repository_byte(tmp_path: Path) -> None:
    fleet = tmp_path / "fleet"
    current = fleet / "current"
    stale = fleet / "stale"
    edited = fleet / "edited"
    unstamped = fleet / "unstamped"
    missing = fleet / "missing"
    malformed = fleet / "malformed"
    ambiguous = fleet / "ambiguous"
    unsupported = fleet / "unsupported"
    initialize_repository(current, {"AGENTS.md": STAMPED_AGENTS})
    initialize_repository(stale, {"AGENTS.md": STALE_AGENTS})
    initialize_repository(edited, {"AGENTS.md": EDITED_AGENTS})
    initialize_repository(unstamped, {"AGENTS.md": MARKERLESS_AGENTS})
    initialize_repository(missing, {})
    initialize_repository(malformed, {"AGENTS.md": MALFORMED_AGENTS})
    initialize_repository(
        ambiguous,
        {"AGENTS.md": DUPLICATED_AGENTS, "CLAUDE.md": DUPLICATED_CLAUDE},
    )
    initialize_repository(unsupported, {"CLAUDE.md": CLAUDE_ONLY})
    paths = (current, stale, edited, unstamped, missing, malformed, ambiguous, unsupported)
    repositories = tuple(inventory.GitRepository(path.resolve(), path.resolve() / ".git") for path in paths)
    before = {path: filesystem_snapshot(path) for path in paths}

    records = inventory.check_inventory_records(repositories, current / "AGENTS.md")
    rendered = inventory.render_checked_inventory(records)

    assert {path: filesystem_snapshot(path) for path in paths} == before
    assert [record.status for record in records] == [
        inventory.FleetStatus.CURRENT,
        inventory.FleetStatus.STALE,
        inventory.FleetStatus.LOCALLY_EDITED,
        inventory.FleetStatus.UNSTAMPED,
        inventory.FleetStatus.MISSING,
        inventory.FleetStatus.MALFORMED,
        inventory.FleetStatus.AMBIGUOUS,
        inventory.FleetStatus.UNSUPPORTED_LAYOUT,
    ]
    expected = {
        "repositories": [
            {
                "repository": str(current.resolve()),
                "layout": "exactly-one-well-formed-doctrine-block",
                "status": "CURRENT",
                "detail": f"installed source-sha256={STAMP}; available source-sha256={STAMP}",
            },
            {
                "repository": str(stale.resolve()),
                "layout": "exactly-one-well-formed-doctrine-block",
                "status": "STALE",
                "detail": f"installed source-sha256={OLD_STAMP}; available source-sha256={STAMP}",
            },
            {
                "repository": str(edited.resolve()),
                "layout": "exactly-one-well-formed-doctrine-block",
                "status": "LOCALLY_EDITED",
                "detail": (
                    f"marker source-sha256={STAMP}; content source-sha256={EDITED_STAMP}; "
                    f"available source-sha256={STAMP}"
                ),
            },
            {
                "repository": str(unstamped.resolve()),
                "layout": "AGENTS.md-only markerless",
                "status": "UNSTAMPED",
                "detail": f"target carries no source stamp; available source-sha256={STAMP}",
            },
            {
                "repository": str(missing.resolve()),
                "layout": "no instruction file",
                "status": "MISSING",
                "detail": "repository has no root instruction file",
            },
            {
                "repository": str(malformed.resolve()),
                "layout": "malformed/ambiguous",
                "status": "MALFORMED",
                "detail": "AGENTS.md has a partial, duplicate, or malformed doctrine marker",
            },
            {
                "repository": str(ambiguous.resolve()),
                "layout": "substantive duplicated AGENTS.md/CLAUDE.md pair",
                "status": "AMBIGUOUS",
                "detail": "AGENTS.md and CLAUDE.md are both substantive",
            },
            {
                "repository": str(unsupported.resolve()),
                "layout": "CLAUDE.md-only",
                "status": "UNSUPPORTED_LAYOUT",
                "detail": "CLAUDE.md-only layout is outside doctrine-check scope",
            },
        ]
    }
    assert rendered == json.dumps(expected, indent=2) + "\n"


def test_check_isolates_one_repository_failure_and_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    broken = inventory.GitRepository(tmp_path / "broken", tmp_path / "broken" / ".git")
    current = tmp_path / "current"
    initialize_repository(current, {"AGENTS.md": STAMPED_AGENTS})
    healthy = inventory.GitRepository(current.resolve(), current.resolve() / ".git")
    original = inventory._check_one

    def fail_one(repository: object, source_path: Path) -> object:
        if repository == broken:
            raise OSError("fixture failure")
        assert isinstance(repository, inventory.GitRepository)
        return original(repository, source_path)

    monkeypatch.setattr(inventory, "_check_one", fail_one)
    records = inventory.check_inventory_records((broken, healthy), current / "AGENTS.md")

    assert records[0] == inventory.RepositoryResult(
        broken.worktree,
        None,
        inventory.FleetStatus.ERROR,
        "OSError: fixture failure",
    )
    assert records[1].status is inventory.FleetStatus.CURRENT


def test_sync_writes_only_clean_stamped_blocks_and_second_run_writes_nothing(tmp_path: Path) -> None:
    owners = tmp_path / "fixture-owners"
    alice = owners / "alice"
    hydrosolutions = owners / "hydrosolutions"
    stale = alice / "stale"
    current = hydrosolutions / "current"
    edited = alice / "edited"
    unstamped = alice / "unstamped"
    missing = hydrosolutions / "missing"
    malformed = hydrosolutions / "malformed"
    ambiguous = hydrosolutions / "ambiguous"
    unsupported = hydrosolutions / "unsupported"
    outside_fixture_fleet = tmp_path / "outside-fixture-fleet"
    initialize_repository(stale, {"AGENTS.md": STALE_AGENTS})
    initialize_repository(current, {"AGENTS.md": STAMPED_AGENTS})
    initialize_repository(edited, {"AGENTS.md": EDITED_AGENTS})
    initialize_repository(unstamped, {"AGENTS.md": MARKERLESS_AGENTS})
    initialize_repository(missing, {})
    initialize_repository(malformed, {"AGENTS.md": MALFORMED_AGENTS})
    initialize_repository(
        ambiguous,
        {"AGENTS.md": DUPLICATED_AGENTS, "CLAUDE.md": DUPLICATED_CLAUDE},
    )
    initialize_repository(unsupported, {"CLAUDE.md": CLAUDE_ONLY})
    initialize_repository(outside_fixture_fleet, {"AGENTS.md": STALE_AGENTS})
    paths = (stale, current, edited, unstamped, missing, malformed, ambiguous, unsupported)
    repositories = tuple(inventory.GitRepository(path.resolve(), path.resolve() / ".git") for path in paths)
    before = {path: filesystem_snapshot(path) for path in (*paths, outside_fixture_fleet)}

    first_records = inventory.sync_inventory_records(repositories, current / "AGENTS.md")
    after_first = {path: filesystem_snapshot(path) for path in (*paths, outside_fixture_fleet)}

    assert (stale / "AGENTS.md").read_text(encoding="utf-8") == UPDATED_AGENTS
    assert after_first[stale] != before[stale]
    for path in (*paths[1:], outside_fixture_fleet):
        assert after_first[path] == before[path]
    assert [record.status for record in first_records] == [
        inventory.FleetStatus.UPDATED,
        inventory.FleetStatus.UNCHANGED,
        inventory.FleetStatus.CONFLICT,
        inventory.FleetStatus.UNSTAMPED,
        inventory.FleetStatus.MISSING,
        inventory.FleetStatus.MALFORMED,
        inventory.FleetStatus.AMBIGUOUS,
        inventory.FleetStatus.UNSUPPORTED_LAYOUT,
    ]
    assert [record.detail for record in first_records] == [
        f"source-sha256={STAMP}",
        f"source-sha256={STAMP}",
        (
            f"{edited.resolve() / 'AGENTS.md'}: doctrine block was edited locally: marker "
            f"source-sha256={STAMP}, content source-sha256={EDITED_STAMP}"
        ),
        "AGENTS.md has no content-stamped doctrine block",
        "repository has no root instruction file",
        "AGENTS.md has a partial, duplicate, or malformed doctrine marker",
        "AGENTS.md and CLAUDE.md are both substantive",
        "CLAUDE.md-only layout is outside doctrine-sync scope",
    ]

    before_second = {path: filesystem_snapshot(path) for path in (*paths, outside_fixture_fleet)}
    second_records = inventory.sync_inventory_records(repositories, current / "AGENTS.md")
    after_second = {path: filesystem_snapshot(path) for path in (*paths, outside_fixture_fleet)}

    assert after_second == before_second
    assert [record.status for record in second_records] == [
        inventory.FleetStatus.UNCHANGED,
        inventory.FleetStatus.UNCHANGED,
        inventory.FleetStatus.CONFLICT,
        inventory.FleetStatus.UNSTAMPED,
        inventory.FleetStatus.MISSING,
        inventory.FleetStatus.MALFORMED,
        inventory.FleetStatus.AMBIGUOUS,
        inventory.FleetStatus.UNSUPPORTED_LAYOUT,
    ]
    assert {record.repository.parent.name for record in second_records} == {"alice", "hydrosolutions"}


def test_sync_isolates_one_repository_failure_and_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    broken = inventory.GitRepository(tmp_path / "broken", tmp_path / "broken" / ".git")
    current = tmp_path / "current"
    initialize_repository(current, {"AGENTS.md": STAMPED_AGENTS})
    healthy = inventory.GitRepository(current.resolve(), current.resolve() / ".git")
    original = inventory._sync_one

    def fail_one(repository: object, source_path: Path) -> object:
        if repository == broken:
            raise OSError("fixture failure")
        assert isinstance(repository, inventory.GitRepository)
        return original(repository, source_path)

    monkeypatch.setattr(inventory, "_sync_one", fail_one)
    records = inventory.sync_inventory_records((broken, healthy), current / "AGENTS.md")

    assert records[0] == inventory.RepositoryResult(
        broken.worktree,
        None,
        inventory.FleetStatus.ERROR,
        "OSError: fixture failure",
    )
    assert records[1].status is inventory.FleetStatus.UNCHANGED


def test_sync_cli_pins_arguments_idempotence_and_aggregate_exit_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    executor = tmp_path / "executor"
    (executor / "scripts").mkdir(parents=True)
    (executor / "scratchpad").mkdir()
    (executor / "AGENTS.md").write_text(STAMPED_AGENTS, encoding="utf-8")
    monkeypatch.setattr(inventory, "__file__", str(executor / "scripts" / "inventory_repositories.py"))
    inventory_path = executor / "scratchpad" / "repository-inventory.json"

    clean_fleet = tmp_path / "clean-fleet"
    stale = clean_fleet / "alice" / "stale"
    initialize_repository(stale, {"AGENTS.md": STALE_AGENTS})
    first_exit = inventory.main(["--sync", str(clean_fleet / "alice")])
    first_output = capsys.readouterr()
    first_expected = {
        "repositories": [
            {
                "repository": str(stale.resolve()),
                "layout": "exactly-one-well-formed-doctrine-block",
                "status": "UPDATED",
                "detail": f"source-sha256={STAMP}",
            }
        ]
    }
    assert first_exit == 0
    assert first_output.out == (f"UPDATED: {stale.resolve()}: source-sha256={STAMP}\nWROTE: {inventory_path}\n")
    assert first_output.err == ""
    assert inventory_path.read_text(encoding="utf-8") == json.dumps(first_expected, indent=2) + "\n"

    before_second = filesystem_snapshot(stale)
    second_exit = inventory.main(["--sync", str(clean_fleet / "alice")])
    second_output = capsys.readouterr()
    second_expected = {
        "repositories": [
            {
                "repository": str(stale.resolve()),
                "layout": "exactly-one-well-formed-doctrine-block",
                "status": "UNCHANGED",
                "detail": f"source-sha256={STAMP}",
            }
        ]
    }
    assert second_exit == 0
    assert second_output.out == (f"UNCHANGED: {stale.resolve()}: source-sha256={STAMP}\nWROTE: {inventory_path}\n")
    assert second_output.err == ""
    assert filesystem_snapshot(stale) == before_second
    assert inventory_path.read_text(encoding="utf-8") == json.dumps(second_expected, indent=2) + "\n"

    mixed_fleet = tmp_path / "mixed-fleet"
    current = mixed_fleet / "alice" / "current"
    missing = mixed_fleet / "hydrosolutions" / "missing"
    initialize_repository(current, {"AGENTS.md": STAMPED_AGENTS})
    initialize_repository(missing, {})
    mixed_exit = inventory.main(["--sync", str(mixed_fleet / "alice"), str(mixed_fleet / "hydrosolutions")])
    mixed_output = capsys.readouterr()
    mixed_expected = {
        "repositories": [
            {
                "repository": str(current.resolve()),
                "layout": "exactly-one-well-formed-doctrine-block",
                "status": "UNCHANGED",
                "detail": f"source-sha256={STAMP}",
            },
            {
                "repository": str(missing.resolve()),
                "layout": "no instruction file",
                "status": "MISSING",
                "detail": "repository has no root instruction file",
            },
        ]
    }
    assert mixed_exit == 1
    assert mixed_output.out == (
        f"UNCHANGED: {current.resolve()}: source-sha256={STAMP}\n"
        f"MISSING: {missing.resolve()}: repository has no root instruction file\n"
        f"WROTE: {inventory_path}\n"
    )
    assert mixed_output.err == ""
    assert inventory_path.read_text(encoding="utf-8") == json.dumps(mixed_expected, indent=2) + "\n"


def test_check_cli_splits_arguments_renders_results_and_aggregates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    executor = tmp_path / "executor"
    (executor / "scripts").mkdir(parents=True)
    (executor / "scratchpad").mkdir()
    (executor / "AGENTS.md").write_text(STAMPED_AGENTS, encoding="utf-8")
    monkeypatch.setattr(inventory, "__file__", str(executor / "scripts" / "inventory_repositories.py"))

    clean_fleet = tmp_path / "clean-fleet"
    clean_current = clean_fleet / "current"
    initialize_repository(clean_current, {"AGENTS.md": STAMPED_AGENTS})
    mixed_fleet = tmp_path / "mixed-fleet"
    mixed_current = mixed_fleet / "current"
    mixed_missing = mixed_fleet / "missing"
    initialize_repository(mixed_current, {"AGENTS.md": STAMPED_AGENTS})
    initialize_repository(mixed_missing, {})

    observed_arguments: list[tuple[str, ...]] = []
    original_search_roots = inventory._search_roots

    def capture_search_roots(arguments: list[str]) -> object:
        observed_arguments.append(tuple(arguments))
        return original_search_roots(arguments)

    monkeypatch.setattr(inventory, "_search_roots", capture_search_roots)
    inventory_path = executor / "scratchpad" / "repository-inventory.json"

    clean_exit = inventory.main(["--check", str(clean_fleet)])
    clean_output = capsys.readouterr()
    clean_expected = {
        "repositories": [
            {
                "repository": str(clean_current.resolve()),
                "layout": "exactly-one-well-formed-doctrine-block",
                "status": "CURRENT",
                "detail": f"installed source-sha256={STAMP}; available source-sha256={STAMP}",
            }
        ]
    }
    assert clean_exit == 0
    assert clean_output.out == (
        f"CURRENT: {clean_current.resolve()}: "
        f"installed source-sha256={STAMP}; available source-sha256={STAMP}\n"
        f"WROTE: {inventory_path}\n"
    )
    assert clean_output.err == ""
    assert inventory_path.read_text(encoding="utf-8") == json.dumps(clean_expected, indent=2) + "\n"

    mixed_exit = inventory.main(["--check", str(mixed_fleet)])
    mixed_output = capsys.readouterr()
    mixed_expected = {
        "repositories": [
            {
                "repository": str(mixed_current.resolve()),
                "layout": "exactly-one-well-formed-doctrine-block",
                "status": "CURRENT",
                "detail": f"installed source-sha256={STAMP}; available source-sha256={STAMP}",
            },
            {
                "repository": str(mixed_missing.resolve()),
                "layout": "no instruction file",
                "status": "MISSING",
                "detail": "repository has no root instruction file",
            },
        ]
    }
    assert mixed_exit == 1
    assert mixed_output.out == (
        f"CURRENT: {mixed_current.resolve()}: "
        f"installed source-sha256={STAMP}; available source-sha256={STAMP}\n"
        f"MISSING: {mixed_missing.resolve()}: repository has no root instruction file\n"
        f"WROTE: {inventory_path}\n"
    )
    assert mixed_output.err == ""
    assert inventory_path.read_text(encoding="utf-8") == json.dumps(mixed_expected, indent=2) + "\n"
    assert observed_arguments == [(str(clean_fleet),), (str(mixed_fleet),)]


def test_check_cli_runs_as_subprocess_by_script_path(tmp_path: Path) -> None:
    executor = tmp_path / "executor"
    scripts = executor / "scripts"
    scripts.mkdir(parents=True)
    (executor / "scratchpad").mkdir()
    (executor / "AGENTS.md").write_text(STAMPED_AGENTS, encoding="utf-8")
    inventory_script = scripts / "inventory_repositories.py"
    shutil.copy2(INVENTORY_SCRIPT, inventory_script)
    shutil.copy2(PROJECT_ROOT / "scripts" / "sync_doctrine.py", scripts / "sync_doctrine.py")

    fleet = tmp_path / "fleet"
    current = fleet / "current"
    initialize_repository(current, {"AGENTS.md": STAMPED_AGENTS})
    result = subprocess.run(
        [sys.executable, str(inventory_script), "--check", str(fleet)],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    module_result = subprocess.run(
        [sys.executable, "-m", "scripts.inventory_repositories", "--check", str(fleet)],
        cwd=executor,
        check=False,
        capture_output=True,
        text=True,
    )

    inventory_path = executor / "scratchpad" / "repository-inventory.json"
    expected = {
        "repositories": [
            {
                "repository": str(current.resolve()),
                "layout": "exactly-one-well-formed-doctrine-block",
                "status": "CURRENT",
                "detail": f"installed source-sha256={STAMP}; available source-sha256={STAMP}",
            }
        ]
    }
    expected_stdout = (
        f"CURRENT: {current.resolve()}: "
        f"installed source-sha256={STAMP}; available source-sha256={STAMP}\n"
        f"WROTE: {inventory_path}\n"
    )
    assert result.returncode == module_result.returncode == 0
    assert result.stdout == module_result.stdout == expected_stdout
    assert result.stderr == module_result.stderr == ""
    assert inventory_path.read_text(encoding="utf-8") == json.dumps(expected, indent=2) + "\n"


def test_check_cli_without_search_root_prints_exact_usage(capsys: pytest.CaptureFixture[str]) -> None:
    exit_status = inventory.main(["--check"])
    output = capsys.readouterr()

    assert exit_status == 64
    assert output.out == ""
    assert output.err == "Usage: inventory_repositories.py [--check | --sync] SEARCH_ROOT [SEARCH_ROOT ...]\n"


def test_sync_cli_without_search_root_prints_exact_usage(capsys: pytest.CaptureFixture[str]) -> None:
    exit_status = inventory.main(["--sync"])
    output = capsys.readouterr()

    assert exit_status == 64
    assert output.out == ""
    assert output.err == "Usage: inventory_repositories.py [--check | --sync] SEARCH_ROOT [SEARCH_ROOT ...]\n"


def test_production_source_has_no_owner_allowlist_or_reimplemented_sync() -> None:
    source = INVENTORY_SCRIPT.read_text(encoding="utf-8")
    assert INVENTORY_SCRIPT.stat().st_mode & stat.S_IXUSR
    for forbidden in (
        "alice",
        "hydrosolutions",
        "require_unedited(",
    ):
        assert forbidden not in source
    assert "check_doctrine(" in source
    assert source.count("sync_doctrine(") == 1
