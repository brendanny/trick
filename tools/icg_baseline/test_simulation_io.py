"""Rejection tests for the real-runtime I/O evidence contract."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

import baseline as b
import simulation as s


class IORuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="icg io ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.expected_path = s.HERE / "runtime/io.expected.json"
        self.expected = json.loads(self.expected_path.read_text())
        self.observations = self.root / "observations.json"
        self.observations.write_bytes(b.json_bytes(self.expected))
        self.diagnostics = json.loads(
            (s.HERE / "runtime/io.expected-diagnostics.json").read_text()
        )
        # Synthetic logs/checkpoint test the collector; CI runs the actual sim.
        (self.root / "stdout.log").write_text(
            "\n".join(
                f"|L 2|time|host| |T 0|0.1| \x1b[33m{message}\x1b[00m"
                for message in self.diagnostics[:-1]
            )
        )
        (self.root / "stderr.log").write_text(f"MemoryManager:{self.diagnostics[-1]}\n")
        self.checkpoint = self.root / "icg_model_checkpoint"
        self.checkpoint.write_text(
            "/* OUTPUT-ONLY: test_io.d4 = 204;*/\n"
            "/* OUTPUT-ONLY: test_io.d5 = 205;*/\n"
            "/* OUTPUT-ONLY: test_io.d6 = 306;*/\n"
            "/* OUTPUT-ONLY: test_io.d7 = 307;*/\n"
            "test_io.d12 = 212;\n"
            "test_io.d13 = 213;\n"
            "test_io.d14 = 314;\n"
            "test_io.d15 = 315;\n"
        )

    def validate(self):
        return s.validate_runtime(self.root, self.expected_path, "io")

    def test_complete_io_contract_is_digest_recorded(self):
        result = self.validate()
        self.assertEqual(
            result["checkpoint_sha256"], b.digest(self.checkpoint.read_bytes())
        )

    def test_output_permission_or_value_corruption_is_rejected(self):
        original = self.checkpoint.read_text()
        for text in (
            original.replace("test_io.d12 = 212;", ""),
            original + "test_io.d0 = 200;\n",
            original + "test_io.d12 = 212;\n",
            original.replace(
                "/* OUTPUT-ONLY: test_io.d4 = 204;*/", "test_io.d4 = 204;"
            ),
            original.replace(
                "test_io.d12 = 212;", "/* OUTPUT-ONLY: test_io.d12 = 212;*/"
            ),
            original.replace("d12 = 212", "d12 = 999"),
            original + "clear_all_vars \n ();\n",
        ):
            self.checkpoint.write_text(text)
            with self.subTest(text=text), self.assertRaises(b.BaselineError):
                self.validate()

    def test_every_observation_is_checked_independently_of_digests(self):
        for key, value in self.expected.items():
            actual = copy.deepcopy(self.expected)
            if isinstance(value, list):
                actual[key][0] = 999
            elif isinstance(value, str):
                actual[key] = "wrong scenario"
            else:
                actual[key] = False  # Also catches bool/number equality in Python.
            self.observations.write_bytes(b.json_bytes(actual))
            with self.subTest(key=key), self.assertRaises(b.BaselineError):
                self.validate()

    def test_missing_duplicate_and_unrelated_diagnostics_are_rejected(self):
        for messages in (
            self.diagnostics[1:],
            self.diagnostics + [self.diagnostics[0]],
            self.diagnostics + ["Checkpoint Agent ERROR: syntax error"],
            self.diagnostics + ["ERROR:Unexpected failure"],
            self.diagnostics + ["Traceback (most recent call last):"],
        ):
            (self.root / "stdout.log").write_text("\n".join(messages))
            (self.root / "stderr.log").write_text("")
            with self.subTest(messages=messages), self.assertRaises(b.BaselineError):
                self.validate()

    def test_expected_negative_probe_does_not_relax_template_gate(self):
        with self.assertRaisesRegex(b.BaselineError, "checkpoint restore error"):
            s.validate_runtime(self.root, s.HERE / "runtime/templates.expected.json")


if __name__ == "__main__":
    unittest.main()
