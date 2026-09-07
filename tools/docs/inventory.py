"""Record source evidence; optionally enrich it with an actual Jekyll HTML build.

Never label inferred source paths or Python Markdown heading IDs as observations
of Jekyll output. Automatic heading IDs require a separately supplied old build.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import markdown
from bs4 import BeautifulSoup
from common import ROOT, html_path, is_helper


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args])


def explicit_anchors(source: str) -> list[str]:
    # Render code as code before inspecting HTML, so examples of <a id=...>
    # do not become false anchors. No toc/slug extension is enabled here.
    rendered = markdown.markdown(source, extensions=["pymdownx.superfences"])
    soup = BeautifulSoup(rendered, "html.parser")
    anchors = {str(tag["id"]) for tag in soup.find_all(id=True)}
    anchors.update(str(tag["name"]) for tag in soup.find_all("a", attrs={"name": True}))
    return sorted(anchors)


def source_inventory(root: Path, ref: str) -> dict:
    commit = (
        git(root, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}")
        .decode()
        .strip()
    )
    entries = git(root, "ls-tree", "-r", "-z", commit, "--", "docs").split(b"\0")
    pages, assets, helpers = [], [], []
    for entry in entries:
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, kind, blob = metadata.decode().split()
        path = name.decode().removeprefix("docs/")
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError(f"Unsupported documentation tree entry: {path} ({mode})")
        record = {"source": path, "git_blob": blob}
        if is_helper(path):
            helpers.append(record)
        elif path.endswith(".md"):
            text = git(root, "cat-file", "blob", blob).decode("utf-8")
            record.update(
                expected_html=html_path(path),
                explicit_anchors=explicit_anchors(text),
                disposition=(
                    "retain-for-historical-review"
                    if path.startswith("not_referenced/")
                    or path.startswith("developer_docs/Des")
                    else "retain"
                ),
            )
            pages.append(record)
        else:
            assets.append(record)
    if not pages:
        raise ValueError("No documentation pages found")
    return {
        "schema_version": 1,
        "source_commit": commit,
        "coverage": {
            "paths": "inferred-from-source-filenames; not a live-route observation",
            "anchors": "explicit-source-anchors-only",
            "rendered_heading_ids": False,
            "host_redirects_verified": False,
            "pages_settings_verified": False,
        },
        "pages": pages,
        "assets": assets,
        "helpers": helpers,
    }


def capture_rendered(baseline: dict, directory: Path) -> dict:
    """Attach static rendered IDs, without claiming host or client-JS behavior."""
    captures = []
    for page in baseline["pages"]:
        path = directory / page["expected_html"]
        if not path.is_file():
            raise ValueError(
                f"Incomplete legacy build: missing {page['expected_html']}"
            )
        content = path.read_bytes()
        soup = BeautifulSoup(content, "html.parser")
        anchors = {str(tag["id"]) for tag in soup.find_all(id=True)}
        anchors.update(
            str(tag["name"]) for tag in soup.find_all("a", attrs={"name": True})
        )
        captures.append({
            "html": page["expected_html"],
            "sha256": hashlib.sha256(content).hexdigest(),
            "anchors": sorted(anchors),
        })
    result = {**baseline, "rendered_capture": captures}
    result["coverage"] = {
        **baseline["coverage"],
        "rendered_heading_ids": True,
        "rendered_evidence": "caller-supplied Jekyll output for source_commit; static HTML only",
        "client_generated_ids_verified": False,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ref", help="Git revision to inventory (defaults to recorded baseline)"
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--check", action="store_true", help="Check reproducibility of source evidence"
    )
    parser.add_argument(
        "--legacy-html", type=Path, help="Optional matching Jekyll build output"
    )
    args = parser.parse_args()
    baseline_path = ROOT / "tools/docs/legacy-routes.json"
    recorded = json.loads(baseline_path.read_text()) if baseline_path.exists() else None
    if args.check and (args.output or args.legacy_html or args.ref):
        parser.error("--check cannot be combined with capture/output/ref options")
    if not args.ref and recorded is None:
        parser.error("--ref is required for the first inventory")
    baseline = source_inventory(ROOT, args.ref or recorded["source_commit"])
    if args.check:
        expected = {key: recorded[key] for key in baseline}
        # The tracked source-only manifest is intentionally immutable during conversion.
        if baseline != expected:
            print(
                "Source inventory differs; review changes before regenerating the baseline."
            )
            return 1
        print(
            f"Source inventory verified: {len(baseline['pages'])} pages, {len(baseline['assets'])} assets"
        )
        return 0
    if args.legacy_html:
        baseline = capture_rendered(baseline, args.legacy_html)
    content = json.dumps(baseline, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
