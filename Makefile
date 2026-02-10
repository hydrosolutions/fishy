.PHONY: sync-docs

sync-docs:
	uv lock --upgrade-package taqsim
	uv sync
	uv run python -c "\
		from pathlib import Path; import shutil; \
		from taqsim.docs import get_docs_path; \
		dst = Path('taqsim_docs'); \
		shutil.rmtree(dst, ignore_errors=True); \
		shutil.copytree(get_docs_path(), dst); \
		print(f'Synced {sum(1 for _ in dst.rglob(chr(42) + \".md\"))} docs to {dst}/')"
