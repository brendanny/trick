"""Negative fixtures for the static reader-experience gates."""

import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_experience import (
    check_navigation,
    check_page,
    check_resources,
    check_sitemap,
    css_resources,
    local_resource,
    nav_paths,
)


class ReaderExperience(unittest.TestCase):
    def test_sitemap_requires_current_pages_and_canonical_prefix_without_duplicates(
        self,
    ):
        metadata = {
            "a.md": {"documentation_status": "current"},
            "old.md": {"documentation_status": "historical"},
        }
        url = "https://nasa.github.io/trick/a.html"
        self.assertEqual(check_sitemap([url], metadata), [])
        for locations in (
            [],
            [url, url],
            [url.replace("/trick/", "/")],
            [url, "https://nasa.github.io/trick/old.html"],
        ):
            self.assertTrue(check_sitemap(locations, metadata))

    def test_nav_has_exactly_one_home_per_current_page(self):
        metadata = {
            "a.md": {"documentation_status": "current"},
            "old.md": {"documentation_status": "historical"},
        }
        self.assertEqual(check_navigation([{"Group": ["a.md"]}], metadata), [])
        for nav in ([], ["a.md", "a.md"], ["a.md", "old.md"], ["a.md", "typo.md"]):
            self.assertTrue(check_navigation(nav, metadata))
        self.assertEqual(
            nav_paths([{"Group": ["a.md", {"B": "b.md"}]}]), ["a.md", "b.md"]
        )

    def test_resource_paths_reject_external_missing_and_outside_prefix(self):
        files = {"assets/app.js"}
        for href in (
            "../assets/app.js",
            "/trick/assets/app.js",
            "https://nasa.github.io/trick/assets/app.js",
        ):
            self.assertIsNone(local_resource("nested/page.html", href, files))
        for href in (
            "https://cdn.example/app.js",
            "//cdn.example/app.js",
            "/assets/app.js",
            "../missing.js",
            "/trick/../other/app.js",
            "http://nasa.github.io/trick/assets/app.js",
        ):
            self.assertIsNotNone(local_resource("nested/page.html", href, files))
        self.assertIsNone(local_resource("a.html", "data:image/png;base64,abc", files))
        self.assertIsNone(local_resource("a.html", "#symbol", files))

    def test_plain_external_links_do_not_make_automatic_requests(self):
        soup = BeautifulSoup(
            '<a href="https://github.com/nasa/trick">Source</a>'
            '<link rel="canonical" href="https://nasa.github.io/trick/a.html">',
            "html.parser",
        )
        self.assertEqual(check_resources("a.html", soup, set()), [])

    def test_automatic_resources_and_repo_stats_fail(self):
        for html in (
            '<script src="https://cdn.example/script.js"></script>',
            '<link rel="preconnect" href="https://fonts.example">',
            '<link rel="stylesheet" href="https://fonts.example/style.css">',
            '<img srcset="https://images.example/a.png 2x">',
            '<iframe src="https://video.example"></iframe>',
            '<video poster="https://images.example/a.png"></video>',
            '<object data="https://files.example/a.svg"></object>',
            "<style>body {background: url(https://images.example/a.png)}</style>",
            '<div style="background: url(https://images.example/a.png)"></div>',
            '<a href="https://github.com/nasa/trick" data-md-component="source">Repo</a>',
            '<meta http-equiv="refresh" content="0;url=https://example.com">',
        ):
            with self.subTest(html=html):
                self.assertTrue(
                    check_resources("a.html", BeautifulSoup(html, "html.parser"), set())
                )

    def test_css_follows_urls_and_imports_but_ignores_comments(self):
        css = (
            "/* url(ignore.png) */ @import \"a.css\"; @import url('b.css'); "
            'p {background: url(c.png)} i {background: url("data:image/svg+xml,abc")} '
        )
        self.assertEqual(
            css_resources(css), ["a.css", "b.css", "c.png", "data:image/svg+xml,abc"]
        )

    def test_page_contract_and_negative_variants(self):
        html = """<link rel="canonical" href="https://nasa.github.io/trick/a.html">
          <a rel="edit" href="https://github.com/nasa/trick/edit/master/docs/a.md">Edit</a>
          <aside class="md-banner">Development documentation · master</aside>
          <form data-md-component="palette">
            <input aria-label="Dark" data-md-color-scheme="default">
            <input aria-label="Light" data-md-color-scheme="slate">
          </form><meta name="viewport" content="width=device-width">
          <a class="md-skip" href="#main">Skip</a><h1 id="main">Title</h1>"""
        self.assertEqual(
            check_page("a.html", BeautifulSoup(html, "html.parser"), "a.md"), []
        )
        for old, new in (
            ("/trick/a.html", "/a.html"),
            ("/docs/a.md", "/.docs-build/source/a.md"),
            ("master/docs", "main/docs"),
            ("Development documentation", "Stable release"),
            ('scheme="slate"', 'scheme="wrong"'),
            ('name="viewport"', 'name="wrong"'),
            ('href="#main"', 'href="#missing"'),
        ):
            with self.subTest(old=old):
                self.assertTrue(
                    check_page(
                        "a.html",
                        BeautifulSoup(html.replace(old, new), "html.parser"),
                        "a.md",
                    )
                )


if __name__ == "__main__":
    unittest.main()
