"""Exercise the real LLVM 17 executable and validate every successful document."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
SCHEMA = json.loads((HERE.parent / "ir/extracted-facts.schema.json").read_text())
SPEC = importlib.util.spec_from_file_location(
    "icg_validate", ROOT / "tools/icg_schema/validate.py"
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)
EXTRACTOR: Path


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="icg-extract-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.header = self.root / "record.hh"
        self.header.write_text((HERE / "fixtures/record.hh").read_text())

    def invoke(self, flags=(), *, options=(), input="record.hh", cwd=None, env=None):
        return subprocess.run(
            [
                str(EXTRACTOR),
                "--diagnostics-format=json",
                "--source-root",
                str(self.root),
                *options,
                input,
                "--",
                *flags,
            ],
            cwd=cwd or self.root,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )

    def success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(result.stdout)
        VALIDATOR.validate(SCHEMA, document)
        report = self.report(result)
        self.assertEqual(report["diagnostics"], document["diagnostics"])
        return document

    def report(self, result):
        report = json.loads(result.stderr)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["document_kind"], "trick.icg.diagnostics")
        ids = {node["id"] for node in report["files"]}
        for diagnostic in report["diagnostics"]:
            # Reuse the same wire definitions for both output channels.
            VALIDATOR.Draft202012Validator(
                {"$defs": SCHEMA["$defs"], "$ref": "#/$defs/diagnostic"}
            ).validate(diagnostic)
            if diagnostic["source"]:
                for point in ("spelling", "expansion", "end"):
                    self.assertIn(diagnostic["source"][point]["file_id"], ids)
        return report

    def failure(self, result, code=None):
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout, "", "Failed extraction must not publish partial facts"
        )
        report = self.report(result)
        self.assertTrue(
            any(d["severity"] in ("error", "fatal") for d in report["diagnostics"])
        )
        if code:
            self.assertIn(code, {d["code"] for d in report["diagnostics"]})
        return report

    @staticmethod
    def declarations(document):
        return {d["qualified_name"]: d for d in document["declarations"]}

    def test_minimal_record_layout_source_and_comments(self):
        document = self.success(self.invoke())
        record, field = (
            self.declarations(document)[name] for name in ("Sample", "Sample::value")
        )
        self.assertEqual((record["size_bits"], record["alignment_bits"]), (32, 32))
        self.assertEqual(record["field_ids"], [field["id"]])
        self.assertEqual(field["offset_bits"], 0)
        self.assertEqual(field["source"]["spelling"]["line"], 4)
        self.assertEqual(field["source"]["end"]["line"], 4)
        self.assertEqual(field["annotations"][0]["payload"], "/// trick_units(m)")
        self.assertEqual(record["usr"], "c:@S@Sample")
        self.assertEqual(
            document["files"][0]["digest"],
            hashlib.sha256(self.header.read_bytes()).hexdigest(),
        )
        self.assertEqual(document["files"][0]["path"]["portable"], "record.hh")
        self.assertEqual(document["provenance"]["frontend_api"], "libtooling")
        self.assertIn("17.0", document["provenance"]["frontend_version"])

    def test_deterministic_serialization_and_sorted_ids(self):
        first = self.invoke()
        document = self.success(first)
        self.assertEqual(first.stdout, self.invoke().stdout)
        for key in ("files", "types", "declarations"):
            ids = [entry["id"] for entry in document[key]]
            self.assertEqual(ids, sorted(ids))

    def test_explicit_arguments_and_target_affect_the_parse(self):
        self.header.write_text(
            "#ifdef SELECTED\nstruct Selected { long value; };\n#else\n#error SELECTED missing\n#endif\n"
        )
        args = ["-DSELECTED", "--target=i386-unknown-linux-gnu", "-std=c++17"]
        document = self.success(self.invoke(args))
        self.assertEqual(self.declarations(document)["Selected"]["size_bits"], 32)
        self.assertEqual(
            document["provenance"]["target_triple"], "i386-unknown-linux-gnu"
        )
        actual = document["provenance"]["arguments"]
        self.assertTrue(all(arg in actual for arg in args))
        self.assertIn("-fsyntax-only", actual)
        self.assertIn("-resource-dir", actual)

    def test_include_order_spaces_and_transitive_dependency_fingerprints(self):
        include = self.root / "include space"
        include.mkdir()
        (include / "config.hh").write_text('#include "detail.hh"\n')
        detail = include / "detail.hh"
        detail.write_text("#define FIELD int\n")
        self.header.write_text(
            '#include "config.hh"\nstruct Sample { FIELD value; };\n'
        )
        first = self.success(self.invoke(["-I", str(include)]))
        self.assertEqual(len(first["files"]), 3)
        self.assertEqual(sum(len(f["includes"]) for f in first["files"]), 2)
        detail.write_text("#define FIELD double\n")
        second = self.success(self.invoke(["-I", str(include)]))
        self.assertNotEqual(
            first["provenance"]["input_digest"], second["provenance"]["input_digest"]
        )
        self.assertEqual(self.declarations(second)["Sample"]["size_bits"], 64)
        alternate = self.root / "alternate"
        alternate.mkdir()
        (alternate / "config.hh").write_text("#define FIELD char\n")
        third = self.success(self.invoke(["-I", str(alternate), "-I", str(include)]))
        self.assertEqual(self.declarations(third)["Sample"]["size_bits"], 8)

    def test_forced_include_and_matching_resource_headers(self):
        (self.root / "forced.hh").write_text("#define PRESENT 1\n")
        self.header.write_text(
            "#include <stddef.h>\n#ifndef PRESENT\n#error missing forced include\n#endif\nstruct Sample { int value; };\n"
        )
        document = self.success(self.invoke(["-include", "forced.hh"]))
        self.assertTrue(
            any(f["path"]["portable"] == "forced.hh" for f in document["files"])
        )
        self.assertTrue(any(f["classification"] == "system" for f in document["files"]))

    def test_macro_spelling_and_expansion_locations(self):
        self.header.write_text("#define FIELD int value\nstruct Sample { FIELD; };\n")
        field = self.declarations(self.success(self.invoke()))["Sample::value"]
        self.assertTrue(field["source"]["macro_expansion"])
        self.assertEqual(field["source"]["spelling"]["line"], 1)
        self.assertEqual(field["source"]["expansion"]["line"], 2)

    def test_command_line_macro_locations_fail_closed(self):
        self.header.write_text("struct Sample { ATTR int value; };\n")
        self.failure(
            self.invoke(['-DATTR=[[clang::annotate("units(m)")]]']),
            "ICG_UNSUPPORTED_DECLARATION",
        )

    def test_annotations_access_qualifiers_and_field_order(self):
        self.header.write_text(
            'class Sample { public: [[clang::annotate("units(m)")]] const int z = 1; private: mutable double a; };\n'
        )
        document = self.success(self.invoke())
        nodes = self.declarations(document)
        self.assertEqual(
            nodes["Sample"]["field_ids"],
            [nodes["Sample::z"]["id"], nodes["Sample::a"]["id"]],
        )
        self.assertEqual(nodes["Sample::z"]["annotations"][0]["payload"], "units(m)")
        self.assertEqual(nodes["Sample::a"]["access"], "private")
        self.assertTrue(nodes["Sample::a"]["mutable"])
        types = {t["id"]: t for t in document["types"]}
        self.assertTrue(types[nodes["Sample::z"]["type_id"]]["qualifiers"]["const"])

    def test_symlink_alias_keeps_ids_and_portable_paths(self):
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        first = self.success(self.invoke())
        second = self.success(
            self.invoke(
                input=str(alias / "record.hh"), options=["--source-root", str(alias)]
            )
        )
        for category in ("files", "types", "declarations"):
            self.assertEqual(
                [n["id"] for n in first[category]], [n["id"] for n in second[category]]
            )
        self.assertEqual(second["files"][0]["path"]["portable"], "record.hh")

    def test_warning_is_visible_and_not_failure(self):
        self.header.write_text(
            "#warning visible warning\nstruct Sample { int value; };\n"
        )
        document = self.success(self.invoke())
        self.assertEqual(document["diagnostics"][0]["severity"], "warning")
        self.assertEqual(document["diagnostics"][0]["source"]["expansion"]["line"], 1)
        self.failure(self.invoke(["-Werror"]))

    def test_parse_error_has_location_and_no_partial_output(self):
        self.header.write_text(
            "struct Good { int a; };\nstruct Broken { Unknown value; };\n"
        )
        report = self.failure(self.invoke())
        self.assertTrue(
            any(
                d["source"] and d["source"]["expansion"]["line"] == 2
                for d in report["diagnostics"]
            )
        )

    def test_missing_include_and_missing_input(self):
        self.header.write_text('#include "absent.hh"\n')
        self.failure(self.invoke())
        self.failure(self.invoke(input="absent.hh"), "ICG_INPUT_READ")

    def test_unsupported_declarations_fail_closed(self):
        for source in (
            "struct Sample { int *value; };",
            "struct Sample { int value[2]; };",
            "struct Sample { unsigned value:3; };",
            "struct Sample { void method(); };",
            "struct Base {}; struct Sample: Base {};",
            "struct Sample;",
            "template<class T> struct Sample { T value; };",
            "namespace ns { struct Sample {}; }",
            "typedef int Alias; struct Sample { Alias value; };",
            "enum E { A };",
            "struct Sample { struct Nested {}; };",
            "struct { int value; } anonymous;",
        ):
            with self.subTest(source=source):
                self.header.write_text(source)
                self.failure(self.invoke(), "ICG_UNSUPPORTED_DECLARATION")

    def test_unsupported_arguments_are_not_silently_dropped(self):
        for args in (
            ["-o", "unwanted.o"],
            ["-c"],
            ["-std=c++20"],
            ["-std=gnu++17"],
            ["-Xclang", "-load"],
            ["@hidden.rsp"],
            ["-Wl,-rpath,/tmp"],
            ["-funknown-option"],
            ["other.cc"],
            ["-x", "c"],
        ):
            with self.subTest(args=args):
                self.failure(self.invoke(args), "ICG_UNSUPPORTED_ARGUMENT")
        self.assertFalse((self.root / "unwanted.o").exists())
        self.failure(self.invoke(["-I"]), "ICG_ARGUMENT_VALUE")

    def test_unknown_warning_option_is_a_driver_error(self):
        self.failure(self.invoke(["-Wicg-nonexistent-warning"]))

    def test_cli_requires_one_input_and_separator(self):
        for args in (["record.hh"], ["record.hh", "other.hh", "--"], ["--"]):
            result = subprocess.run(
                [str(EXTRACTOR), "--diagnostics-format=json", *args],
                cwd=self.root,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            self.failure(result, "ICG_USAGE")

    def test_input_and_argument_changes_change_evidence_digest(self):
        first = self.success(self.invoke())
        second = self.success(self.invoke(["-DUNUSED=1"]))
        self.assertNotEqual(
            first["provenance"]["input_digest"], second["provenance"]["input_digest"]
        )
        self.header.write_text(self.header.read_text() + "\n// changed\n")
        third = self.success(self.invoke())
        self.assertNotEqual(
            first["provenance"]["input_digest"], third["provenance"]["input_digest"]
        )

    def test_environment_inputs_are_recorded(self):
        env = dict(os.environ, CPATH=str(self.root))
        document = self.success(self.invoke(env=env))
        self.assertEqual(document["provenance"]["environment"]["CPATH"], str(self.root))

    def test_human_diagnostics_stay_on_stderr(self):
        self.header.write_text("#error deliberate\n")
        result = subprocess.run(
            [str(EXTRACTOR), "record.hh", "--"],
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("record.hh:1:", result.stderr)
        self.assertIn("deliberate", result.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--extractor", required=True, type=Path)
    args, remaining = parser.parse_known_args()
    EXTRACTOR = args.extractor.resolve(strict=True)
    unittest.main(argv=[sys.argv[0], *remaining])
