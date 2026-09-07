"""Small shared helpers for the non-publishing documentation migration harness."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPERS = frozenset({"_config.yml", "_Sidebar.md", "_Footer.md"})


def is_helper(path: str) -> bool:
    return path in HELPERS or path.startswith("_layouts/")


def html_path(source: str) -> str:
    return str(Path(source).with_suffix(".html")).replace("\\", "/")
