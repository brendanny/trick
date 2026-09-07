"""Small regression tests, including negative tests against the real generator."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build import require_generated_path, source_files, stage, zensical_command
from check_site import inspect_site, resolve_local
from common import ROOT, html_path, is_helper
from inventory import capture_rendered, explicit_anchors, source_inventory


class PathsAndAnchors(unittest.TestCase):
    def test_workflow_is_valid_and_has_no_deployment_permissions(self):
        workflow = yaml.load(
            (ROOT / ".github/workflows/docs.yml").read_text(), Loader=yaml.BaseLoader
        )
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(
            set(workflow["on"]), {"pull_request", "push", "workflow_dispatch"}
        )
        self.assertEqual(
            workflow["on"]["push"]["branches"], ["master", "zensical-migration"]
        )
        self.assertEqual(set(workflow["jobs"]), {"docs"})
        self.assertNotIn("permissions", workflow["jobs"]["docs"])
        self.assertNotIn("deploy-pages", str(workflow))

    def test_helpers_are_explicit(self):
        self.assertTrue(is_helper("_layouts/default.html"))
        self.assertTrue(is_helper("_Sidebar.md"))
        self.assertFalse(is_helper("not_referenced/design/DesIntegrator.md"))
        self.assertFalse(is_helper("images/_diagram.png"))

    def test_html_path_preserves_case_and_punctuation(self):
        self.assertEqual(html_path("a/GNU-(GSL).md"), "a/GNU-(GSL).html")

    def test_explicit_anchors_ignore_code_examples(self):
        source = '<a id="real"></a>\n<a name="old-style"></a>\n\n# Heading\n\n```html\n<a id="fake"></a>\n```\n\n`<a id="inline-fake"></a>`\n'
        self.assertEqual(explicit_anchors(source), ["old-style", "real"])

    def test_relative_query_and_encoded_fragment(self):
        self.assertEqual(
            resolve_local("a/First.html", "../Second.html?q=1#x%20y", {"Second.html"}),
            ("Second.html", "x y"),
        )

    def test_root_and_extensionless_candidates(self):
        files = {"index.html", "guide.html", "nested/index.html"}
        self.assertEqual(resolve_local("a.html", "/trick", files), ("index.html", ""))
        self.assertEqual(resolve_local("a.html", "guide", files), ("guide.html", ""))
        self.assertEqual(
            resolve_local("a.html", "nested/", files), ("nested/index.html", "")
        )

    def test_markdown_link_is_not_mistaken_for_html(self):
        self.assertEqual(resolve_local("a.html", "b.md", {"b.html"}), ("b.md", ""))

    def test_external_and_outside_project_are_not_read(self):
        for href in [
            "https://example.org/x",
            "mailto:x@example.org",
            "/other/x",
            "/trick/%2e%2e/private",
            "//example.org/x",
        ]:
            self.assertIsNone(resolve_local("a.html", href, set()))


class TemporaryRepo(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "docs").mkdir()
        (self.root / "docs/index.md").write_text('# Start\n\n<a id="kept"></a>\n')
        (self.root / "docs/_config.yml").write_text("markdown: GFM\n")
        (self.root / "docs/_layouts").mkdir()
        (self.root / "docs/_layouts/default.html").write_text("{{ content }}")
        (self.root / "docs/picture.png").write_bytes(b"test asset")

    def commit(self):
        subprocess.run(["git", "-C", str(self.root), "add", "docs"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                "fixture",
            ],
            check=True,
        )

    def test_inventory_records_source_not_fabricated_rendered_ids(self):
        self.commit()
        result = source_inventory(self.root, "HEAD")
        self.assertEqual(len(result["pages"]), 1)
        self.assertEqual(result["pages"][0]["explicit_anchors"], ["kept"])
        self.assertFalse(result["coverage"]["rendered_heading_ids"])
        self.assertEqual(result, source_inventory(self.root, "HEAD"))

    def test_staging_preserves_sources_and_syncs_add_remove_edit(self):
        original = (self.root / "docs/index.md").read_bytes()
        first = stage(self.root)
        target = self.root / ".docs-build/source"
        self.assertFalse((target / "_config.yml").exists())
        self.assertFalse((target / "_layouts").exists())
        self.assertEqual((target / "index.md").read_bytes(), original)
        (self.root / "docs/picture.png").unlink()
        (self.root / "docs/new.md").write_text("# New\n")
        (self.root / "docs/index.md").write_text("# Changed\n")
        stage(self.root, first)
        self.assertFalse((target / "picture.png").exists())
        self.assertEqual((target / "index.md").read_text(), "# Changed\n")
        self.assertTrue((target / "new.md").is_file())
        self.assertTrue((self.root / "docs/_config.yml").is_file())

    def test_generated_directory_guards(self):
        with self.assertRaises(ValueError):
            require_generated_path(self.root, self.root / "docs")
        (self.root / "site").mkdir()
        (self.root / "site/user.txt").write_text("tracked")
        subprocess.run(["git", "-C", str(self.root), "add", "site"], check=True)
        with self.assertRaises(ValueError):
            require_generated_path(self.root, self.root / "site")

    def test_source_symlink_is_rejected(self):
        (self.root / "docs/link.md").symlink_to(self.root / "docs/index.md")
        with self.assertRaises(ValueError):
            source_files(self.root)

    def test_legacy_capture_requires_every_page(self):
        self.commit()
        baseline = source_inventory(self.root, "HEAD")
        output = self.root / "legacy"
        output.mkdir()
        with self.assertRaises(ValueError):
            capture_rendered(baseline, output)
        (output / "index.html").write_text(
            '<h1 id="jekyll-heading">Start</h1><a id="kept"></a>'
        )
        captured = capture_rendered(baseline, output)
        self.assertTrue(captured["coverage"]["rendered_heading_ids"])
        self.assertEqual(
            captured["rendered_capture"][0]["anchors"], ["jekyll-heading", "kept"]
        )
        self.assertFalse(baseline["coverage"]["rendered_heading_ids"])

    def test_built_output_reports_raw_html_and_gates_missing_assets(self):
        self.commit()
        baseline = source_inventory(self.root, "HEAD")
        output = self.root / "output"
        output.mkdir()
        (output / "index.html").write_text(
            '<body><a id="kept"></a><a href="missing.html">bad</a><a href="#gone">bad anchor</a></body>'
        )
        (output / "search.json").write_text('{"fixture": true}')
        result = inspect_site(output, baseline, [])
        self.assertIn("Missing baseline asset: picture.png", result["gate_errors"])
        self.assertEqual(
            {x["kind"] for x in result["migration_findings"]},
            {"missing-target", "missing-fragment"},
        )

    def test_corrupt_asset_and_invalid_search_fail_structural_gate(self):
        self.commit()
        baseline = source_inventory(self.root, "HEAD")
        output = self.root / "output"
        output.mkdir()
        (output / "index.html").write_text('<body><a id="kept"></a></body>')
        (output / "picture.png").write_bytes(b"corrupted asset")
        (output / "search.json").write_text('{"items": []}')
        result = inspect_site(output, baseline, [])
        self.assertIn("Changed baseline asset: picture.png", result["gate_errors"])
        self.assertIn("Empty or invalid built-in search index", result["gate_errors"])

    def test_missing_page_and_explicit_anchor_fail_structural_gate(self):
        self.commit()
        baseline = source_inventory(self.root, "HEAD")
        output = self.root / "output"
        output.mkdir()
        result = inspect_site(output, baseline, [])
        self.assertIn("Missing baseline page: index.html", result["gate_errors"])
        (output / "index.html").write_text("<body>Anchor was lost</body>")
        result = inspect_site(output, baseline, [])
        self.assertIn("Missing explicit anchor: index.html#kept", result["gate_errors"])


class RealZensical(unittest.TestCase):
    def build_fixture(self, text):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs/index.md").write_text(text)
            (root / "zensical.toml").write_text(
                '[project]\nsite_name="Validation fixture"\ndocs_dir="docs"\nsite_dir="site"\nuse_directory_urls=false\n'
                "[project.theme]\nfont=false\n"
                "[project.validation]\ninvalid_links=true\ninvalid_link_anchors=true\n"
            )
            result = subprocess.run(
                zensical_command("build", "--clean", "--strict"),
                cwd=root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result

    def test_valid_fixture(self):
        result = self.build_fixture("# Start\n\n[Heading](#start)\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_invalid_page_fails_strict_build(self):
        result = self.build_fixture("# Start\n\n[Missing](missing.md)\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not exist", result.stdout + result.stderr)

    def test_invalid_anchor_fails_strict_build(self):
        result = self.build_fixture("# Start\n\n[Missing](#not-an-anchor)\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("anchor does not exist", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
