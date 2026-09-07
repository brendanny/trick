"""Failure-path tests for the configured simulation evidence gate."""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import baseline as b
import simulation as s


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="icg simulation ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.expected_path = s.HERE / "runtime/templates.expected.json"
        self.expected = json.loads(self.expected_path.read_text())
        self.observed = self.root / "observations.json"
        self.observed.write_bytes(b.json_bytes(self.expected))
        (self.root / "stdout.log").write_text("")
        (self.root / "stderr.log").write_text("")
        self.checkpoint = self.root / "icg_model_checkpoint"
        # Synthetic text is only for testing the collector's completeness checks.
        self.checkpoint.write_text(
            "\n".join([
                "tso.tobj.TTT_var_scalar_builtins.aa = 1000;",
                "tso.tobj.TTT_var_array_builtins.aa = {1, 2};",
                "tso.tobj.TTT_var_enum.aa = Bar_1;",
                "tso.tobj.TTT_var_template_parameters.aa.t = 17;",
            ])
        )

    def test_complete_runtime_evidence_is_digest_recorded(self):
        result = s.validate_runtime(self.root, self.expected_path)
        self.assertEqual(
            result["checkpoint_sha256"], b.digest(self.checkpoint.read_bytes())
        )
        self.assertGreater(result["checkpoint_bytes"], 0)

    def test_wrong_missing_and_boolean_values_are_rejected(self):
        for change in (
            "wrong",
            "missing",
            "boolean",
            "unchanged",
            "time",
            "restore-status",
        ):
            actual = copy.deepcopy(self.expected)
            if change == "wrong":
                actual["restored"]["integer"] = -10
            elif change == "missing":
                del actual["before"]["reals"]
            elif change == "boolean":
                actual["restore_status"] = False
            elif change == "unchanged":
                actual["mutated"] = actual["before"]
            elif change == "time":
                actual["sim_time"] = 0.0
            else:
                actual["restore_status"] = 1
            self.observed.write_bytes(b.json_bytes(actual))
            with self.subTest(change=change), self.assertRaises(b.BaselineError):
                s.validate_runtime(self.root, self.expected_path)

    def test_success_exit_without_runtime_output_is_not_evidence(self):
        self.observed.unlink()
        with self.assertRaises(OSError):
            s.validate_runtime(self.root, self.expected_path)

    def test_empty_partial_and_global_clear_checkpoints_are_rejected(self):
        original = self.checkpoint.read_text()
        for text in ("", "unrelated = 1;", original + "\nclear_all_vars();"):
            self.checkpoint.write_text(text)
            with self.subTest(text=text), self.assertRaises(b.BaselineError):
                s.validate_runtime(self.root, self.expected_path)

    def test_checkpoint_symlink_escape_is_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        target = outside / "checkpoint"
        target.write_text(self.checkpoint.read_text())
        evidence = self.root / "evidence"
        evidence.mkdir()
        (evidence / "observations.json").write_bytes(self.observed.read_bytes())
        (evidence / "stdout.log").write_text("")
        (evidence / "stderr.log").write_text("")
        (evidence / "icg_model_checkpoint").symlink_to(target)
        with self.assertRaises(b.BaselineError):
            s.validate_runtime(evidence, self.expected_path)

    def test_dirty_simulation_is_rejected_without_cleanup(self):
        sim = self.root / "sim"
        sim.mkdir()
        s.require_fresh_simulation(sim)
        for name in ("build", "S_source.hh", "S_main_test.exe"):
            path = sim / name
            path.write_text("existing user output")
            with self.subTest(name=name), self.assertRaises(b.BaselineError):
                s.require_fresh_simulation(sim)
            self.assertEqual(path.read_text(), "existing user output")
            path.unlink()

    def test_missing_ambiguous_and_external_executables_are_rejected(self):
        sim = self.root / "sim"
        sim.mkdir()
        with self.assertRaises(b.BaselineError):
            s.executable(sim)
        first = sim / "S_main_first.exe"
        first.write_text("synthetic executable")
        first.chmod(0o755)
        self.assertEqual(s.executable(sim), first.resolve())
        alias = self.root / "sim-alias"
        alias.symlink_to(sim, target_is_directory=True)
        self.assertEqual(s.executable(alias), first.resolve())
        second = sim / "S_main_second.exe"
        second.symlink_to(first)
        with self.assertRaises(b.BaselineError):
            s.executable(sim)
        second.unlink()
        first.unlink()
        outside = self.root / "outside.exe"
        outside.write_text("synthetic external executable")
        outside.chmod(0o755)
        first.symlink_to(outside)
        with self.assertRaises(b.BaselineError):
            s.executable(sim)

    def test_failed_runtime_does_not_accept_leftover_observations(self):
        output = self.root / "run"
        binary = self.root / "binary"
        binary.write_text("synthetic binary")
        with (
            patch.object(s, "executable", return_value=binary),
            patch.object(b, "measure", return_value={"returncode": 124}),
            patch.object(s, "validate_runtime") as validate,
        ):
            with self.assertRaises(b.BaselineError):
                s.runtime(self.root, output, {}, "/usr/bin/timeout", 1)
            validate.assert_not_called()
        report = json.loads((output / "report.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["measurement"]["returncode"], 124)

    def test_logged_restore_errors_are_not_hidden_by_zero_return_status(self):
        for marker in (
            "Checkpoint restore failed.",
            "Traceback (most recent call last):",
        ):
            (self.root / "stdout.log").write_text(marker)
            (self.root / "stderr.log").write_text("")
            with self.subTest(marker=marker), self.assertRaises(b.BaselineError):
                s.validate_runtime(self.root, self.expected_path)


if __name__ == "__main__":
    unittest.main()
