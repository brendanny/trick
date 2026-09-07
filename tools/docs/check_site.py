"""Check structural pilot gates and report the unfinished corpus migration.

Default mode fails on missing pages/assets/explicit anchors and leaked helpers,
but reports existing link/duplicate-ID findings. --strict fails on all findings
and incomplete legacy coverage, and is a future cutover gate, not today's claim.
"""

import argparse
import hashlib
import json
import posixpath
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup
from common import ROOT, html_path, is_helper

ORIGIN = "https://nasa.github.io"
PREFIX = "/trick/"


def resolve_local(page: str, href: str, files: set[str]) -> tuple[str, str] | None:
    """Resolve output URLs, not Markdown paths; never read outside the site tree."""
    target = urlsplit(urljoin(ORIGIN + PREFIX + page, href))
    if target.scheme not in {"http", "https"} or target.netloc != "nasa.github.io":
        return None
    path = posixpath.normpath(unquote(target.path))
    if path == PREFIX.rstrip("/"):
        path = PREFIX
    if not path.startswith(PREFIX):
        return None  # another project on nasa.github.io, not this site's output
    relative = path[len(PREFIX) :]
    if not relative or target.path.endswith("/"):
        relative = posixpath.join(relative, "index.html")
    elif relative not in files and not posixpath.splitext(relative)[1]:
        # File-presence resolution only; this does NOT prove Pages serves aliases.
        relative = next(
            (
                candidate
                for candidate in (relative + ".html", relative + "/index.html")
                if candidate in files
            ),
            relative,
        )
    return relative, unquote(target.fragment)


def collect_site(directory: Path) -> tuple[set[str], dict]:
    files, pages = set(), {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Unexpected symlink in built output: {path}")
        if not path.is_file():
            continue
        name = path.relative_to(directory).as_posix()
        files.add(name)
        if path.suffix != ".html":
            continue
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        body = soup.select_one("article.md-content__inner") or soup.body or soup
        ids = [str(tag["id"]) for tag in body.find_all(id=True)]
        names = [str(tag["name"]) for tag in body.find_all("a", attrs={"name": True})]
        links = [str(tag["href"]) for tag in body.find_all("a", href=True)]
        resources = [str(tag["src"]) for tag in body.find_all(src=True)]
        pages[name] = {
            "anchors": set(ids + names),
            "duplicate_ids": sorted(
                key for key, count in Counter(ids).items() if count > 1
            ),
            "links": links,
            "resources": resources,
            "text": body.get_text(" ", strip=True),
            "code_blocks": len(body.select("pre code")),
            "images": len(body.find_all("img")),
            "headings": len(body.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])),
        }
    return files, pages


def inspect_site(directory: Path, baseline: dict, pilot: list[dict]) -> dict:
    files, pages = collect_site(directory)
    errors, findings = [], []
    for helper in baseline["helpers"]:
        name = helper["source"]
        if name in files or (name.endswith(".md") and html_path(name) in files):
            errors.append(f"Jekyll helper published: {name}")
    for name in files:
        if is_helper(name) or name in {"_Sidebar.html", "_Footer.html"}:
            errors.append(f"Jekyll helper output: {name}")
    for page in baseline["pages"]:
        name = page["expected_html"]
        if name not in pages:
            errors.append(f"Missing baseline page: {name}")
            continue
        for anchor in page["explicit_anchors"]:
            if anchor not in pages[name]["anchors"]:
                errors.append(f"Missing explicit anchor: {name}#{anchor}")
    for asset in baseline["assets"]:
        if asset["source"] not in files:
            errors.append(f"Missing baseline asset: {asset['source']}")
        else:
            content = (directory / asset["source"]).read_bytes()
            header = f"blob {len(content)}\0".encode("ascii")
            digest = hashlib.sha1(header + content, usedforsecurity=False).hexdigest()
            if digest != asset["git_blob"]:
                errors.append(f"Changed baseline asset: {asset['source']}")
    for capture in baseline.get("rendered_capture", []):
        actual = pages.get(capture["html"], {}).get("anchors", set())
        for anchor in capture["anchors"]:
            if anchor not in actual:
                findings.append({
                    "kind": "legacy-rendered-anchor",
                    "page": capture["html"],
                    "target": anchor,
                })
    for name, page in pages.items():
        for anchor in page["duplicate_ids"]:
            findings.append({"kind": "duplicate-id", "page": name, "target": anchor})
        for href in sorted(set(page["links"] + page["resources"])):
            resolved = resolve_local(name, href, files)
            if resolved is None:
                continue
            target, fragment = resolved
            if target not in files:
                findings.append({
                    "kind": "missing-target",
                    "page": name,
                    "target": href,
                })
            elif (
                fragment
                and target in pages
                and fragment not in pages[target]["anchors"]
            ):
                findings.append({
                    "kind": "missing-fragment",
                    "page": name,
                    "target": href,
                })
    for example in pilot:
        name = html_path(example["source"])
        page = pages.get(name)
        if page is None:
            errors.append(f"Missing pilot page: {name}")
            continue
        for key in ("code_blocks", "images", "headings"):
            if page[key] < example.get("min_" + key, 0):
                errors.append(f"Pilot {name}: too few {key}")
        for phrase in example.get("contains", []):
            if phrase not in page["text"]:
                errors.append(f"Pilot {name}: missing expected text {phrase!r}")
    if "search.json" not in files:
        errors.append("Missing built-in search index")
    else:
        search = json.loads((directory / "search.json").read_text())
        items = search.get("items") if isinstance(search, dict) else None
        if not isinstance(items, list) or not items:
            errors.append("Empty or invalid built-in search index")
        else:
            locations = {
                urlsplit(item.get("location", "")).path
                for item in items
                if isinstance(item, dict)
            }
            for example in pilot:
                if html_path(example["source"]) not in locations:
                    errors.append(
                        f"Pilot page missing from search: {example['source']}"
                    )
    return {
        "schema_version": 1,
        "source_commit": baseline["source_commit"],
        "legacy_coverage": baseline["coverage"],
        "published_html_files": len(pages),
        "pilot_pages": len(pilot),
        "gate_errors": sorted(set(errors)),
        "migration_findings": sorted(
            findings, key=lambda row: (row["page"], row["kind"], row["target"])
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=ROOT / "site")
    parser.add_argument(
        "--baseline", type=Path, default=ROOT / "tools/docs/legacy-routes.json"
    )
    parser.add_argument("--report", type=Path, default=ROOT / ".docs-build/report.json")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text())
    pilot = json.loads((ROOT / "tools/docs/pilot.json").read_text())
    report = inspect_site(args.site, baseline, pilot)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Checked {report['published_html_files']} HTML files and {report['pilot_pages']} pilot pages."
    )
    print(
        f"Structural errors: {len(report['gate_errors'])}; migration findings: {len(report['migration_findings'])}."
    )
    for error in report["gate_errors"]:
        print("ERROR:", error)
    print("Detailed report:", args.report)
    incomplete = not all(
        baseline["coverage"].get(key)
        for key in (
            "rendered_heading_ids",
            "host_redirects_verified",
            "pages_settings_verified",
        )
    )
    if incomplete:
        print(
            "Legacy coverage is incomplete: rendered IDs and live publishing/alias checks remain cutover requirements."
        )
    return int(
        bool(
            report["gate_errors"]
            or (args.strict and (report["migration_findings"] or incomplete))
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
