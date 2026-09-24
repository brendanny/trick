"""Compare facts while changing the actual declaration-extraction worklist."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.icg_schema import validate as ir  # noqa: E402

SCHEMA = json.loads((HERE.parent / "ir/extracted-facts.schema.json").read_text())
EXTRACTOR: Path
WORKLIST_EXTRACTOR: Path
CLANG: Path


class WorklistTests(unittest.TestCase):
    maxDiff = 5000

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="icg-worklist-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.header = self.root / "model.hh"
        self.env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("TRICK_") and k != "ICG_TEST_WORKLIST_ORDER"
        }

    def run_extractor(self, binary, order, header, root, options=()):
        result = subprocess.run(
            [
                str(binary),
                "--source-root",
                str(root),
                "--diagnostics-format=json",
                *options,
                str(header),
                "--",
            ],
            env={**self.env, "ICG_TEST_WORKLIST_ORDER": order},
            capture_output=True,
            text=True,
            timeout=30,
        )
        trace, diagnostics = [], []
        for line in result.stderr.splitlines():
            if line.startswith("ICG_TEST_VISIT "):
                trace.append(json.loads(line.removeprefix("ICG_TEST_VISIT ")))
            else:
                diagnostics.append(line)
        report = json.loads("\n".join(diagnostics))
        if result.returncode == 0:
            document = json.loads(result.stdout)
            ir.validate(SCHEMA, document)
            self.assertEqual(report["diagnostics"], document["diagnostics"])
        else:
            self.assertEqual(
                result.stdout, "", "failed traversal published partial facts"
            )
            self.assertTrue(
                any(d["severity"] in ("error", "fatal") for d in report["diagnostics"])
            )
        return result, report, trace

    def compare(
        self, *, success=True, header=None, root=None, reorder=True, options=()
    ):
        header, root = header or self.header, root or self.root
        normal, report, trace = self.run_extractor(
            EXTRACTOR, "lifo", header, root, options
        )
        self.assertEqual(trace, [], "test hooks leaked into the production executable")
        fifo, fifo_report, fifo_trace = self.run_extractor(
            WORKLIST_EXTRACTOR, "fifo", header, root, options
        )
        lifo, lifo_report, lifo_trace = self.run_extractor(
            WORKLIST_EXTRACTOR, "lifo", header, root, options
        )
        self.assertEqual(normal.returncode == 0, success, normal.stderr)
        self.assertEqual(normal.returncode, fifo.returncode)
        self.assertEqual(normal.returncode, lifo.returncode)
        self.assertEqual(normal.stdout, fifo.stdout)
        self.assertEqual(report, fifo_report)
        if reorder:
            self.assertGreater(len(fifo_trace), 1)
            if success:
                self.assertCountEqual(fifo_trace, lifo_trace)
            # Failure stops type interning, so subsequent dependency closure can
            # differ. Failed runs must still reject without publishing facts.
            self.assertNotEqual(
                fifo_trace, lifo_trace, "live extraction order was not changed"
            )
        if success:
            # Compare every byte, including provenance, source evidence, graph and
            # input digests. Sorting the output must not hide stale cached facts.
            self.assertEqual(json.loads(normal.stdout), json.loads(lifo.stdout))
            self.assertEqual(normal.stdout, lifo.stdout)
            self.assertEqual(report, lifo_report)
            return json.loads(normal.stdout), fifo_trace, lifo_trace
        # Errors are encountered in worklist order; retain complete diagnostics,
        # including multiplicity, severity, source and message, ignoring only order.
        for key in ("files", "diagnostics"):
            self.assertCountEqual(report[key], lifo_report[key])
        return report, fifo_trace, lifo_trace

    def test_existing_semantic_corpus_is_identical_in_both_orders(self):
        for header in sorted((HERE / "fixtures").glob("*.hh")):
            with self.subTest(fixture=header.name):
                options = []
                if header.name == "evidence.hh":
                    for name in ("model.hh", "other.hh"):
                        options.extend((
                            "--select-file",
                            str(HERE / "fixtures/evidence" / name),
                        ))
                self.compare(
                    header=header,
                    root=HERE / "fixtures",
                    reorder=header.name != "record.hh",
                    options=options,
                )

    def test_late_dependencies_and_aliases_bind_to_the_same_concrete_owners(self):
        self.header.write_text(
            "template<class T> struct Box { using ref = int&; using chain = ref; ref get(); void set(chain value); T value; };\n"
            "template<class T> struct Wrap { Box<T> box; };\n"
            "struct First { Wrap<int> value; }; struct Second { Wrap<char> value; };\n"
        )
        facts, fifo, lifo = self.compare()
        nodes = {n["qualified_name"]: n for n in facts["declarations"]}
        self.assertIn("Box<int>::ref", nodes)
        self.assertIn("Box<char>::ref", nodes)
        self.assertNotEqual(nodes["Box<int>::ref"]["id"], nodes["Box<char>::ref"]["id"])
        # These instances are discovered from record fields, not selection roots.
        self.assertLess(fifo.index("First"), fifo.index("Wrap<int>"))
        self.assertLess(lifo.index("Wrap<char>"), lifo.index("First"))

    def test_implicit_and_defaulted_noexcept_facts_are_stable(self):
        self.header.write_text(
            "struct Throws { Throws() noexcept(false); ~Throws() noexcept(false); };\n"
            "template<class T> struct Box { Box() = default; ~Box() = default; T value; };\n"
            "struct Implicit { Box<Throws> value; }; struct Plain { Box<int> value; };\n"
        )
        facts, _, _ = self.compare()
        nodes = {n["qualified_name"]: n for n in facts["declarations"]}
        for name, expected in (("Implicit", "false"), ("Plain", "true")):
            slots = {s["kind"]: s for s in nodes[name]["special_members"]}
            self.assertEqual(slots["default_constructor"]["noexcept"], expected)
            self.assertEqual(slots["destructor"]["noexcept"], expected)

    def test_late_sema_errors_publish_nothing_in_either_order(self):
        self.header.write_text(
            "template<class T> struct Lazy { Lazy() noexcept(sizeof(typename T::missing) > 0) = default; };\n"
            "struct Bad { Lazy<int> value; }; struct Other { int value; };\n"
        )
        parsed = subprocess.run(
            [str(CLANG), "-std=c++17", "-x", "c++", "-fsyntax-only", str(self.header)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(parsed.returncode, 0, parsed.stderr)
        report, _, _ = self.compare(success=False)
        self.assertTrue(
            any(
                d["code"].startswith("CLANG_") and d["severity"] == "error"
                for d in report["diagnostics"]
            )
        )

    def test_unrelated_rejection_with_alias_dependencies_is_stable(self):
        self.header.write_text(
            "struct Unsupported { static int value; };\n"
            "template<class T> struct Box { using ref = int&; ref get(); T value; };\n"
            "struct Model { Box<int> first; Box<char> second; };\n"
        )
        report, _, _ = self.compare(success=False)
        self.assertIn(
            "ICG_UNSUPPORTED_DECLARATION", {d["code"] for d in report["diagnostics"]}
        )

    def test_parse_errors_do_not_reach_the_worklist(self):
        self.header.write_text(
            "#error stop before extraction\nstruct Model { int value; };\n"
        )
        _, fifo, lifo = self.compare(success=False, reorder=False)
        self.assertEqual(fifo, [])
        self.assertEqual(lifo, [])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--extractor", type=Path, required=True)
    parser.add_argument("--worklist-extractor", type=Path, required=True)
    parser.add_argument("--clang", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    EXTRACTOR, WORKLIST_EXTRACTOR, CLANG = (
        args.extractor,
        args.worklist_extractor,
        args.clang,
    )
    unittest.main(argv=[sys.argv[0], *remaining])
