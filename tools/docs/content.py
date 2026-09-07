"""Validate authored page metadata and preserve the migration's code samples."""

import markdown
import yaml
from bs4 import BeautifulSoup
from build import source_files
from inventory import git


def frontmatter(source: str) -> tuple[dict, str]:
    lines = source.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("Missing YAML front matter")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError("Unterminated YAML front matter")
    metadata = yaml.safe_load("".join(lines[1:end]))
    if not isinstance(metadata, dict):
        raise ValueError("Front matter must be a mapping")
    if not isinstance(metadata.get("title"), str) or not metadata["title"].strip():
        raise ValueError("Missing page title")
    if metadata.get("documentation_status") not in {"current", "historical"}:
        raise ValueError("Missing or invalid documentation_status")
    search = metadata.get("search", {})
    if not isinstance(search, dict):
        raise ValueError("search must be a mapping")
    if metadata["documentation_status"] == "historical":
        if search.get("exclude") is not True:
            raise ValueError("Historical pages must be excluded from search")
    elif search.get("exclude", False) is not False:
        raise ValueError("Current pages must remain searchable")
    return metadata, "".join(lines[end + 1 :])


def code_samples(source: str) -> list[str]:
    """Code text only, in order; Markdown links and page metadata are not code."""
    soup = BeautifulSoup(
        markdown.markdown(source, extensions=["pymdownx.superfences"]), "html.parser"
    )
    return [code.get_text() for code in soup.select("pre code")]


def inspect_content(root, baseline: dict) -> tuple[dict, list[str]]:
    pages, errors = {}, []
    originals = {page["source"]: page for page in baseline["pages"]}
    for name, path in source_files(root).items():
        if not name.endswith(".md"):
            continue
        try:
            metadata, body = frontmatter(path.read_text(encoding="utf-8"))
        except (ValueError, yaml.YAMLError) as error:
            errors.append(f"{name}: {error}")
            continue
        samples = code_samples(body)
        original = originals.get(name)
        if original:
            previous = git(root, "cat-file", "blob", original["git_blob"]).decode()
            if samples != code_samples(previous):
                errors.append(f"Changed migration code samples: {name}")
        pages[name] = {**metadata, "code_samples": samples}
    return pages, errors
