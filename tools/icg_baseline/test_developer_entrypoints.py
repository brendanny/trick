"""Manual test commands must distinguish missing tools from successful checks."""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class DeveloperEntryPointTests(unittest.TestCase):
    def run_python(self, *args):
        return subprocess.run(
            [sys.executable, *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_unconfigured_discovery_fails_with_a_runnable_command(self):
        for suite in ("emit", "policy"):
            with self.subTest(suite=suite):
                result = self.run_python(
                    "-m", "unittest", "discover", "-s", f"tools/icg_{suite}"
                )
                self.assertNotEqual(result.returncode, 0, result.stderr)
                self.assertIn("require --extractor and --compiler", result.stderr)
                self.assertIn(f"-R icg_{suite}_integration", result.stderr)
                self.assertNotIn("OK", result.stderr)

    def test_integration_scripts_require_both_tools(self):
        for script in ("icg_emit/test_emit.py", "icg_policy/test_resolve.py"):
            for options in ((), ("--extractor", "unused"), ("--compiler", "unused")):
                with self.subTest(script=script, options=options):
                    result = self.run_python(f"tools/{script}", *options)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    missing = (
                        "--compiler" if "--extractor" in options else "--extractor"
                    )
                    self.assertIn("required", result.stderr)
                    self.assertIn(missing, result.stderr)

    def test_explicit_rule_suite_works_without_native_tools(self):
        result = self.run_python(
            "-m", "unittest", "tools.icg_policy.test_resolve.RuleTests"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK", result.stderr)
        self.assertNotIn("skipped", result.stderr)
