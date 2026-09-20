"""init preservation : TemplateFiles × WarmUvCache × EmptyHome → InitializedDoctrineSync."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PATHS = (
    ".gitignore",
    ".pce/repository-contract.json",
    ".python-version",
    "AGENTS.md",
    "CLAUDE.md",
    "CONTEXT.md",
    "README.md",
    "docs/codex-non-interactive.md",
    "init.sh",
    "pyproject.toml",
    "scratchpad/.gitkeep",
    "scripts/controlled_retrofit.py",
    "scripts/inventory_repositories.py",
    "scripts/sync_doctrine.py",
    "src/mypackage/__init__.py",
    "tests/.gitkeep",
    "tests/test_controlled_retrofit.py",
    "tests/test_init.py",
    "tests/test_inventory_repositories.py",
    "tests/test_smoke.py",
    "tests/test_sync_doctrine.py",
    "uv.lock",
)
UNCHANGED_PATHS = (
    ".gitignore",
    ".pce/repository-contract.json",
    ".python-version",
    "CONTEXT.md",
    "docs/codex-non-interactive.md",
    "scratchpad/.gitkeep",
    "scripts/controlled_retrofit.py",
    "scripts/inventory_repositories.py",
    "tests/.gitkeep",
    "tests/test_controlled_retrofit.py",
    "tests/test_init.py",
    "tests/test_inventory_repositories.py",
    "tests/test_smoke.py",
    "tests/test_sync_doctrine.py",
)
PROJECT_NAME = "example-project"
PLACEHOLDER = "SHORT PROJECT DESC" + "RIPTION"
EXPECTED_OVERVIEW = "## 0. Project Overview\n\nexample-project\n\n## 1. Python Environment"
EXPECTED_CLAUDE_POINTER = "See [AGENTS.md](./AGENTS.md).\n"
EXPECTED_INIT_STDOUT = """Initializing project: example-project (package: example_project)
Done! Project 'example-project' is ready.
"""
SOURCE_STAMP = "59e37fd6b3dbab27530822e6956da51bb7ae76b637e3638530f99a8b4db9038d"
SOURCE_BODY = """Four rules. They are one design stance seen four ways: a module means one thing, receives exactly what it needs, in types that cannot lie, and dies rather than guess.

1. **A module means one thing.**
2. **It receives exactly what it needs.**
3. **Its types cannot lie.**
4. **It dies rather than guess.**
"""
SOURCE_BLOCK = f"""<!-- BEGIN SYNCED DOCTRINE; source-sha256={SOURCE_STAMP} -->
{SOURCE_BODY}<!-- END SYNCED DOCTRINE -->"""
DOCTRINE_RULES = (
    "1. **A module means one thing.**",
    "2. **It receives exactly what it needs.**",
    "3. **Its types cannot lie.**",
    "4. **It dies rather than guess.**",
)
EXPECTED_SYNC_STDOUT = f"UNCHANGED: AGENTS.md: source-sha256={SOURCE_STAMP}\n"


def test_init_preserves_doctrine_sync_offline_with_empty_home(tmp_path: Path) -> None:
    project_copy = tmp_path / "pyplate"
    for relative_path in PROJECT_PATHS:
        source = PROJECT_ROOT / relative_path
        destination = project_copy / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    source_cache = PROJECT_ROOT / ".uv-cache"
    assert source_cache.is_dir()
    shutil.copytree(source_cache, project_copy / ".uv-cache")

    empty_home = tmp_path / "empty-home"
    empty_home.mkdir()
    environment = os.environ.copy()
    environment["HOME"] = str(empty_home)
    environment["UV_OFFLINE"] = "1"
    environment["UV_PYTHON"] = sys.executable
    init_result = subprocess.run(
        ["bash", str(project_copy / "init.sh"), PROJECT_NAME],
        cwd=project_copy,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert init_result.returncode == 0
    assert init_result.stdout == EXPECTED_INIT_STDOUT
    assert list(empty_home.iterdir()) == []
    assert (project_copy / "CLAUDE.md").read_text() == EXPECTED_CLAUDE_POINTER
    assert (project_copy / "README.md").read_text() == "# example-project\n"
    assert not (project_copy / "init.sh").exists()
    assert not (project_copy / "src" / "mypackage").exists()
    assert (project_copy / "src" / "example_project" / "__init__.py").read_bytes() == (
        PROJECT_ROOT / "src" / "mypackage" / "__init__.py"
    ).read_bytes()

    expected_pyproject = (
        (PROJECT_ROOT / "pyproject.toml")
        .read_text()
        .replace('name = "mypackage"', 'name = "example-project"')
        .replace('description = "Add your description here"', 'description = "example-project"')
    )
    assert (project_copy / "pyproject.toml").read_text() == expected_pyproject
    expected_lock = (PROJECT_ROOT / "uv.lock").read_text().replace('name = "mypackage"', 'name = "example-project"')
    assert (project_copy / "uv.lock").read_text() == expected_lock
    for relative_path in UNCHANGED_PATHS:
        assert (project_copy / relative_path).read_bytes() == (PROJECT_ROOT / relative_path).read_bytes()

    files_with_placeholder = [
        path.relative_to(project_copy)
        for path in project_copy.rglob("*")
        if path.is_file() and PLACEHOLDER.encode() in path.read_bytes()
    ]
    assert files_with_placeholder == []

    sync_script = project_copy / "scripts" / "sync_doctrine.py"
    assert sync_script.read_bytes() == (PROJECT_ROOT / "scripts" / "sync_doctrine.py").read_bytes()
    assert sync_script.stat().st_mode & stat.S_IXUSR

    agents_path = project_copy / "AGENTS.md"
    expected_agents = (PROJECT_ROOT / "AGENTS.md").read_text().replace(PLACEHOLDER, PROJECT_NAME)
    agents_text = agents_path.read_text(encoding="utf-8")
    assert agents_text == expected_agents
    assert EXPECTED_OVERVIEW in agents_text
    assert hashlib.sha256(SOURCE_BODY.encode("utf-8")).hexdigest() == SOURCE_STAMP
    assert agents_text.count("<!-- BEGIN SYNCED DOCTRINE;") == 1
    assert agents_text.count("<!-- END SYNCED DOCTRINE -->") == 1
    assert SOURCE_BLOCK in agents_text
    for rule in DOCTRINE_RULES:
        assert rule in agents_text

    before = agents_path.stat()
    first_sync = subprocess.run(
        [str(sync_script)],
        cwd=project_copy,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    second_sync = subprocess.run(
        [str(sync_script)],
        cwd=project_copy,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    after = agents_path.stat()

    assert (first_sync.returncode, second_sync.returncode) == (0, 0)
    assert (first_sync.stdout, second_sync.stdout) == (EXPECTED_SYNC_STDOUT, EXPECTED_SYNC_STDOUT)
    assert (first_sync.stderr, second_sync.stderr) == ("", "")
    assert agents_path.read_text(encoding="utf-8") == agents_text
    assert after.st_mtime_ns == before.st_mtime_ns
