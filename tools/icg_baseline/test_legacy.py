"""Legacy capture plumbing and integrity checks for actual checked-in evidence."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import baseline as b
import legacy


class LegacyCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="legacy evidence ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "header.hh").write_text("struct Model { int field; };\n")
        self.case = {"id": "model", "header": "header.hh"}
        self.manifest = {
            "schema_version": 1,
            "scope": "isolated-legacy-headers",
            "cases": [self.case],
            "artifacts": [
                {"id": "metadata", "required": True, "patterns": ["build/io_*.cpp"]}
            ],
        }
        self.manifest_path = self.root / "corpus.json"

    def load(self):
        self.manifest_path.write_bytes(b.json_bytes(self.manifest))
        return legacy.load_corpus(self.manifest_path, self.root)

    def test_header_corpus_does_not_pretend_to_have_sdefine(self):
        self.assertEqual(self.load(), self.manifest)
        self.assertFalse((self.root / "S_define").exists())

    def test_invalid_duplicate_or_traversing_ids_are_rejected(self):
        for name in ("..", "../escape", "/absolute", "with space", ""):
            with self.subTest(name=name):
                self.case["id"] = name
                with self.assertRaises(b.BaselineError):
                    self.load()
        self.case["id"] = "model"
        self.manifest["cases"].append(self.case)
        with self.assertRaises(b.BaselineError):
            self.load()

    def test_missing_and_escaping_headers_are_rejected(self):
        for name in ("absent.hh", "../outside.hh", "/absolute.hh"):
            self.case["header"] = name
            with self.assertRaises(b.BaselineError):
                self.load()

    def test_escaping_artifact_globs_are_rejected(self):
        for pattern in ("../*.cpp", "/tmp/*.cpp"):
            self.manifest["artifacts"][0]["patterns"] = [pattern]
            with self.assertRaises(b.BaselineError):
                self.load()

    def test_header_path_cannot_inject_a_translation_unit(self):
        self.case["header"] = 'header.hh"\n#error injected'
        with self.assertRaisesRegex(b.BaselineError, "C\\+\\+ include"):
            self.load()

    def test_empty_and_wrong_scope_corpora_are_rejected(self):
        self.manifest["scope"] = "simulation"
        with self.assertRaises(b.BaselineError):
            self.load()
        self.manifest["scope"] = "isolated-legacy-headers"
        self.manifest["cases"] = []
        with self.assertRaises(b.BaselineError):
            self.load()

    def test_ambient_trick_policy_is_not_inherited(self):
        with patch.dict(
            os.environ,
            {
                "TRICK_ICG_EXCLUDE": "/everything",
                "TRICK_ICG_COMPAT15": "1",
                "TRICK_CXX": "bad; command",
                "CPATH": "/injected",
            },
        ):
            env = legacy.environment(self.root, Path("/usr/bin/c++"))
        self.assertNotIn("TRICK_ICG_EXCLUDE", env)
        self.assertNotIn("TRICK_ICG_COMPAT15", env)
        self.assertNotIn("CPATH", env)
        self.assertEqual(env["TRICK_CXX"], "/usr/bin/c++")
        self.assertEqual(env["TRICK_HOME"], str(self.root))

    def run_pass(self, command):
        work, output = self.root / "work", self.root / "capture"
        (work / "build").mkdir(parents=True)
        # Synthetic stale text tests the harness only, not legacy behavior.
        (work / "build/io_stale.cpp").write_text("stale output\n")
        code = legacy.run_pass(
            self.manifest,
            self.case,
            self.root,
            work,
            output,
            command,
            dict(os.environ),
            "cold",
        )
        return code, output

    def test_failed_command_never_publishes_stale_snapshot(self):
        code, output = self.run_pass([sys.executable, "-c", "raise SystemExit(7)"])
        self.assertEqual(code, 3)
        self.assertFalse((output / "snapshot.json").exists())
        report = json.loads((output / "report.json").read_text())
        self.assertEqual(report["status"], "command_failed")
        self.assertEqual(report["measurement"]["returncode"], 7)

    def test_missing_required_outputs_are_not_success(self):
        self.manifest["artifacts"][0]["patterns"] = ["build/missing.cpp"]
        with self.assertRaises(b.BaselineError):
            self.run_pass([sys.executable, "-c", "pass"])
        output = self.root / "capture"
        self.assertFalse((output / "snapshot.json").exists())
        self.assertEqual(
            json.loads((output / "report.json").read_text())["status"],
            "capture_failed",
        )

    def test_worker_receives_explicit_environment(self):
        output = self.root / "measure"
        output.mkdir()
        env = dict(os.environ, TRICK_ICG_EXCLUDE="explicit-test-value")
        result = b.measure(
            [sys.executable, "-c", "import os; print(os.environ['TRICK_ICG_EXCLUDE'])"],
            self.root,
            output,
            env=env,
        )
        self.assertEqual(result["returncode"], 0)
        self.assertEqual((output / "stdout.log").read_text(), "explicit-test-value\n")


class LegacyReferenceTests(unittest.TestCase):
    """These assertions inspect real legacy-generated bytes, not invented output."""

    def setUp(self):
        self.root = legacy.HERE / "legacy/reference"
        self.manifest = legacy.load_corpus(legacy.MANIFEST, legacy.ROOT)

    def snapshot(self, case, label="cold"):
        path = self.root / case / f"{label}.json"
        return path, json.loads(path.read_text())

    def texts(self, case, group):
        path, snapshot = self.snapshot(case)
        return "".join(
            b.artifact_text(path, item)
            for item in snapshot["artifacts"].values()
            if item["group"] == group
        )

    def test_all_twelve_snapshots_have_intact_sidecars_and_expected_scope(self):
        for case in self.manifest["cases"]:
            for label in legacy.PASSES:
                with self.subTest(case=case["id"], label=label):
                    path, snapshot = self.snapshot(case["id"], label)
                    self.assertEqual(
                        snapshot["artifact_spec"], self.manifest["artifacts"]
                    )
                    self.assertEqual(snapshot["case"], case["id"])
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(b.compare(path, path), 0)
                    groups = {a["group"] for a in snapshot["artifacts"].values()}
                    for group in self.manifest["artifacts"]:
                        if group["required"]:
                            self.assertIn(group["id"], groups)

    def test_warm_contents_equal_and_forced_sie_appends_are_preserved(self):
        for case in self.manifest["cases"]:
            cold_path, cold = self.snapshot(case["id"])
            _, warm = self.snapshot(case["id"], "warm")
            forced_path, forced = self.snapshot(case["id"], "forced")
            self.assertEqual(cold, warm)
            changed = [
                name
                for name, item in cold["artifacts"].items()
                if item != forced["artifacts"][name]
            ]
            self.assertEqual(changed, ["build/classes.resource"])
            name = changed[0]
            self.assertEqual(
                b.artifact_text(forced_path, forced["artifacts"][name]),
                2 * b.artifact_text(cold_path, cold["artifacts"][name]),
            )

    def test_comparison_records_differences_between_digest_valid_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "comparison.diff"
            cold, _ = self.snapshot("embedded")
            forced, _ = self.snapshot("embedded", "forced")
            self.assertFalse(legacy.compare_to_file(cold, forced, log))
            self.assertIn("changed: build/classes.resource", log.read_text())

    def test_deleted_constructor_keeps_legacy_calloc_without_placement_new(self):
        text = self.texts("deleted-constructor", "legacy-metadata")
        self.assertIn("ATTRIBUTES attrEmpty[]", text)
        self.assertIn("calloc(num, sizeof(Empty))", text)
        self.assertNotIn("new(&temp[ii]) Empty()", text)
        self.assertIn(
            "new(&temp[ii]) Starter()", self.texts("anonymous-enum", "legacy-metadata")
        )

    def test_units_bitfields_and_exclusions_are_real_legacy_evidence(self):
        text = self.texts("embedded", "legacy-metadata")
        self.assertIn('{"d", "double", "rad"', text)
        self.assertIn("TRICK_UNSIGNED_BITFIELD", text)
        self.assertNotIn("attrIgnoreType1", text)
        self.assertNotIn("attrTopClass__PrivateEmbed", text)
        self.assertIn("ENUM_ATTR enumTopClass__PublicEnum[]", text)
        self.assertIn("init_attrTopClass_c_intf", text)


if __name__ == "__main__":
    unittest.main()
