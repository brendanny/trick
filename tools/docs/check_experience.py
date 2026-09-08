"""Static reader-experience checks, not browser or accessibility certification."""

import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from xml.etree import ElementTree

import tomllib
from bs4 import BeautifulSoup
from build import source_files
from common import ROOT, html_path
from content import frontmatter

SITE_URL = "https://nasa.github.io/trick/"
EDIT_URL = "https://github.com/nasa/trick/edit/master/docs/"
AUTO_LINKS = {
    "stylesheet",
    "icon",
    "preload",
    "modulepreload",
    "prefetch",
    "preconnect",
    "dns-prefetch",
    "manifest",
}
CSS_URL = re.compile(
    r"url\(\s*(?:\"([^\"]*)\"|'([^']*)'|([^)]*))\s*\)"
    r"|@import\s+(?:\"([^\"]*)\"|'([^']*)')",
    re.IGNORECASE,
)


def nav_paths(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        value = value.values()
    return [path for child in value for path in nav_paths(child)]


def check_navigation(nav, metadata: dict) -> list[str]:
    counts = Counter(nav_paths(nav))
    current = {
        name
        for name, meta in metadata.items()
        if meta["documentation_status"] == "current"
    }
    errors = [
        f"Current page needs one nav home: {name} ({counts[name]})"
        for name in sorted(current)
        if counts[name] != 1
    ]
    errors.extend(
        f"Non-current or unknown page in nav: {name}"
        for name in sorted(counts.keys() - current)
    )
    return errors


def nav_ancestors(value, parents=()) -> dict:
    if isinstance(value, str):
        return {value: parents}
    if isinstance(value, dict):
        return {
            name: trail
            for child in value.values()
            for name, trail in nav_ancestors(
                child,
                (*parents, nav_paths(child)[0]) if isinstance(child, list) else parents,
            ).items()
        }
    return {
        name: trail
        for child in value
        for name, trail in nav_ancestors(child, parents).items()
    }


def check_navigation_controls(nav, pages: dict) -> list[str]:
    """Check the rendered section scope, trails, and sequential page links."""
    errors = []
    order = nav_paths(nav)
    ancestors = nav_ancestors(nav)
    tabs = [(title, nav_paths(value)) for item in nav for title, value in item.items()]
    expected_tabs = [(title, SITE_URL + html_path(paths[0])) for title, paths in tabs]
    for source in order:
        page = html_path(source)
        if page not in pages:
            continue  # Missing output is reported by the authored-page check.
        soup = pages[page]

        def links(selector, page=page, soup=soup):
            return [
                unquote(urljoin(SITE_URL + page, tag["href"]))
                for tag in soup.select(selector)
            ]

        rendered_tabs = [
            (tag.get_text(" ", strip=True), target)
            for tag, target in zip(
                soup.select(".md-tabs a[href]"), links(".md-tabs a[href]")
            )
        ]
        if rendered_tabs != expected_tabs:
            errors.append(f"Incorrect section tabs: {page}")
        section = next(i for i, (_, paths) in enumerate(tabs) if source in paths)
        if links(".md-tabs__item--active a[href]") != [expected_tabs[section][1]]:
            errors.append(f"Incorrect active tab: {page}")
        active = soup.select(
            ".md-nav--primary.md-nav--lifted > ul > .md-nav__item--active"
        )
        if len(active) != 1:
            errors.append(f"Missing section-scoped sidebar: {page}")
        else:
            targets = {
                unquote(urljoin(SITE_URL + page, tag["href"]))
                for tag in active[0].select("a[href]")
                if not urlsplit(tag["href"]).fragment
            }
            if targets != {SITE_URL + html_path(name) for name in tabs[section][1]}:
                errors.append(f"Incorrect sidebar section pages: {page}")
        # The native theme shows breadcrumbs for two or more ancestor sections;
        # the active tab identifies pages immediately within a top-level section.
        if len(ancestors[source]) > 1 and links(".md-path a[href]") != [
            SITE_URL + html_path(name) for name in ancestors[source]
        ]:
            errors.append(f"Incorrect breadcrumbs: {page}")
        position = order.index(source)
        for direction, neighbor in (("prev", position - 1), ("next", position + 1)):
            expected = (
                [SITE_URL + html_path(order[neighbor])]
                if 0 <= neighbor < len(order)
                else []
            )
            if links(f".md-footer__link--{direction}[href]") != expected:
                errors.append(f"Incorrect {direction} page navigation: {page}")
    return errors


def check_outline(page: str, soup) -> list[str]:
    """A single page title keeps every Markdown section in the native TOC."""
    errors = []
    if len(soup.select("article h1")) != 1:
        errors.append(f"Page needs one top-level title: {page}")
    headings = {
        tag["id"]
        for tag in soup.select("article :is(h2, h3, h4, h5, h6)[id]")
        if tag.select_one("a.headerlink")
    }
    contents = {
        unquote(tag["href"][1:])
        for tag in soup.select('.md-nav--secondary a[href^="#"]')
    }
    if headings - contents:
        errors.append(f"Sections missing from native contents: {page}")
    for tag in soup.select("article th, article strong, article h1, article h2"):
        text = tag.get_text(" ", strip=True).removesuffix(" ¶").lower()
        if text in {"contents", "table of contents", "quick jump menu"} or (
            text.startswith("home") and "→" in text
        ):
            errors.append(f"Legacy navigation inside article: {page}")
    if any(
        re.fullmatch(r"(?:next|previous) page", tag.get_text(strip=True), re.IGNORECASE)
        for tag in soup.select("article a[href]")
    ):
        errors.append(f"Legacy page footer inside article: {page}")
    return errors


def local_resource(page: str, href: str, files: set[str]) -> str | None:
    """Require same-origin, under-prefix resources; data URLs need no request."""
    if href.startswith(("data:", "#")):
        return None
    target = urlsplit(urljoin(SITE_URL + page, href))
    if target.scheme != "https" or target.netloc != "nasa.github.io":
        return f"External automatic resource: {page}: {href}"
    path = unquote(target.path)
    if not path.startswith("/trick/"):
        return f"Resource outside site prefix: {page}: {href}"
    if path.removeprefix("/trick/") not in files:
        return f"Missing automatic resource: {page}: {href}"
    return None


def css_resources(css: str) -> list[str]:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    return [
        next(group for group in match.groups() if group is not None).strip()
        for match in CSS_URL.finditer(css)
    ]


def check_resources(page: str, soup, files: set[str]) -> list[str]:
    resources = [str(tag["src"]) for tag in soup.find_all(src=True)]
    resources += [
        str(tag["href"])
        for tag in soup.find_all("link", href=True)
        if AUTO_LINKS.intersection(tag.get("rel", []))
    ]
    resources += [str(tag["poster"]) for tag in soup.find_all(poster=True)]
    resources += [str(tag["data"]) for tag in soup.find_all("object", data=True)]
    for tag in soup.find_all(srcset=True):
        resources.extend(
            part.strip().split()[0]
            for part in str(tag["srcset"]).split(",")
            if part.strip()
        )
    for tag in soup.find_all("style"):
        resources.extend(css_resources(tag.get_text()))
    for tag in soup.find_all(style=True):
        resources.extend(css_resources(str(tag["style"])))
    errors = [
        error for href in resources if (error := local_resource(page, href, files))
    ]
    if soup.select('[data-md-component="source"]'):
        errors.append(f"Network-backed repository statistics enabled: {page}")
    if soup.find("meta", attrs={"http-equiv": re.compile("^refresh$", re.IGNORECASE)}):
        errors.append(f"Automatic meta refresh needs review: {page}")
    return errors


def check_page(page: str, soup, source: str) -> list[str]:
    errors = []
    canonical = [tag.get("href") for tag in soup.select('link[rel="canonical"]')]
    if canonical != [SITE_URL + page]:
        errors.append(f"Incorrect canonical URL: {page}")
    edits = [unquote(tag.get("href", "")) for tag in soup.select('a[rel="edit"]')]
    if edits != [EDIT_URL + source]:
        errors.append(f"Incorrect authored-source edit URL: {page}")
    banner = soup.select_one(".md-banner")
    if banner is None or "Development documentation · master" not in banner.get_text():
        errors.append(f"Missing development label: {page}")
    palettes = soup.select('[data-md-component="palette"] input[aria-label]')
    if {tag.get("data-md-color-scheme") for tag in palettes} != {"default", "slate"}:
        errors.append(f"Missing labeled light/dark controls: {page}")
    if not soup.select_one('meta[name="viewport"]'):
        errors.append(f"Missing responsive viewport: {page}")
    skip = soup.select_one("a.md-skip[href]")
    if skip is None or soup.find(id=unquote(skip["href"].removeprefix("#"))) is None:
        errors.append(f"Missing or broken skip link: {page}")
    return errors


def check_sitemap(locations: list[str], metadata: dict) -> list[str]:
    # The pinned generator omits search-excluded pages from the sitemap too.
    expected = {
        SITE_URL + html_path(name)
        for name, meta in metadata.items()
        if meta["documentation_status"] == "current"
    }
    if set(locations) != expected or len(locations) != len(expected):
        return ["Sitemap must contain each current canonical URL exactly once"]
    return []


def inspect_experience(root: Path, directory: Path) -> dict:
    config = tomllib.loads((root / "zensical.toml").read_text())["project"]
    metadata = {
        name: frontmatter(path.read_text())[0]
        for name, path in source_files(root).items()
        if name.endswith(".md")
    }
    errors = check_navigation(config["nav"], metadata)
    files = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file()
    }
    pages = {
        name: BeautifulSoup((directory / name).read_text(), "html.parser")
        for name in sorted(files)
        if name.endswith(".html")
    }
    errors.extend(check_navigation_controls(config["nav"], pages))
    for page, soup in pages.items():
        errors.extend(check_resources(page, soup, files))
        runtime = soup.select_one("script#__config")
        if runtime:
            data = json.loads(runtime.get_text())
            for href in (data["search"], data["base"].rstrip("/") + "/search.json"):
                if error := local_resource(page, href, files):
                    errors.append(error)
            if any(
                feature.startswith("navigation.instant") for feature in data["features"]
            ):
                errors.append(
                    f"Instant navigation requires separate validation: {page}"
                )
    for name in sorted(files):
        if name.endswith(".css"):
            for href in css_resources((directory / name).read_text()):
                if error := local_resource(name, href, files):
                    errors.append(error)
    for source in metadata:
        page = html_path(source)
        if page not in pages:
            errors.append(f"Missing authored output: {page}")
            continue
        errors.extend(check_page(page, pages[page], source))
        errors.extend(check_outline(page, pages[page]))
    historical = {
        html_path(name)
        for name, meta in metadata.items()
        if meta["documentation_status"] == "historical"
    }
    archive = pages.get("archive.html", BeautifulSoup("", "html.parser"))
    archive_links = {
        unquote(urlsplit(urljoin(SITE_URL + "archive.html", tag["href"])).path)
        for tag in archive.select("article a[href]")
    }
    errors.extend(
        f"Historical page missing from archive: {name}"
        for name in sorted(historical)
        if "/trick/" + name not in archive_links
    )
    home = pages.get("index.html", BeautifulSoup("", "html.parser"))
    nav_links = {
        unquote(urljoin(SITE_URL + "index.html", tag["href"]))
        for tag in home.select(".md-nav--primary a[href]")
    }
    errors.extend(
        f"Missing rendered navigation link: {name}"
        for name in nav_paths(config["nav"])
        if SITE_URL + html_path(name) not in nav_links
    )
    missing = pages.get("404.html", BeautifulSoup("", "html.parser"))
    recovery = {tag["href"] for tag in missing.select("article a[href]")}
    for target in (
        "",
        "documentation/install_guide/Install-Guide.html",
        "faq/FAQ.html",
        "archive.html",
    ):
        if SITE_URL + target not in recovery:
            errors.append(f"Missing prefix-safe 404 recovery link: {target or 'home'}")
    sitemap = ElementTree.parse(directory / "sitemap.xml")
    locations = [unquote(node.text or "") for node in sitemap.findall(".//{*}loc")]
    errors.extend(check_sitemap(locations, metadata))
    return {
        "authored_pages": len(metadata),
        "nav_pages": len(nav_paths(config["nav"])),
        "archived_pages": len(historical),
        "html_files_audited": len(pages),
        "errors": sorted(set(errors)),
        "browser_validation": "pending: visual, keyboard, contrast, mobile, and network-blocked browser checks",
    }


def main() -> int:
    report = inspect_experience(ROOT, ROOT / "site")
    output = ROOT / ".docs-build/experience-report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        f"Reader experience: {report['nav_pages']} nav pages, "
        f"{report['archived_pages']} archived pages, {len(report['errors'])} errors."
    )
    for error in report["errors"]:
        print(error)
    print(f"Report: {output}")
    return bool(report["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
