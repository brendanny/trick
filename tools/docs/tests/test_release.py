"""Exercise actual candidate archives and fail-closed publishing policy offline."""

import copy
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build import source_files
from check_site import load_baseline
from common import ROOT
from external_links import audit, audit_url
from release import (
    LEGACY_GATES,
    QUERIES,
    REVIEWS,
    digest,
    package,
    safe_name,
    unpack,
    validate_approval,
    validate_reports,
    validate_run,
)


def approval_for(source, checksum):
    return {
        "schema_version": 1,
        "source_commit": source,
        "site_tar_sha256": checksum,
        "reviews": {
            name: {
                "status": "passed",
                "reviewer": "Synthetic test reviewer",
                "evidence": "https://example.invalid/test-evidence",
            }
            for name in REVIEWS
        },
        "rollback": {
            "source_commit": "b" * 40,
            "artifact_sha256": "c" * 64,
            "artifact_url": "https://example.invalid/test-rollback",
            "rehearsal_evidence": "https://example.invalid/test-rehearsal",
        },
    }


class PublishingPolicy(unittest.TestCase):
    def test_checked_in_approval_does_not_authorize_a_release(self):
        approval = json.loads((ROOT / "tools/docs/release-approval.json").read_text())
        with self.assertRaises(ValueError):
            validate_approval(approval, "a" * 40, "d" * 64)

    def test_approval_is_exact_and_every_review_and_rollback_is_required(self):
        source, checksum = "a" * 40, "d" * 64
        approval = approval_for(source, checksum)
        validate_approval(approval, source, checksum)
        for key, value in (("source_commit", "b" * 40), ("site_tar_sha256", "b" * 64)):
            with self.assertRaises(ValueError):
                validate_approval({**approval, key: value}, source, checksum)
        for name in REVIEWS:
            for key, value in (
                ("status", "pending"),
                ("reviewer", ""),
                ("evidence", None),
            ):
                broken = copy.deepcopy(approval)
                broken["reviews"][name][key] = value
                with self.assertRaises(ValueError):
                    validate_approval(broken, source, checksum)
        for key in approval["rollback"]:
            broken = copy.deepcopy(approval)
            broken["rollback"][key] = None
            with self.assertRaises(ValueError):
                validate_approval(broken, source, checksum)

    def test_only_successful_upstream_master_push_run_is_trusted(self):
        run = {
            "id": 123,
            "repository": {"full_name": "nasa/trick"},
            "head_repository": {"full_name": "nasa/trick"},
            "path": ".github/workflows/docs.yml",
            "event": "push",
            "head_branch": "master",
            "head_sha": "a" * 40,
            "status": "completed",
            "conclusion": "success",
        }
        validate_run(run, "123", "a" * 40)
        for key, value in (
            ("id", 124),
            ("repository", {"full_name": "brendanny/trick"}),
            ("head_repository", {"full_name": "someone/trick"}),
            ("path", ".github/workflows/untrusted.yml"),
            ("event", "pull_request"),
            ("event", "workflow_dispatch"),
            ("head_branch", "zensical-migration"),
            ("head_sha", "b" * 40),
            ("status", "in_progress"),
            ("conclusion", "failure"),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_run({**run, key: value}, "123", "a" * 40)
        for invalid in ("../123", "1; echo bad", "-1", "0"):
            with self.assertRaises(ValueError):
                validate_run(run, invalid, "a" * 40)

    def test_workflow_separates_read_only_promotion_and_protected_deployment(self):
        workflow = yaml.load(
            (ROOT / ".github/workflows/docs-publish.yml").read_text(),
            Loader=yaml.BaseLoader,
        )
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(
            workflow["concurrency"],
            {"group": "documentation-pages-production", "cancel-in-progress": "false"},
        )
        prepare, deploy = (workflow["jobs"][name] for name in ("prepare", "deploy"))
        self.assertEqual(
            prepare["permissions"], {"contents": "read", "actions": "read"}
        )
        self.assertEqual(deploy["permissions"], {"pages": "write", "id-token": "write"})
        self.assertEqual(deploy["needs"], "prepare")
        self.assertEqual(deploy["environment"]["name"], "github-pages")
        for job in (prepare, deploy):
            self.assertEqual(
                " ".join(job["if"].split()),
                "github.event_name == 'workflow_dispatch' && github.repository == 'nasa/trick' && github.ref == 'refs/heads/master' && vars.DOCS_PAGES_ENABLED == 'true'",
            )
            for step in job["steps"]:
                if "uses" in step:
                    self.assertRegex(step["uses"], r"^actions/[a-z-]+@[0-9a-f]{40}$")
                self.assertNotIn("${{", step.get("run", ""))
        self.assertEqual(len(deploy["steps"]), 1)
        self.assertTrue(deploy["steps"][0]["uses"].startswith("actions/deploy-pages@"))
        self.assertNotIn("build.py", str(prepare))
        self.assertNotIn("pull_request_target", workflow["on"])

    def test_source_collisions_fail_before_rendering(self):
        for names in (
            ("guide.md", "guide.html"),
            ("Guide.md", "guide.md"),
            ("a.md", "a.html/b.png"),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for name in ("index.md", *names):
                    path = root / "docs" / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("fixture")
                with self.assertRaisesRegex(ValueError, "collision"):
                    source_files(root)

    def test_supplemental_evidence_cannot_change_the_legacy_contract(self):
        original = json.loads((ROOT / "tools/docs/legacy-routes.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.json"
            for key in ("source_commit", "pages", "assets", "helpers"):
                path.write_text(json.dumps({**original, key: []}))
                with self.assertRaises(ValueError):
                    load_baseline(path)
            broken = copy.deepcopy(original)
            broken["coverage"]["rendered_heading_ids"] = True
            path.write_text(json.dumps(broken))
            with self.assertRaises(ValueError):
                load_baseline(path)


class CandidateArchives(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "tools/docs").mkdir(parents=True)
        (self.root / "tools/docs/requirements.txt").write_text("synthetic test lock\n")
        (self.root / ".gitignore").write_text("site/\n.docs-build/\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Docs test",
                "-c",
                "user.email=docs@example.invalid",
                "commit",
                "-qm",
                "Synthetic candidate fixture",
            ],
            cwd=self.root,
            check=True,
        )
        (self.root / "site").mkdir()
        for name in ("index.html", "404.html", "search.json"):
            (self.root / "site" / name).write_text("Synthetic " + name)
        (self.root / ".docs-build").mkdir()
        self.reports = {
            "corpus": {
                "gate_errors": [],
                "migration_findings": [],
                "legacy_coverage": dict.fromkeys(LEGACY_GATES, True),
            },
            "experience": {"errors": [], "nav_pages": 1},
            "search": {
                "checks": [
                    {"query": query, "rank": 1, "max_rank": 3}
                    for query in sorted(QUERIES)
                ],
                "negative_fixtures": 4,
            },
        }
        for key, name in (
            ("corpus", "report"),
            ("experience", "experience-report"),
            ("search", "search-report"),
        ):
            (self.root / ".docs-build" / (name + ".json")).write_text(
                json.dumps(self.reports[key])
            )
        self.manifest = package(self.root)
        self.bundle = self.root / ".docs-build/candidate"
        self.output = self.root / ".docs-build/publish"
        self.source = self.manifest["source_commit"]
        self.checksum = self.manifest["site_tar_sha256"]
        self.approval = approval_for(self.source, self.checksum)

    def promote(self):
        unpack(self.bundle, self.output, self.source, self.checksum, self.approval)

    def test_round_trip_preserves_every_byte_and_tar_is_deterministic(self):
        self.promote()
        for name in self.manifest["files"]:
            self.assertEqual(
                (self.root / "site" / name).read_bytes(),
                (self.output / name).read_bytes(),
            )
        self.bundle.rename(self.bundle.with_name("previous-candidate"))
        self.assertEqual(package(self.root)["site_tar_sha256"], self.checksum)

    def test_changed_archive_and_member_manifest_are_rejected_before_output(self):
        with (self.bundle / "site.tar").open("ab") as stream:
            stream.write(b"tampered")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.promote()
        self.assertFalse(self.output.exists())

    def test_failed_reports_missing_search_and_legacy_evidence_are_rejected(self):
        for key in LEGACY_GATES:
            broken = copy.deepcopy(self.reports)
            broken["corpus"]["legacy_coverage"][key] = "true"
            with self.assertRaises(ValueError):
                validate_reports(broken, release=True)
        for group, key, value in (
            ("corpus", "gate_errors", ["broken"]),
            ("corpus", "migration_findings", ["broken"]),
            ("experience", "errors", ["broken"]),
            ("search", "checks", []),
        ):
            broken = copy.deepcopy(self.reports)
            broken[group][key] = value
            with self.assertRaises(ValueError):
                validate_reports(broken)

    def test_missing_or_changed_manifested_file_is_rejected(self):
        for files in (
            {**self.manifest["files"], "missing.html": "0" * 64},
            {**self.manifest["files"], "index.html": "0" * 64},
        ):
            (self.bundle / "candidate.json").write_text(
                json.dumps({**self.manifest, "files": files})
            )
            with self.assertRaises(ValueError):
                self.promote()
            self.assertFalse(self.output.exists())

    def test_unsafe_archive_members_are_rejected_even_with_matching_checksum(self):
        for name, kind in (
            ("../escape", tarfile.REGTYPE),
            ("/absolute", tarfile.REGTYPE),
            ("link", tarfile.SYMTYPE),
            ("hard", tarfile.LNKTYPE),
            ("pipe", tarfile.FIFOTYPE),
            (".git/config", tarfile.REGTYPE),
            ("_config.yml", tarfile.REGTYPE),
        ):
            with tarfile.open(self.bundle / "site.tar", "w") as tar:
                entry = tarfile.TarInfo(name)
                entry.type, entry.size = kind, 0
                tar.addfile(entry, io.BytesIO(b""))
            self.checksum = digest(self.bundle / "site.tar")
            self.approval = approval_for(self.source, self.checksum)
            manifest = {**self.manifest, "site_tar_sha256": self.checksum}
            (self.bundle / "candidate.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                self.promote()
            self.assertFalse(self.output.exists())
        for name in ("a/./b", "a//b", "a\\b", "a\nb", ""):
            self.assertFalse(safe_name(name))

    def test_packaging_rejects_dirty_source_existing_candidate_and_symlinks(self):
        with self.assertRaisesRegex(ValueError, "already exists"):
            package(self.root)
        (self.root / "site/link").symlink_to("index.html")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            package(self.root)
        (self.root / "tools/docs/requirements.txt").write_text("changed")
        with self.assertRaisesRegex(ValueError, "clean committed"):
            package(self.root)


class ExternalLinkAudit(unittest.TestCase):
    def test_audit_is_bounded_and_exceptions_require_reasons(self):
        with patch("external_links.subprocess.run") as run:
            report = audit(["https://example.com/a"], {}, budget=0)
            self.assertEqual(report["results"][0]["status"], "not-checked")
            run.assert_not_called()
            report = audit(
                ["https://example.com/a"],
                {"https://example.com/a": "Manual review: requires login"},
            )
            self.assertEqual(report["results"][0]["status"], "exception")
            run.assert_not_called()
            run.return_value = subprocess.CompletedProcess([], 0, "301", "")
            self.assertEqual(
                audit(["https://example.com/a"], {})["results"][0]["status"], "redirect"
            )
            command = run.call_args.args[0]
            self.assertIn("--head", command)
            self.assertNotIn("--location", command)
        with self.assertRaises(ValueError):
            audit([], {"https://example.com": ""})

    def test_only_eligible_external_urls_are_audited(self):
        self.assertEqual(audit_url("https://example.com/a#b"), "https://example.com/a")
        for url in (
            "https://nasa.github.io/trick/index.html",
            "mailto:a@example.com",
            "https://localhost/a",
            "http://127.0.0.1/a",
            "http://[::1]/a",
            "https://user:pass@example.com/a",
            "https://a.local/a",
            "https://example.com:bad/a",
        ):
            self.assertIsNone(audit_url(url))


if __name__ == "__main__":
    unittest.main()
