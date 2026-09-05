"""Harness regression tests. Synthetic files here are NOT legacy ICG baselines."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import baseline as b


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="icg baseline ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "checkout"
        self.sim = self.root / "test/SIM_fixture"
        self.sim.mkdir(parents=True)
        self.source = self.sim / "S_define"
        self.source.write_text("// synthetic input\n")
        self.case = {
            "id": "fixture",
            "directory": "test/SIM_fixture",
            "covers": ["harness"],
        }
        self.manifest = {
            "schema_version": 1,
            "cases": [self.case],
            "artifacts": [
                {"id": "metadata", "required": True, "patterns": ["build/**/io_*.cpp"]},
                {"id": "lists", "required": False, "patterns": ["build/io_link_list"]},
            ],
        }
        self.manifest_path = self.base / "corpus.json"
        self.manifest_path.write_bytes(b.json_bytes(self.manifest))
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Harness Test",
                "-c",
                "user.email=harness@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "fixture",
            ],
            check=True,
        )

    def artifact(
        self, text="ATTRIBUTES attrFixture[] = {};\n", relative="build/io_fixture.cpp"
    ):
        path = self.sim / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = b.main([
                "--root",
                str(self.root),
                "--manifest",
                str(self.manifest_path),
                *map(str, args),
            ])
        return code, stdout.getvalue(), stderr.getvalue()

    def capture(self, name):
        output = self.base / name
        result = self.cli("capture", "--case", "fixture", "--output", output)
        self.assertEqual(result[0], 0, result)
        return output / "snapshot.json"

    def test_manifest_rejects_duplicate_case_and_escape(self):
        for cases in (
            [self.case, self.case],
            [dict(self.case, directory="../outside")],
        ):
            self.manifest_path.write_bytes(
                b.json_bytes(dict(self.manifest, cases=cases))
            )
            self.assertEqual(self.cli("list")[0], 2)

    def test_manifest_rejects_unknown_version_and_missing_input(self):
        self.manifest_path.write_bytes(
            b.json_bytes(dict(self.manifest, schema_version=99))
        )
        self.assertEqual(self.cli("list")[0], 2)
        self.manifest_path.write_bytes(b.json_bytes(self.manifest))
        self.source.unlink()
        self.assertEqual(self.cli("list")[0], 2)

    def test_path_normalization_preserves_semantic_text_and_order(self):
        text = (
            f'#include "{self.sim}/model.hh"\n{self.root}/include/trick/attributes.h\n'
        )
        text += f'{self.root}-other/model.hh\n"m/s"\n{{"b", 8}},\n{{"a", 4}},\n'
        normalized = b.normalize(text, self.root, self.sim)
        self.assertIn("${SIM_ROOT}/model.hh", normalized)
        self.assertIn("${TRICK_ROOT}/include/trick/attributes.h", normalized)
        self.assertIn(f"{self.root}-other/model.hh", normalized)
        self.assertTrue(normalized.endswith('"m/s"\n{"b", 8},\n{"a", 4},\n'))

    def test_same_normalized_snapshot_across_checkout_roots(self):
        def make_snapshot(root):
            sim = root / self.case["directory"]
            sim.mkdir(parents=True, exist_ok=True)
            path = sim / f"build{sim}/io_fixture.cpp"
            path.parent.mkdir(parents=True)
            path.write_text(
                f'#include "{sim}/model.hh"\n#include "{root}/include/header.hh"\n'
            )
            return b.snapshot(
                self.manifest, self.case, b.collect(self.manifest, root, self.case)
            )

        self.assertEqual(
            make_snapshot(self.root), make_snapshot(self.base / "other checkout")
        )

    def test_normalization_accepts_spelled_and_resolved_symlink_roots(self):
        alias = self.base.resolve() / "linked checkout"
        alias.symlink_to(self.root.resolve(), target_is_directory=True)
        sim_alias = alias / self.case["directory"]
        text = (
            f"{sim_alias}/model.hh\n{self.sim.resolve()}/model.hh\n"
            f"{alias}/include/header.hh\n{self.root.resolve()}/include/header.hh\n"
            f"build{sim_alias}/io_fixture.cpp\n"
            f"{alias}-other/model.hh\n"
        )
        self.assertEqual(
            b.normalize(text, alias, sim_alias),
            "${SIM_ROOT}/model.hh\n${SIM_ROOT}/model.hh\n"
            "${TRICK_ROOT}/include/header.hh\n${TRICK_ROOT}/include/header.hh\n"
            "build${SIM_ROOT}/io_fixture.cpp\n"
            f"{alias}-other/model.hh\n",
        )

    def test_capture_preserves_configured_symlink_spelling(self):
        alias = self.base.resolve() / "linked checkout"
        alias.symlink_to(self.root.resolve(), target_is_directory=True)
        sim_alias = alias / self.case["directory"]
        path = self.artifact(
            f'#include "{sim_alias}/model.hh"\n'
            f'#include "{self.root.resolve()}/include/header.hh"\n',
            f"build{sim_alias}/io_fixture.cpp",
        )
        self.root = alias
        aliased = self.capture("aliased")
        path.unlink()
        self.root = alias.resolve()
        self.artifact(
            f'#include "{self.sim.resolve()}/model.hh"\n'
            f'#include "{self.root}/include/header.hh"\n',
            f"build{self.sim.resolve()}/io_fixture.cpp",
        )
        resolved = self.capture("resolved")
        self.assertEqual(self.cli("compare", aliased, resolved)[0], 0)
        data = json.loads(aliased.read_text())
        self.assertIn("build${SIM_ROOT}/io_fixture.cpp", data["artifacts"])

    def test_atomic_writer_does_not_touch_identical_output(self):
        path = self.base / "nested/result.json"
        b.write_changed(path, b"first")
        os.utime(path, ns=(1_000_000, 1_000_000))
        b.write_changed(path, b"first")
        self.assertEqual(path.stat().st_mtime_ns, 1_000_000)
        b.write_changed(path, b"second")
        self.assertEqual(path.read_bytes(), b"second")
        self.assertEqual(list(path.parent.iterdir()), [path])

    def test_missing_required_artifact_cannot_succeed(self):
        output = self.base / "missing"
        self.assertEqual(
            self.cli("capture", "--case", "fixture", "--output", output)[0], 2
        )
        self.assertFalse((output / "snapshot.json").exists())
        self.assertEqual(
            json.loads((output / "report.json").read_text())["status"], "capture_failed"
        )

    def test_invalid_utf8_is_not_silently_discarded(self):
        self.artifact().write_bytes(b"\xff")
        self.assertEqual(
            self.cli("capture", "--case", "fixture", "--output", self.base / "binary")[
                0
            ],
            2,
        )

    def test_symlink_escape_is_rejected(self):
        outside = self.base / "outside.cpp"
        outside.write_text("secret")
        path = self.artifact()
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaises(b.BaselineError):
            b.collect(self.manifest, self.root, self.case)

    def test_duplicate_artifact_group_membership_is_rejected(self):
        self.artifact()
        self.manifest["artifacts"].append({
            "id": "duplicate",
            "patterns": ["build/*.cpp"],
        })
        with self.assertRaises(b.BaselineError):
            b.collect(self.manifest, self.root, self.case)

    def test_compare_detects_offsets_order_additions_and_deletions(self):
        path = self.artifact('{"first", 4},\n{"second", 8}\n')
        old = self.capture("old")
        self.assertEqual(self.cli("compare", old, old)[0], 0)
        path.write_text('{"second", 8},\n{"first", 16}\n')
        self.artifact("object.o\n", "build/io_link_list")
        new = self.capture("new")
        code, output, _ = self.cli("compare", old, new)
        self.assertEqual(code, 1)
        self.assertIn('+{"first", 16}', output)
        self.assertIn("added: build/io_link_list", output)
        self.assertIn("removed: build/io_link_list", self.cli("compare", new, old)[1])

    def test_comparison_rejects_corrupt_or_incompatible_evidence(self):
        self.artifact()
        old = self.capture("valid")
        data = json.loads(old.read_text())
        bad = self.base / "bad.json"
        for key, value in (
            ("schema_version", 99),
            ("case", "other"),
            ("artifacts", {}),
        ):
            bad.write_bytes(b.json_bytes(dict(data, **{key: value})))
            self.assertEqual(self.cli("compare", old, bad)[0], 2)
        data["artifacts"]["build/io_fixture.cpp"]["text"] += "corruption"
        bad.write_bytes(b.json_bytes(data))
        self.assertEqual(self.cli("compare", old, bad)[0], 2)

    def test_churn_separates_rewrites_from_content_changes(self):
        path = self.artifact()
        os.utime(path, ns=(1_000_000, 1_000_000))
        before = b.collect(self.manifest, self.root, self.case)
        self.artifact()
        after = b.collect(self.manifest, self.root, self.case)
        self.assertEqual(
            b.churn(before, after)["rewritten_unchanged"], ["build/io_fixture.cpp"]
        )
        self.artifact("changed")
        after = b.collect(self.manifest, self.root, self.case)
        self.assertEqual(
            b.churn(before, after)["content_changed"], ["build/io_fixture.cpp"]
        )

    def test_run_preserves_argv_and_measures_noop(self):
        path = self.artifact()
        os.utime(path, ns=(1_000_000, 1_000_000))
        output = self.base / "run with spaces"
        literal = "spaces ; $(no-shell) `literal`"
        code, _, error = self.cli(
            "run",
            "--case",
            "fixture",
            "--output",
            output,
            "--stage",
            "harness",
            "--label",
            "warm",
            "--",
            sys.executable,
            "-c",
            "import sys; print(sys.argv[1])",
            literal,
        )
        self.assertEqual(code, 0, error)
        self.assertEqual((output / "stdout.log").read_text(), literal + "\n")
        report = json.loads((output / "report.json").read_text())
        self.assertEqual(report["measurement"]["argv"][-1], literal)
        self.assertGreater(report["measurement"]["max_rss_bytes"], 0)
        self.assertGreater(report["measurement"]["wall_seconds"], 0)
        self.assertTrue(all(not value for value in report["churn"].values()))

    def test_failed_command_keeps_logs_but_no_snapshot(self):
        self.artifact()  # Stale success output must not make a failed command pass.
        output = self.base / "failure"
        result = self.cli(
            "run",
            "--case",
            "fixture",
            "--output",
            output,
            "--stage",
            "icg",
            "--label",
            "cold",
            "--",
            sys.executable,
            "-c",
            "import sys; print('parse failed', file=sys.stderr); sys.exit(7)",
        )
        self.assertEqual(result[0], 3)
        report = json.loads((output / "report.json").read_text())
        self.assertEqual(report["measurement"]["returncode"], 7)
        self.assertEqual(report["status"], "command_failed")
        self.assertIn("parse failed", (output / "stderr.log").read_text())
        self.assertFalse((output / "snapshot.json").exists())

    def test_missing_executable_is_recorded(self):
        output = self.base / "no-executable"
        result = self.cli(
            "run",
            "--case",
            "fixture",
            "--output",
            output,
            "--stage",
            "icg",
            "--label",
            "cold",
            "--",
            str(self.base / "missing-command"),
        )
        self.assertEqual(result[0], 3)
        report = json.loads((output / "report.json").read_text())
        self.assertEqual(report["measurement"]["returncode"], 127)
        self.assertIsNotNone(report["measurement"]["error"])

    def test_capture_refuses_to_overwrite_evidence(self):
        self.artifact()
        path = self.capture("existing")
        before = path.read_bytes()
        self.assertEqual(
            self.cli("capture", "--case", "fixture", "--output", path.parent)[0], 2
        )
        self.assertEqual(before, path.read_bytes())

    def test_evidence_directory_cannot_pollute_simulation(self):
        self.artifact()
        self.assertEqual(
            self.cli(
                "capture", "--case", "fixture", "--output", self.sim / "build/report"
            )[0],
            2,
        )

    def test_provenance_records_modified_inputs_not_arbitrary_environment(self):
        self.source.write_text("// edited input\n")
        os.environ["ICG_TEST_SECRET"] = "not-for-evidence"
        self.addCleanup(os.environ.pop, "ICG_TEST_SECRET")
        value = b.provenance(self.root, self.case, self.manifest_path)
        self.assertIn("S_define", value["git_status"])
        self.assertEqual(
            value["tracked_simulation_inputs"]["test/SIM_fixture/S_define"],
            b.digest(self.source.read_bytes()),
        )
        self.assertNotIn("ICG_TEST_SECRET", value["environment"])

    def test_checked_in_manifest_references_real_simulations(self):
        manifest = b.load_manifest(b.HERE / "corpus.json", b.DEFAULT_ROOT)
        self.assertGreaterEqual(len(manifest["cases"]), 12)

    def test_checked_in_artifact_patterns_do_not_overlap(self):
        manifest = json.loads((b.HERE / "corpus.json").read_text())
        for group in manifest["artifacts"]:
            for pattern in group["patterns"]:
                relative = pattern.replace("**/", "nested/").replace("*", "example")
                self.artifact("synthetic output\n", relative)
        artifacts = b.collect(manifest, self.root, self.case)
        self.assertEqual(
            {a["group"] for a in artifacts.values()},
            {g["id"] for g in manifest["artifacts"]},
        )


if __name__ == "__main__":
    unittest.main()
