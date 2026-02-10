from pathlib import Path


def get_docs_path() -> Path:
    return Path(__file__).parent / "documentation"
