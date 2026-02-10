# Consuming fishy Documentation

## Overview

fishy ships its `documentation/` directory inside the Python package. Downstream repos access docs programmatically instead of copying files manually.

## API

```python
from fishy import get_docs_path

docs = get_docs_path()  # Returns pathlib.Path to documentation/
```

`get_docs_path()` returns the absolute `Path` to the documentation directory inside the installed fishy package. It works with both editable installs (`uv sync`) and wheel installs.

## Makefile Sync Target

Add this to your downstream repo's `Makefile` to sync docs locally:

```makefile
.PHONY: sync-docs

sync-docs:
	uv lock --upgrade-package fishy
	uv sync
	uv run python -c "from pathlib import Path; import shutil; from fishy.docs import get_docs_path; dst = Path('fishy_docs'); shutil.rmtree(dst, ignore_errors=True); shutil.copytree(get_docs_path(), dst); print(f'Synced {sum(1 for _ in dst.rglob(chr(42) + chr(46) + \"md\"))} docs to {dst}/')"
```

Running `make sync-docs` will:

1. Upgrade fishy to the latest version
2. Copy the bundled docs to a local `fishy_docs/` directory
3. Print the count of synced files

## New Repo Quickstart

1. Add fishy as a dependency: `uv add fishy`
2. Add the Makefile target above
3. Run `make sync-docs`
4. Add `fishy_docs/` to your `.gitignore` (or track it for offline access)
5. Reference docs in your `CLAUDE.md` or agent context as needed
