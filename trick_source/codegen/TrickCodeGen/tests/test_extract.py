"""Exercise the real LLVM 17 executable and validate every successful document."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
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
        self.assertEqual(document["schema_version"], 3)
        VALIDATOR.validate(SCHEMA, document)
        report = self.report(result)
        self.assertEqual(report["diagnostics"], document["diagnostics"])
        return document

    def report(self, result):
        report = json.loads(result.stderr)
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(report["document_kind"], "trick.icg.diagnostics")
        ids = {node["id"] for node in report["files"]}
        for node in report["files"]:
            VALIDATOR.Draft202012Validator({
                "$defs": SCHEMA["$defs"],
                "$ref": "#/$defs/file",
            }).validate(node)
        for diagnostic in report["diagnostics"]:
            # Reuse the same wire definitions for both output channels.
            VALIDATOR.Draft202012Validator({
                "$defs": SCHEMA["$defs"],
                "$ref": "#/$defs/diagnostic",
            }).validate(diagnostic)
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
            "struct Sample { unsigned value:3; };",
            "struct Sample { void method(); };",
            "struct Base {}; struct Sample: Base {};",
            "template<class T> struct Sample { T value; };",
            "namespace ns { struct Sample {}; }",
            "enum E { A };",
            "struct { int value; } anonymous;",
        ):
            with self.subTest(source=source):
                self.header.write_text(source)
                self.failure(self.invoke(), "ICG_UNSUPPORTED_DECLARATION")

    def test_pointer_and_reference_layers_preserve_qualifiers(self):
        self.header.write_text(
            "struct Sample { const int *p; int *const q = nullptr; volatile int &r; int &&s; int **pp; };\n"
        )
        document = self.success(self.invoke())
        declarations = self.declarations(document)
        types = {t["id"]: t for t in document["types"]}
        fields = {
            name: types[declarations["Sample::" + name]["type_id"]]
            for name in ("p", "q", "r", "s", "pp")
        }
        self.assertFalse(fields["p"]["qualifiers"]["const"])
        self.assertTrue(types[fields["p"]["pointee_id"]]["qualifiers"]["const"])
        self.assertTrue(fields["q"]["qualifiers"]["const"])
        self.assertFalse(types[fields["q"]["pointee_id"]]["qualifiers"]["const"])
        self.assertEqual(fields["r"]["kind"], "lvalue_reference")
        self.assertTrue(types[fields["r"]["pointee_id"]]["qualifiers"]["volatile"])
        self.assertEqual(fields["s"]["kind"], "rvalue_reference")
        self.assertEqual(types[fields["pp"]["pointee_id"]]["kind"], "pointer")

    def test_array_dimensions_and_pointer_binding_are_structural(self):
        self.header.write_text(
            "struct Sample { int matrix[2][3]; int *pointers[2]; int (*array)[2]; int (*unknown)[]; };\n"
        )
        document = self.success(self.invoke())
        declarations = self.declarations(document)
        types = {t["id"]: t for t in document["types"]}
        matrix = types[declarations["Sample::matrix"]["type_id"]]
        self.assertEqual(matrix["extent"], 2)
        self.assertEqual(types[matrix["element_id"]]["extent"], 3)
        pointers = types[declarations["Sample::pointers"]["type_id"]]
        array = types[declarations["Sample::array"]["type_id"]]
        self.assertEqual(types[pointers["element_id"]]["kind"], "pointer")
        self.assertEqual(types[array["pointee_id"]]["kind"], "array")
        self.assertNotEqual(array["id"], pointers["id"])
        unknown = types[declarations["Sample::unknown"]["type_id"]]
        self.assertIsNone(types[unknown["pointee_id"]]["extent"])

    def test_alias_chains_and_canonical_types(self):
        self.header.write_text(
            "typedef int Number; using Other = Number; using Pointer = Other*; struct Sample { Other a; int b; Pointer p; int *q; const Number c = 1; };\n"
        )
        document = self.success(self.invoke())
        declarations = self.declarations(document)
        types = {t["id"]: t for t in document["types"]}
        a = types[declarations["Sample::a"]["type_id"]]
        self.assertEqual(a["kind"], "alias")
        self.assertEqual(a["canonical_id"], declarations["Sample::b"]["type_id"])
        self.assertEqual(a["declaration_id"], declarations["Other"]["id"])
        self.assertEqual(
            types[declarations["Other"]["underlying_type_id"]]["declaration_id"],
            declarations["Number"]["id"],
        )
        p = types[declarations["Sample::p"]["type_id"]]
        self.assertEqual(p["canonical_id"], declarations["Sample::q"]["type_id"])
        c = types[declarations["Sample::c"]["type_id"]]
        self.assertTrue(types[c["canonical_id"]]["qualifiers"]["const"])

    def test_const_array_alias_preserves_element_qualifiers(self):
        self.header.write_text(
            "using Row = int[3]; struct Sample { const Row row = {}; const int direct[3] = {}; };\n"
        )
        document = self.success(self.invoke())
        declarations = self.declarations(document)
        types = {t["id"]: t for t in document["types"]}
        row = types[declarations["Sample::row"]["type_id"]]
        direct = types[declarations["Sample::direct"]["type_id"]]
        self.assertEqual(row["canonical_id"], direct["canonical_id"])
        # Array qualification is normalized onto elements, including aliases.
        canonical = types[row["canonical_id"]]
        self.assertFalse(canonical["qualifiers"]["const"])
        self.assertTrue(types[canonical["element_id"]]["qualifiers"]["const"])

    def test_recursive_records_and_forward_declarations(self):
        self.header.write_text(
            "struct B; struct A { B *b; A *self; }; struct B { A *a; }; struct B;\n"
        )
        document = self.success(self.invoke())
        declarations = self.declarations(document)
        self.assertEqual(set(declarations), {"A", "A::b", "A::self", "B", "B::a"})
        types = {t["id"]: t for t in document["types"]}
        b = types[declarations["A::b"]["type_id"]]
        self.assertEqual(
            types[b["pointee_id"]]["declaration_id"], declarations["B"]["id"]
        )
        self.assertTrue(declarations["B"]["definition"])
        self.assertEqual(declarations["B"]["field_ids"], [declarations["B::a"]["id"]])

    def test_incomplete_record_has_unknown_layout(self):
        self.header.write_text("struct Opaque; struct Sample { Opaque *p; };\n")
        declarations = self.declarations(self.success(self.invoke()))
        opaque = declarations["Opaque"]
        self.assertFalse(opaque["definition"])
        self.assertFalse(opaque["complete"])
        self.assertIsNone(opaque["size_bits"])
        self.assertIsNone(opaque["alignment_bits"])
        self.assertEqual(opaque["capabilities"][0]["reason_code"], "INCOMPLETE_TYPE")

    def test_nested_record_alias_and_distinct_parent_contexts(self):
        self.header.write_text(
            "struct Outer { struct Inner; using Value = int; Inner *p; }; struct Outer::Inner { Outer::Value x; };\n"
        )
        declarations = self.declarations(self.success(self.invoke()))
        outer, inner = declarations["Outer"], declarations["Outer::Inner"]
        self.assertEqual(inner["semantic_parent_id"], outer["id"])
        self.assertNotIn("lexical_parent_id", inner)
        self.assertEqual(
            set(outer["nested_declaration_ids"]),
            {inner["id"], declarations["Outer::Value"]["id"]},
        )

    def test_referenced_header_declarations_form_a_closed_graph(self):
        (self.root / "types.hh").write_text(
            "struct Unused { void method(); }; struct Node { Node *next; int value; }; using NodePtr = Node*;\n"
        )
        self.header.write_text('#include "types.hh"\nstruct Sample { NodePtr p; };\n')
        document = self.success(self.invoke())
        declarations = self.declarations(document)
        self.assertIn("Node", declarations)
        self.assertIn("NodePtr", declarations)
        self.assertNotIn("Unused", declarations)
        source = declarations["Node"]["source"]["spelling"]["file_id"]
        self.assertEqual(
            next(f for f in document["files"] if f["id"] == source)["path"]["portable"],
            "types.hh",
        )

    def test_unsupported_referenced_type_does_not_publish_partial_facts(self):
        (self.root / "types.hh").write_text("struct Node { void method(); };\n")
        self.header.write_text('#include "types.hh"\nstruct Sample { Node *p; };\n')
        self.failure(self.invoke(), "ICG_UNSUPPORTED_DECLARATION")

    def test_structural_ids_survive_root_relocation_and_field_reordering(self):
        source = "struct Node { int *p; double value[3]; };\n"
        self.header.write_text(source)
        first = self.success(self.invoke())
        other = self.root / "relocated"
        other.mkdir()
        (other / "record.hh").write_text("struct Node { double value[3]; int *p; };\n")
        second = self.success(
            self.invoke(cwd=other, options=["--source-root", str(other)])
        )
        for key in ("types", "declarations", "files"):
            self.assertEqual(
                {n["id"] for n in first[key]}, {n["id"] for n in second[key]}
            )

    def test_unsupported_structural_types_fail_closed(self):
        for source in (
            "struct Sample { int (*callback)(double); };",
            "struct Sample { int Sample::*member; };",
            "using Value = decltype(1);",
            "using Value = int __attribute__((vector_size(16))); ",
        ):
            with self.subTest(source=source):
                self.header.write_text(source)
                self.failure(self.invoke(), "ICG_UNSUPPORTED_TYPE")

    def test_checked_in_structural_fixture(self):
        for filename in ("structured.hh", "model-types.hh"):
            (self.root / filename).write_text(
                (HERE / "fixtures" / filename).read_text()
            )
        document = self.success(self.invoke(input="structured.hh"))
        declarations = self.declarations(document)
        self.assertTrue(
            {"Handle", "Model", "Opaque", "Node", "Node::Weight"} <= declarations.keys()
        )
        self.assertFalse(declarations["Opaque"]["complete"])
        self.assertEqual(len(document["files"]), 2)

    def test_reference_alias_collapse_and_qualified_record_links(self):
        self.header.write_text(
            "struct Node {}; using Ref = int&; using Collapsed = Ref&&; struct Sample { Ref l; Collapsed r; const Node *node; };\n"
        )
        document = self.success(self.invoke())
        declarations = self.declarations(document)
        types = {t["id"]: t for t in document["types"]}
        left = types[declarations["Sample::l"]["type_id"]]
        right = types[declarations["Sample::r"]["type_id"]]
        self.assertEqual(left["canonical_id"], right["canonical_id"])
        self.assertEqual(types[left["canonical_id"]]["kind"], "lvalue_reference")
        pointer = types[declarations["Sample::node"]["type_id"]]
        node = types[pointer["pointee_id"]]
        self.assertTrue(node["qualifiers"]["const"])
        self.assertEqual(node["declaration_id"], declarations["Node"]["id"])

    def test_referenced_system_alias_keeps_origin(self):
        system = self.root / "system"
        system.mkdir()
        (system / "types.hh").write_text("using SystemValue = unsigned long;\n")
        self.header.write_text(
            "#include <types.hh>\nstruct Sample { SystemValue value; };\n"
        )
        document = self.success(self.invoke(["-isystem", str(system)]))
        self.assertEqual(self.declarations(document)["SystemValue"]["origin"], "system")

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

    def test_paired_arguments_cannot_swallow_flags(self):
        for flag in (
            "-I",
            "-isystem",
            "-iquote",
            "-D",
            "-U",
            "-include",
            "-imacros",
            "--sysroot",
            "-isysroot",
            "-target",
            "--target",
        ):
            for value in ("-DSECRET=1", "--", ""):
                with self.subTest(flag=flag, value=value):
                    result = self.invoke([flag, value])
                    self.failure(result, "ICG_ARGUMENT_VALUE")
                    self.assertEqual(result.returncode, 2)
        self.header.write_text(
            "#ifndef SECRET\n#error missing define\n#endif\nstruct Present {};\n"
        )
        self.success(self.invoke(["-I", ".", "-D", "SECRET=1"]))

    def test_pragma_once_warning_is_suppressed_without_hiding_other_warnings(self):
        self.header.write_text("#pragma once\nstruct Sample {};\n")
        self.assertEqual(self.success(self.invoke(["-Werror"]))["diagnostics"], [])
        self.header.write_text(
            "#pragma once\n#warning visible warning\nstruct Sample {};\n"
        )
        diagnostics = self.success(self.invoke())["diagnostics"]
        self.assertEqual(len(diagnostics), 1)
        self.assertIn("visible warning", diagnostics[0]["message"])
        self.failure(self.invoke(["-Werror"]))

    def test_all_unsupported_members_are_reported_in_one_run(self):
        self.header.write_text(
            "struct Sample {\nunsigned bits : 1;\nstatic int value;\nvoid run();\nstruct { int item; };\n};\n"
        )
        report = self.failure(self.invoke(), "ICG_UNSUPPORTED_DECLARATION")
        lines = {
            d["source"]["expansion"]["line"]
            for d in report["diagnostics"]
            if d["code"] == "ICG_UNSUPPORTED_DECLARATION"
        }
        self.assertTrue({2, 3, 4, 5} <= lines, report)

    def test_external_headers_require_explicit_roots(self):
        with tempfile.TemporaryDirectory(prefix="icg-external-") as external:
            directory = Path(external)
            (directory / "external.hh").write_text("using External = long;\n")
            self.header.write_text(
                "#include <external.hh>\nstruct Sample { External value; };\n"
            )
            flags = ["-isystem", external]
            report = self.failure(self.invoke(flags), "ICG_UNMAPPED_FILE")
            self.assertEqual(
                sum(d["code"] == "ICG_UNMAPPED_FILE" for d in report["diagnostics"]), 1
            )
            first = self.success(
                self.invoke(flags, options=["--path-root", f"sysroot={external}"])
            )
            with tempfile.TemporaryDirectory(prefix="icg-relocated-sdk-") as relocated:
                shutil.copy(directory / "external.hh", relocated)
                second = self.success(
                    self.invoke(
                        ["-isystem", relocated],
                        options=["--path-root", f"sysroot={relocated}"],
                    )
                )
            for key in ("types", "declarations"):
                self.assertEqual(first[key], second[key])
            self.assertEqual(
                {f["id"] for f in first["files"]}, {f["id"] for f in second["files"]}
            )

    def test_real_resource_headers_survive_installation_relocation(self):
        self.header.write_text(
            "#include <stddef.h>\nstruct Sample { size_t value; };\n"
        )
        first = self.success(self.invoke())
        original = Path(first["provenance"]["path_roots"]["resource-dir"])
        files = [f for f in first["files"] if f["path"]["root"] == "resource-dir"]
        self.assertTrue(files)
        self.assertEqual(self.declarations(first)["size_t"]["origin"], "system")
        with tempfile.TemporaryDirectory(prefix="icg-resource-") as relocated:
            target = Path(relocated)
            shutil.copytree(original / "include", target / "include")
            second = self.success(
                self.invoke(options=["--path-root", f"resource-dir={relocated}"])
            )
        for key in ("types", "declarations"):
            self.assertEqual(first[key], second[key])
        self.assertEqual(
            {f["id"] for f in first["files"]}, {f["id"] for f in second["files"]}
        )

    def test_named_roots_use_longest_match_and_disambiguate_relative_names(self):
        build = self.root / "build"
        build.mkdir()
        (build / "record.hh").write_text("using Generated = int;\n")
        self.header.write_text(
            '#include "build/record.hh"\nstruct Sample { Generated value; };\n'
        )
        document = self.success(self.invoke(options=["--path-root", f"build={build}"]))
        self.assertEqual(
            {(f["path"]["root"], f["path"]["portable"]) for f in document["files"]},
            {("source", "record.hh"), ("build", "record.hh")},
        )
        alias = self.root / "build-alias"
        alias.symlink_to(build, target_is_directory=True)
        second = self.success(self.invoke(options=["--path-root", f"build={alias}"]))
        self.assertEqual(document["files"], second["files"])
        self.failure(
            self.invoke(options=["--path-root", f"duplicate={self.root}"]),
            "ICG_PATH_ROOT",
        )
        self.failure(
            self.invoke(options=["--path-root", "build=/icg-nonexistent-dir"]),
            "ICG_PATH_ROOT",
        )

    def test_large_layout_and_array_quantities_remain_exact(self):
        self.header.write_text(
            "struct Huge { char bytes[9007199254740992ULL]; int last; };\n"
        )
        document = self.success(self.invoke())
        declarations = self.declarations(document)
        self.assertEqual(declarations["Huge::last"]["offset_bits"], str(2**56))
        self.assertEqual(declarations["Huge"]["size_bits"], str(2**56 + 32))
        self.assertEqual(
            next(t["extent"] for t in document["types"] if t["kind"] == "array"),
            str(2**53),
        )

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
