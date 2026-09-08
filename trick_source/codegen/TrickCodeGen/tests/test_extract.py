"""Exercise the real LibTooling executable and validate every successful document."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
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
PATH_ROOTS: list[str] = []
LAYOUT_COMPILER: Path | None = None
LLVM_MAJOR: int | None = None
LIFECYCLE_SANITIZERS = False
LIFECYCLE_LEAK_CHECK = False


def layout_compiler_path(value):
    # Driver mode can depend on argv[0]: resolving clang++ to clang loses
    # automatic C++ runtime linkage. Validate without dereferencing the name.
    path = Path(value).absolute()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise argparse.ArgumentTypeError(f"Compiler is not executable: {path}")
    return path


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
                *(arg for root in PATH_ROOTS for arg in ("--path-root", root)),
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
        self.assertEqual(document["schema_version"], 10)
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
        version = re.search(
            r"\bclang version (\d+)\.", document["provenance"]["frontend_version"]
        )
        self.assertIsNotNone(version)
        major = int(version.group(1))
        self.assertIn(major, range(17, 24))
        if LLVM_MAJOR is not None:
            self.assertEqual(major, LLVM_MAJOR)

    def test_deterministic_serialization_and_sorted_ids(self):
        first = self.invoke()
        document = self.success(first)
        self.assertEqual(first.stdout, self.invoke().stdout)
        for key in ("files", "types", "declarations"):
            ids = [entry["id"] for entry in document[key]]
            self.assertEqual(ids, sorted(ids))

    def test_graph_and_evidence_digests_are_independently_reproducible(self):
        # Exercise UTF-8 and JSON escaping, including control characters, across
        # the C++ serializer and the independently implemented Python projection.
        self.header.write_text(
            '/// café 漢字 \\ "quoted"\n'
            'struct Sample { [[clang::annotate("\\v\\f\\b\\t\\n\\r")]] int value; };\n',
            encoding="utf-8",
        )
        document = self.success(self.invoke())
        self.assertEqual(document["provenance"]["identity_version"], 1)
        self.assertEqual(document["provenance"]["graph_digest_version"], 1)
        self.assertEqual(
            document["provenance"]["graph_digest"], VALIDATOR.graph_digest(document)
        )
        expected = document["provenance"].pop("input_digest")
        encoded = json.dumps(
            document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        self.assertEqual(expected, hashlib.sha256(encoded).hexdigest())

    def test_graph_digest_distinguishes_target_layout_changes(self):
        self.header.write_text("struct Sample { long value; };\n")
        first = self.success(self.invoke(["--target=x86_64-unknown-linux-gnu"]))
        second = self.success(self.invoke(["--target=i386-unknown-linux-gnu"]))
        self.assertNotEqual(
            first["provenance"]["graph_digest"], second["provenance"]["graph_digest"]
        )

    def test_graph_digest_does_not_rewrite_paths_embedded_in_facts(self):
        self.header.write_text("struct [[clang::annotate(__FILE__)]] Sample {};\n")
        first = self.success(self.invoke(input=str(self.header)))
        with tempfile.TemporaryDirectory(prefix="icg-embedded-path-") as relocated:
            target = Path(relocated) / self.header.name
            shutil.copy2(self.header, target)
            second = self.success(
                self.invoke(
                    input=str(target),
                    cwd=relocated,
                    options=["--source-root", relocated],
                )
            )
        self.assertNotEqual(
            first["provenance"]["graph_digest"], second["provenance"]["graph_digest"]
        )

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
            "struct Sample { template<class T> void method(T); };",
            "template<class T> using Sample = T;",
            "namespace ns { int variable; }",
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
        (self.root / "types.hh").write_text("struct Node { static int value; };\n")
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
            "struct Sample {\nfriend struct Friend;\nstatic int value;\ntemplate<class T> void run(T);\ntemplate<class T> Sample(T);\n};\n"
        )
        report = self.failure(self.invoke(), "ICG_UNSUPPORTED_DECLARATION")
        lines = {
            d["source"]["expansion"]["line"]
            for d in report["diagnostics"]
            if d["code"] == "ICG_UNSUPPORTED_DECLARATION"
        }
        self.assertTrue({2, 3, 4, 5} <= lines, report)

    def test_named_inline_and_nested_namespaces_preserve_context(self):
        self.header.write_text(
            "namespace Empty {}\n"
            "namespace A { inline namespace V { struct Node {}; } }\n"
            "namespace B::C { struct Node {}; using Value = A::Node; }\n"
        )
        document = self.success(self.invoke())
        nodes = self.declarations(document)
        self.assertEqual(nodes["Empty"]["declaration_ids"], [])
        self.assertTrue(nodes["A::V"]["inline"])
        self.assertFalse(nodes["B::C"]["inline"])
        for child, parent in (
            ("A::V", "A"),
            ("A::V::Node", "A::V"),
            ("B::C", "B"),
            ("B::C::Node", "B::C"),
        ):
            with self.subTest(child=child):
                self.assertEqual(
                    nodes[child]["semantic_parent_id"], nodes[parent]["id"]
                )
                self.assertEqual(nodes[child]["lexical_parent_id"], nodes[parent]["id"])
                self.assertIn(nodes[child]["id"], nodes[parent]["declaration_ids"])
                self.assertEqual(nodes[child]["identity_kind"], "usr")
        self.assertNotEqual(nodes["A::V::Node"]["id"], nodes["B::C::Node"]["id"])

    def test_namespace_reopenings_merge_members_and_keep_block_sources(self):
        self.header.write_text(
            "/// first block\nnamespace N { struct First {}; }\n"
            "/// second block\nnamespace N { struct Second {}; }\n"
            'namespace [[clang::annotate("third")]] N { using Third = int; }\n'
        )
        document = self.success(self.invoke())
        nodes = self.declarations(document)
        namespace = nodes["N"]
        self.assertEqual(
            sum(n["kind"] == "namespace" for n in document["declarations"]), 1
        )
        self.assertEqual(
            [s["spelling"]["line"] for s in namespace["reopening_sources"]], [2, 4, 5]
        )
        self.assertEqual(namespace["source"], namespace["reopening_sources"][0])
        self.assertEqual(
            [a["payload"] for a in namespace["annotations"]],
            ["/// first block", "/// second block", "third"],
        )
        self.assertEqual(
            namespace["declaration_ids"],
            sorted(nodes[name]["id"] for name in ("N::First", "N::Second", "N::Third")),
        )

    def test_namespace_dependency_closure_does_not_select_header_siblings(self):
        (self.root / "types.hh").write_text(
            "namespace N { struct Node { int value; }; struct Unused { void method(); }; }\n"
        )
        self.header.write_text(
            '#include "types.hh"\nnamespace N { using Handle = Node*; }\n'
        )
        document = self.success(self.invoke())
        nodes = self.declarations(document)
        self.assertEqual(set(nodes), {"N", "N::Node", "N::Node::value", "N::Handle"})
        self.assertEqual(len(nodes["N"]["reopening_sources"]), 2)

    def test_namespace_alias_chain_preserves_immediate_targets(self):
        (self.root / "types.hh").write_text(
            "namespace N { struct Unused { void method(); }; }\n"
        )
        self.header.write_text(
            '#include "types.hh"\nnamespace First = N;\nnamespace Second = First;\n'
        )
        nodes = self.declarations(self.success(self.invoke()))
        self.assertEqual(set(nodes), {"N", "First", "Second"})
        self.assertEqual(nodes["First"]["kind"], "namespace_alias")
        self.assertEqual(nodes["First"]["target_namespace_id"], nodes["N"]["id"])
        self.assertEqual(nodes["Second"]["target_namespace_id"], nodes["First"]["id"])
        self.assertEqual(nodes["N"]["declaration_ids"], [])

    def test_out_of_line_definition_keeps_semantic_and_lexical_contexts(self):
        self.header.write_text(
            "namespace N { struct Node; struct Outer { struct Inner; }; }\n"
            "struct N::Node { int value; };\n"
            "namespace N { struct Outer::Inner { int value; }; }\n"
        )
        nodes = self.declarations(self.success(self.invoke()))
        self.assertEqual(nodes["N::Node"]["semantic_parent_id"], nodes["N"]["id"])
        self.assertNotIn("lexical_parent_id", nodes["N::Node"])
        self.assertEqual(
            nodes["N::Outer::Inner"]["semantic_parent_id"], nodes["N::Outer"]["id"]
        )
        self.assertEqual(
            nodes["N::Outer::Inner"]["lexical_parent_id"], nodes["N"]["id"]
        )

    def test_unnamed_typedef_record_has_source_identity(self):
        self.header.write_text("typedef struct { int value; } Point;\n")
        document = self.success(self.invoke())
        nodes = {n["id"]: n for n in document["declarations"]}
        types = {t["id"]: t for t in document["types"]}
        # Clang may display both the typedef and its unnamed record as Point.
        # Display names are not unique graph keys.
        alias = next(n for n in nodes.values() if n["kind"] == "alias")
        record = nodes[types[alias["underlying_type_id"]]["declaration_id"]]
        self.assertTrue(record["anonymous"])
        self.assertEqual(record["name"], "")
        self.assertEqual(record["identity_kind"], "source")
        field = nodes[record["field_ids"][0]]
        self.assertEqual(field["name"], "value")
        self.assertEqual(field["identity_kind"], "source")
        self.assertFalse(field["anonymous_member"])

    def test_anonymous_display_names_use_the_same_semantic_context_components(self):
        self.header.write_text(
            "namespace N { inline namespace v1 {\n"
            "typedef struct { int x; } Point;\n"
            "typedef union { int i; double d; } Value;\n"
            "typedef enum { E } Code;\n"
            "struct Outer { struct { int u; } a; union { int b; float c; };\n"
            "unsigned : 0; Outer(); ~Outer(); operator int() const; int operator()(int) const; };\n"
            "}}\nN::v1::Outer::Outer() = default;\n"
            "#define PAIR(Owner) struct Owner { struct { int u; } a; };\n"
            "PAIR(P1) PAIR(P2)\n"
        )
        document = self.success(self.invoke())
        nodes = {n["id"]: n for n in document["declarations"]}
        for node in nodes.values():
            if "semantic_parent_id" in node:
                parent = nodes[node["semantic_parent_id"]]
                self.assertTrue(
                    node["qualified_name"].startswith(parent["qualified_name"] + "::"),
                    node,
                )
        names = {n["qualified_name"] for n in nodes.values()}
        self.assertTrue(
            {
                "N::v1::Point::x",
                "N::v1::Value::i",
                "N::v1::Code",
                "P1::(anonymous struct)::u",
                "P2::(anonymous struct)::u",
                "N::v1::Outer::(anonymous union)::b",
                "N::v1::Outer::(unnamed bitfield)",
                "N::v1::Outer::Outer",
                "N::v1::Outer::~Outer",
                "N::v1::Outer::operator int",
                "N::v1::Outer::operator()",
            }.issubset(names),
            names,
        )

    def test_source_identity_uses_versioned_extractor_owned_kind_tags(self):
        text = "typedef struct { int value; } Point;\n"
        self.header.write_text(text)
        document = self.success(self.invoke())
        record = next(n for n in document["declarations"] if n["kind"] == "record")
        field = next(n for n in document["declarations"] if n["kind"] == "field")

        def hashed(value):
            return hashlib.sha256(
                json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()

        for node, kind, token, parent in (
            (record, "record", "struct", ""),
            (field, "field", "value", record["id"]),
        ):
            offset = text.index(token)
            location = {
                "file_id": document["files"][0]["id"],
                "line": 1,
                "column": offset + 1,
                "offset": offset,
            }
            identity = {
                "version": 1,
                "kind": kind,
                "parent": parent,
                "name": node["name"],
                "location": hashed(location),
            }
            expected = (
                "decl:"
                + hashlib.sha256(
                    (
                        "source:"
                        + json.dumps(identity, sort_keys=True, separators=(",", ":"))
                    ).encode()
                ).hexdigest()
            )
            self.assertEqual(node["id"], expected)

    def test_distinct_unnamed_member_types_are_not_merged(self):
        self.header.write_text(
            "struct Outer { struct { int value; } a; struct { int value; } b; };\n"
        )
        document = self.success(self.invoke())
        nodes = self.declarations(document)
        self.assertNotEqual(nodes["Outer::a"]["type_id"], nodes["Outer::b"]["type_id"])
        records = [n for n in document["declarations"] if n.get("anonymous")]
        self.assertEqual(len(records), 2)
        self.assertNotEqual(records[0]["field_ids"], records[1]["field_ids"])
        self.assertEqual(
            set(nodes["Outer"]["nested_declaration_ids"]), {n["id"] for n in records}
        )
        self.assertNotIn(str(self.root), json.dumps(document["types"]))

    def test_anonymous_aggregates_preserve_physical_storage_and_offsets(self):
        self.header.write_text(
            "struct Outer { int prefix; union { struct { int x; }; double d; }; };\n"
        )
        document = self.success(self.invoke())
        nodes = {n["id"]: n for n in document["declarations"]}
        types = {t["id"]: t for t in document["types"]}
        outer = self.declarations(document)["Outer"]
        self.assertEqual(len(outer["field_ids"]), 2)
        storage = nodes[outer["field_ids"][1]]
        self.assertEqual(storage["name"], "")
        self.assertTrue(storage["anonymous_member"])
        self.assertEqual(storage["identity_kind"], "source")
        self.assertEqual(storage["offset_bits"], 64)
        union = nodes[types[storage["type_id"]]["declaration_id"]]
        self.assertEqual(union["record_tag"], "union")
        self.assertEqual([nodes[i]["offset_bits"] for i in union["field_ids"]], [0, 0])
        inner_storage = nodes[union["field_ids"][0]]
        self.assertTrue(inner_storage["anonymous_member"])
        inner = nodes[types[inner_storage["type_id"]]["declaration_id"]]
        self.assertEqual(nodes[inner["field_ids"][0]]["name"], "x")
        # IndirectFieldDecl lookup aliases do not duplicate the five storage fields.
        self.assertEqual(sum(n["kind"] == "field" for n in nodes.values()), 5)

    def test_nested_macro_expansions_disambiguate_anonymous_records(self):
        self.header.write_text(
            "#define ANON struct { int value; }\n"
            "#define TWO ANON a; ANON b;\n"
            "struct Outer { TWO };\n"
        )
        first = self.invoke()
        document = self.success(first)
        records = [n for n in document["declarations"] if n.get("anonymous")]
        self.assertEqual(len(records), 2)
        # Ultimate spelling and expansion points coincide; the intermediate
        # macro caller locations must still distinguish these declarations.
        for key in ("spelling", "expansion"):
            self.assertEqual(records[0]["source"][key], records[1]["source"][key])
        self.assertNotEqual(records[0]["id"], records[1]["id"])
        self.assertNotEqual(records[0]["field_ids"], records[1]["field_ids"])
        self.assertEqual(first.stdout, self.invoke().stdout)

    def test_anonymous_ids_disambiguate_same_basename_headers(self):
        for name in ("left", "right"):
            directory = self.root / name
            directory.mkdir()
            (directory / "member.hh").write_text(f"struct {{ int value; }} {name};\n")
        self.header.write_text(
            'struct Outer {\n#include "left/member.hh"\n#include "right/member.hh"\n};\n'
        )
        document = self.success(self.invoke())
        records = [n for n in document["declarations"] if n.get("anonymous")]
        self.assertEqual(len(records), 2)
        self.assertNotEqual(records[0]["id"], records[1]["id"])
        self.assertNotEqual(
            records[0]["source"]["spelling"]["file_id"],
            records[1]["source"]["spelling"]["file_id"],
        )

    def test_repeated_macro_arguments_preserve_substitution_identity(self):
        for macros, use in (
            ("#define TWO(TYPE) TYPE a; TYPE b;\n", "TWO(struct { int value; })"),
            (
                "#define INNER(TYPE, NAME) TYPE NAME;\n"
                "#define TWO(TYPE) INNER(TYPE, a) INNER(TYPE, b)\n",
                "TWO(struct { int value; })",
            ),
            (
                "#define ANON struct { int value; }\n"
                "#define TWO(TYPE) TYPE a; TYPE b;\n",
                "TWO(ANON)",
            ),
        ):
            with self.subTest(macros=macros):
                self.header.write_text(macros + f"struct Outer {{ {use} }};\n")
                first = self.invoke()
                document = self.success(first)
                records = [n for n in document["declarations"] if n.get("anonymous")]
                self.assertEqual(len(records), 2)
                self.assertNotEqual(records[0]["id"], records[1]["id"])
                self.assertNotEqual(records[0]["field_ids"], records[1]["field_ids"])
                self.assertEqual(first.stdout, self.invoke().stdout)
                with tempfile.TemporaryDirectory(
                    prefix="icg-macro-relocated-"
                ) as relocated:
                    shutil.copy2(self.header, Path(relocated) / self.header.name)
                    second = self.success(
                        self.invoke(cwd=relocated, options=["--source-root", relocated])
                    )
                    for key in ("declarations", "types"):
                        self.assertEqual(document[key], second[key])

    def test_anonymous_namespace_is_unique_per_translation_unit(self):
        (self.root / "types.hh").write_text(
            "namespace { struct Local { int value; }; }\n"
            "namespace { using Handle = Local*; }\n"
            "namespace Public { struct Shared {}; }\n"
        )
        source = '#include "types.hh"\nstruct Model { Handle p; Public::Shared s; };\n'
        self.header.write_text(source)
        (self.root / "other.hh").write_text(source)
        first = self.success(self.invoke())
        second = self.success(self.invoke(input="other.hh"))
        for document in (first, second):
            anonymous = [
                n
                for n in document["declarations"]
                if n["kind"] == "namespace" and n["anonymous"]
            ]
            self.assertEqual(len(anonymous), 1)
            self.assertEqual(len(anonymous[0]["reopening_sources"]), 2)
        first_local = {
            n["id"] for n in first["declarations"] if n["identity_kind"] == "source"
        }
        second_local = {
            n["id"] for n in second["declarations"] if n["identity_kind"] == "source"
        }
        self.assertEqual(len(first_local), 4)
        self.assertTrue(first_local.isdisjoint(second_local))
        self.assertEqual(
            self.declarations(first)["Public::Shared"]["id"],
            self.declarations(second)["Public::Shared"]["id"],
        )

    def test_anonymous_ids_survive_root_relocation_and_symlink_aliases(self):
        self.header.write_text((HERE / "fixtures/contexts.hh").read_text())
        first = self.success(self.invoke())
        with tempfile.TemporaryDirectory(prefix="icg-context-relocated-") as relocated:
            target = Path(relocated)
            shutil.copy2(self.header, target / self.header.name)
            alias = target / "alias"
            alias.symlink_to(target, target_is_directory=True)
            for root in (target, alias):
                with self.subTest(root=root):
                    second = self.success(
                        self.invoke(cwd=root, options=["--source-root", str(root)])
                    )
                    for key in ("declarations", "types"):
                        self.assertEqual(first[key], second[key])
                    self.assertEqual(
                        first["provenance"]["graph_digest"],
                        second["provenance"]["graph_digest"],
                    )
                    self.assertNotEqual(
                        first["provenance"]["input_digest"],
                        second["provenance"]["input_digest"],
                    )

    def test_unimplemented_namespace_members_fail_closed(self):
        for source in (
            "namespace N { struct Good {}; int variable; }",
            "namespace N { struct Good {}; } using namespace N;",
            "namespace N { struct Good {}; } using N::Good;",
        ):
            with self.subTest(source=source):
                self.header.write_text(source)
                self.failure(self.invoke(), "ICG_UNSUPPORTED_DECLARATION")

    def test_anonymous_command_line_macro_has_no_fabricated_source_identity(self):
        self.header.write_text("typedef ANON Point;\n")
        self.failure(
            self.invoke(["-DANON=struct { int value; }"]), "ICG_IDENTITY_SOURCE"
        )

    def test_failed_references_in_bases_nested_types_and_callables_collect_errors(self):
        self.header.write_text(
            "namespace { BASE struct Methods { METHODS }; }\n"
            "struct Derived : virtual Base { ~Derived() override; };\n"
            "struct HasNested { NESTED value; static int rejected; };\n"
        )
        report = self.failure(
            self.invoke([
                "-DBASE=struct Base { virtual ~Base(); };",
                "-DMETHODS=Methods(); Methods(const Methods&); virtual ~Methods();",
                "-DNESTED=struct { int value; }",
            ]),
            "ICG_IDENTITY_SOURCE",
        )
        # Unrepresentable anchors exercise empty request results in direct and
        # virtual bases, overrides, explicit special members, and nested IDs.
        self.assertGreaterEqual(
            sum(d["code"] == "ICG_IDENTITY_SOURCE" for d in report["diagnostics"]), 4
        )
        self.assertTrue(
            any(
                d["code"] == "ICG_UNSUPPORTED_DECLARATION" and "members" in d["message"]
                for d in report["diagnostics"]
            ),
            report,
        )

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
            self.assertEqual(
                first["provenance"]["graph_digest"],
                second["provenance"]["graph_digest"],
            )

    def test_scoped_unscoped_enums_and_duplicate_values(self):
        self.header.write_text(
            "enum Plain { Negative=-7, Next, Same=Next, Last=100 };\n"
            "enum class Scoped : unsigned short { Zero, High=65535 };\n"
            "using Alias = Scoped; struct Model { const Alias state; Plain values[2]; };\n"
        )
        document = self.success(self.invoke())
        nodes = self.declarations(document)
        plain, scoped = nodes["Plain"], nodes["Scoped"]
        self.assertFalse(plain["scoped"])
        self.assertFalse(plain["underlying_fixed"])
        self.assertTrue(plain["underlying_signed"])
        self.assertEqual(
            [e["value"] for e in plain["enumerators"]], ["-7", "-6", "-6", "100"]
        )
        self.assertEqual(
            [e["name"] for e in plain["enumerators"]],
            ["Negative", "Next", "Same", "Last"],
        )
        self.assertTrue(scoped["scoped"])
        self.assertTrue(scoped["underlying_fixed"])
        self.assertFalse(scoped["underlying_signed"])
        self.assertEqual((scoped["size_bits"], scoped["alignment_bits"]), (16, 16))
        types = {t["id"]: t for t in document["types"]}
        alias = types[nodes["Model::state"]["type_id"]]
        canonical = types[alias["canonical_id"]]
        self.assertEqual(canonical["kind"], "enum")
        self.assertEqual(canonical["declaration_id"], scoped["id"])
        self.assertTrue(canonical["qualifiers"]["const"])

    def test_enum_integrals_remain_exact_beyond_json_and_64_bits(self):
        self.header.write_text(
            "enum class Unsigned : unsigned long long { Max=18446744073709551615ULL, Exact=9007199254740993ULL };\n"
            "enum Signed : long long { Min=(-9223372036854775807LL-1) };\n"
            "enum class Wide : unsigned __int128 { High=((unsigned __int128)1 << 100), Max=~(unsigned __int128)0 };\n"
            "enum class WideSigned : __int128 { Low=-((__int128)1 << 100) };\n"
        )
        nodes = self.declarations(self.success(self.invoke()))
        self.assertEqual(
            [e["value"] for e in nodes["Unsigned"]["enumerators"]],
            [str(2**64 - 1), str(2**53 + 1)],
        )
        self.assertEqual(nodes["Signed"]["enumerators"][0]["value"], str(-(2**63)))
        self.assertEqual(
            [e["value"] for e in nodes["Wide"]["enumerators"]],
            [str(2**100), str(2**128 - 1)],
        )
        self.assertEqual(nodes["WideSigned"]["enumerators"][0]["value"], str(-(2**100)))
        self.assertEqual(nodes["Wide"]["size_bits"], 128)

    def test_opaque_enum_is_complete_without_a_definition(self):
        self.header.write_text(
            "enum class State; enum Mode : unsigned char;\n"
            "struct Sample { State state; Mode mode; };\n"
        )
        nodes = self.declarations(self.success(self.invoke()))
        for name, size in (("State", 32), ("Mode", 8)):
            node = nodes[name]
            self.assertTrue(node["complete"])
            self.assertFalse(node["definition"])
            self.assertTrue(node["underlying_fixed"])
            self.assertEqual(node["enumerators"], [])
            self.assertEqual(node["size_bits"], size)

    def test_enum_redeclarations_fold_to_definition_and_keep_identity(self):
        self.header.write_text("enum class State : int;\n")
        first = self.success(self.invoke())
        self.header.write_text(
            "enum class State : int;\nenum class State : int { On=2 };\nenum class State : int;\n"
        )
        second = self.success(self.invoke())
        enum = self.declarations(second)["State"]
        self.assertEqual(enum["id"], self.declarations(first)["State"]["id"])
        self.assertTrue(enum["definition"])
        self.assertEqual(enum["source"]["spelling"]["line"], 2)
        self.assertEqual(len(second["declarations"]), 1)

    def test_nested_and_referenced_enums_preserve_selection_and_context(self):
        (self.root / "types.hh").write_text(
            "namespace N { enum class Used { A }; struct Unused { void run(); }; }\n"
        )
        self.header.write_text(
            '#include "types.hh"\nnamespace N { struct Holder { enum E { Item }; E value; Used used; }; }\n'
        )
        nodes = self.declarations(self.success(self.invoke()))
        self.assertNotIn("N::Unused", nodes)
        self.assertEqual(
            nodes["N::Holder::E"]["semantic_parent_id"], nodes["N::Holder"]["id"]
        )
        self.assertEqual(
            nodes["N::Holder"]["nested_declaration_ids"], [nodes["N::Holder::E"]["id"]]
        )
        self.assertIn(nodes["N::Used"]["id"], nodes["N"]["declaration_ids"])

    def test_enum_underlying_alias_bool_and_character_types(self):
        self.header.write_text(
            "using Byte = unsigned char; enum class E : Byte { Max=255 };\n"
            "enum class Boolean : bool { No=false, Yes=true };\n"
            "enum class Character : char { A=65 }; enum class WideChar : wchar_t { A=65 };\n"
        )
        nodes = self.declarations(self.success(self.invoke()))
        self.assertEqual(nodes["E"]["size_bits"], 8)
        self.assertFalse(nodes["E"]["underlying_signed"])
        self.assertEqual(
            [e["value"] for e in nodes["Boolean"]["enumerators"]], ["0", "1"]
        )

    def test_enum_comments_attributes_and_macro_sources(self):
        self.header.write_text(
            "#define ITEM(NAME) NAME = 3\n/// enum note\n"
            "enum E {\n/// value note\n"
            'Value [[clang::annotate("enum-value")]] = 2,\nITEM(Macro)\n};\n'
        )
        node = self.declarations(self.success(self.invoke()))["E"]
        self.assertEqual(node["annotations"][0]["payload"], "/// enum note")
        first, macro = node["enumerators"]
        self.assertEqual(
            [a["payload"] for a in first["annotations"]],
            ["/// value note", "enum-value"],
        )
        self.assertTrue(macro["source"]["macro_expansion"])
        self.assertEqual(macro["value"], "3")

    def test_enum_layout_honors_alignment_and_packing_attributes(self):
        self.header.write_text(
            "enum __attribute__((aligned(16))) Aligned { A };\n"
            "enum __attribute__((packed)) Packed { P=3 };\n"
            "static_assert(alignof(Aligned)==16); static_assert(sizeof(Aligned)==4);\n"
            "static_assert(alignof(Packed)==1); static_assert(sizeof(Packed)==1);\n"
        )
        nodes = self.declarations(
            self.success(self.invoke(["--target=x86_64-unknown-linux-gnu"]))
        )
        self.assertEqual(
            (nodes["Aligned"]["size_bits"], nodes["Aligned"]["alignment_bits"]),
            (32, 128),
        )
        self.assertEqual(
            (nodes["Packed"]["size_bits"], nodes["Packed"]["alignment_bits"]), (8, 8)
        )

    def test_anonymous_enums_and_bitfields_keep_relocatable_distinct_ids(self):
        self.header.write_text(
            "typedef enum { One } First; typedef enum { Two } Second;\n"
            "#define PADDING unsigned : 1;\n"
            "#define TWO PADDING PADDING\n"
            "namespace { struct Model { TWO enum { Three } value; }; }\n"
        )
        first_result = self.invoke()
        first = self.success(first_result)
        self.assertEqual(first_result.stdout, self.invoke().stdout)
        enums = [n for n in first["declarations"] if n["kind"] == "enum"]
        self.assertEqual(len(enums), 3)
        self.assertTrue(
            all(n["anonymous"] and n["identity_kind"] == "source" for n in enums)
        )
        bits = [n for n in first["declarations"] if n.get("bitfield")]
        self.assertEqual(len(bits), 2)
        self.assertNotEqual(bits[0]["id"], bits[1]["id"])
        with tempfile.TemporaryDirectory(prefix="icg-enum-relocated-") as relocated:
            shutil.copy2(self.header, Path(relocated) / self.header.name)
            second = self.success(
                self.invoke(cwd=relocated, options=["--source-root", relocated])
            )
            for key in ("types", "declarations"):
                self.assertEqual(first[key], second[key])

    def test_bitfields_keep_padding_separators_offsets_and_capabilities(self):
        self.header.write_text(
            "struct Bits { unsigned a:3; unsigned :2; unsigned b:3; unsigned :0; signed c:4; bool d:1; };\n"
        )
        document = self.success(self.invoke(["--target=x86_64-unknown-linux-gnu"]))
        nodes = {n["id"]: n for n in document["declarations"]}
        record = self.declarations(document)["Bits"]
        fields = [nodes[i] for i in record["field_ids"]]
        self.assertEqual([f["name"] for f in fields], ["a", "", "b", "", "c", "d"])
        self.assertEqual([f["bit_width"] for f in fields], [3, 2, 3, 0, 4, 1])
        self.assertEqual([f["offset_bits"] for f in fields], [0, 3, 5, 32, 32, 36])
        self.assertEqual(record["size_bits"], 64)
        for field in fields:
            self.assertTrue(field["bitfield"])
            self.assertFalse(field["anonymous_member"])
            self.assertEqual(
                field["capabilities"],
                [
                    {
                        "name": "field-address",
                        "status": "unsupported",
                        "reason_code": "BITFIELD_NOT_ADDRESSABLE",
                    }
                ],
            )
            if not field["name"]:
                self.assertEqual(field["identity_kind"], "source")

    def test_packed_union_and_overwide_bitfield_layout(self):
        self.header.write_text(
            "struct __attribute__((packed)) Packed { unsigned a:3; unsigned b:10; unsigned char tail; };\n"
            "union Overlay { unsigned a:3; unsigned b:5; };\n"
            "struct Wide { unsigned char value:12; };\n"
        )
        document = self.success(self.invoke(["--target=x86_64-unknown-linux-gnu"]))
        nodes = self.declarations(document)
        self.assertEqual(
            (nodes["Packed"]["size_bits"], nodes["Packed"]["alignment_bits"]), (24, 8)
        )
        self.assertEqual(nodes["Packed::b"]["offset_bits"], 3)
        self.assertEqual(nodes["Packed::tail"]["offset_bits"], 16)
        self.assertEqual(
            nodes["Overlay::a"]["offset_bits"], nodes["Overlay::b"]["offset_bits"]
        )
        self.assertEqual(nodes["Wide::value"]["bit_width"], 12)
        self.assertTrue(
            any(d["severity"] == "warning" for d in document["diagnostics"])
        )

    def test_enum_bitfield_types_width_expressions_and_annotations(self):
        self.header.write_text(
            "enum class State : unsigned char { Ready=3 };\n#define WIDTH 2\n"
            'struct Sample { /// field note\n[[clang::annotate("bits")]] State state:WIDTH; const unsigned count:(1+2); };\n'
        )
        document = self.success(self.invoke())
        nodes = self.declarations(document)
        field = nodes["Sample::state"]
        self.assertEqual(field["bit_width"], 2)
        self.assertEqual(
            [a["payload"] for a in field["annotations"]], ["/// field note", "bits"]
        )
        self.assertEqual(nodes["Sample::count"]["bit_width"], 3)
        self.assertIn(
            nodes["State"]["type_id"],
            {t["id"] for t in document["types"] if t["kind"] == "enum"},
        )

    def test_invalid_or_dependent_enums_and_bitfields_publish_nothing(self):
        for source in (
            "enum class E : unsigned char { Bad=256 };",
            "enum class E : unsigned { Bad=-1 };",
            "struct Bits { unsigned zero:0; };",
            "struct Bits { unsigned negative:-1; };",
            "struct Bits { float invalid:2; };",
            "template<int N> struct Bits { unsigned value:N; }; struct Bad { Bits<-1> bits; };",
            "template<class T> struct Model { enum class E : T { A }; }; struct Bad { Model<float> model; };",
        ):
            with self.subTest(source=source):
                self.header.write_text(source)
                self.failure(self.invoke())

    def test_checked_in_enum_and_bitfield_fixture(self):
        self.header.write_text((HERE / "fixtures/enums-bitfields.hh").read_text())
        document = self.success(self.invoke())
        nodes = self.declarations(document)
        self.assertEqual(
            nodes["model::Limits"]["enumerators"][0]["value"], str(2**64 - 1)
        )
        self.assertFalse(nodes["model::Opaque"]["definition"])
        self.assertEqual(nodes["model::Packet::count"]["bit_width"], 5)

    def callable_fixture(self):
        self.header.write_text((HERE / "fixtures/callables.hh").read_text())
        return self.success(self.invoke())

    def callables(self, document, name):
        return [
            n
            for n in document["declarations"]
            if n["kind"] == "callable" and n["qualified_name"] == name
        ]

    def special_members(self, document, name):
        return {
            s["kind"]: s for s in self.declarations(document)[name]["special_members"]
        }

    def test_callable_overloads_flags_and_member_ownership(self):
        document = self.callable_fixture()
        nodes = self.declarations(document)
        values = self.callables(document, "callable_model::Methods::value")
        self.assertEqual(len(values), 2)
        self.assertEqual(
            {(v["const"], v["ref_qualifier"]) for v in values},
            {(True, "lvalue"), (False, "rvalue")},
        )
        ctors = self.callables(document, "callable_model::Methods::Methods")
        self.assertEqual(len(ctors), 3)
        self.assertEqual(len({n["id"] for n in ctors}), 3)
        self.assertTrue(all(n["identity_kind"] == "usr" for n in ctors))
        self.assertEqual(sum(n["explicit"] for n in ctors), 1)
        self.assertTrue(all(n["return_type_id"] is None for n in ctors))
        self.assertTrue(nodes["callable_model::Methods::watch"]["volatile"])
        self.assertTrue(nodes["callable_model::Methods::scale"]["static"])
        self.assertTrue(nodes["callable_model::Methods::twice"]["constexpr"])
        self.assertTrue(nodes["callable_model::Methods::twice"]["definition"])
        conversion = nodes["callable_model::Methods::operator bool"]
        self.assertEqual(
            (
                conversion["callable_kind"],
                conversion["explicit"],
                conversion["noexcept"],
            ),
            ("conversion", True, "true"),
        )
        owner = nodes["callable_model::Methods"]
        self.assertEqual(
            set(owner["callable_ids"]),
            {
                n["id"]
                for n in document["declarations"]
                if n["kind"] == "callable"
                and n.get("semantic_parent_id") == owner["id"]
            },
        )
        self.assertEqual(owner["nested_declaration_ids"], [])

    def test_callable_redeclarations_defaults_and_parameter_adjustment(self):
        document = self.callable_fixture()
        functions = self.callables(document, "callable_model::free")
        self.assertEqual(len(functions), 2)
        function = next(f for f in functions if len(f["redeclarations"]) == 2)
        self.assertEqual(function["parameters"][0]["name"], "renamed")
        self.assertEqual(
            [r["parameters"][0]["name"] for r in function["redeclarations"]],
            ["value", "renamed"],
        )
        default = function["parameters"][0]
        self.assertTrue(default["has_default"])
        self.assertEqual(default["default_origin"], "inherited")
        self.assertEqual(default["default_spelling"], "(2 + 3)")
        self.assertTrue(default["default_source"]["macro_expansion"])
        self.assertEqual(
            [r["parameters"][0]["default_origin"] for r in function["redeclarations"]],
            ["written", "inherited"],
        )
        nodes = self.declarations(document)
        types = {t["id"]: t for t in document["types"]}
        array = nodes["callable_model::arrays"]["parameters"][0]
        self.assertEqual(types[array["type_id"]]["kind"], "pointer")
        self.assertEqual(types[array["original_type_id"]]["kind"], "array")
        self.assertTrue(nodes["callable_model::varargs"]["variadic"])

    def test_callable_out_of_line_definition_preserves_both_contexts(self):
        document = self.callable_fixture()
        late = self.callables(document, "callable_model::Late::Late")[0]
        self.assertTrue(late["defaulted"])
        self.assertTrue(late["user_provided"])
        self.assertTrue(late["definition"])
        self.assertEqual(len(late["redeclarations"]), 2)
        self.assertNotEqual(late["semantic_parent_id"], late["lexical_parent_id"])
        self.assertEqual(
            late["redeclarations"][0]["lexical_parent_id"], late["semantic_parent_id"]
        )

    def test_callable_annotations_survive_redeclarations(self):
        self.header.write_text(
            '/// first\nvoid f([[clang::annotate("one")]] int value=2);\n/// second\nvoid f(int renamed);\n'
        )
        node = self.callables(self.success(self.invoke()), "f")[0]
        self.assertEqual(
            [a["payload"] for a in node["annotations"]], ["/// first", "/// second"]
        )
        self.assertEqual(
            node["redeclarations"][0]["parameters"][0]["annotations"][0]["payload"],
            "one",
        )

    def test_local_comments_preserve_empty_and_uncommented_redeclarations(self):
        self.header.write_text(
            "/** first */\nvoid f();\n"
            "/** */\nvoid f();\n"
            "void f();\n"
            "/** last */\nvoid f();\n"
            "struct A { int value; ///< trailing\n};\n"
        )
        document = self.success(self.invoke())
        node = self.callables(document, "f")[0]
        self.assertEqual(
            [
                (a["payload"], a["source"]["spelling"]["line"])
                for a in node["annotations"]
            ],
            [("/** first */", 1), ("/** */", 3), ("/** last */", 6)],
        )
        field = self.declarations(document)["A::value"]
        self.assertEqual(field["annotations"][0]["payload"], "///< trailing")

    def test_implicit_special_members_are_materialized_not_assumed_available(self):
        document = self.callable_fixture()
        plain = self.special_members(document, "callable_model::Plain")
        self.assertEqual(len(plain), 6)
        self.assertTrue(
            all(s["state"] == "implicit" and not s["deleted"] for s in plain.values())
        )
        ref = self.special_members(document, "callable_model::Reference")
        self.assertTrue(ref["default_constructor"]["deleted"])
        self.assertTrue(ref["copy_assignment"]["deleted"])
        self.assertTrue(ref["move_assignment"]["deleted"])
        self.assertFalse(ref["copy_constructor"]["deleted"])
        self.assertEqual(
            self.special_members(document, "callable_model::NoDefault")[
                "default_constructor"
            ]["state"],
            "suppressed",
        )
        self.assertEqual(
            self.special_members(document, "callable_model::UserDtor")[
                "move_constructor"
            ]["state"],
            "suppressed",
        )
        self.assertEqual(
            self.special_members(document, "callable_model::ContainsThrows")[
                "default_constructor"
            ]["noexcept"],
            "false",
        )

    def test_user_special_members_keep_deletion_access_and_defaulting_separate(self):
        document = self.callable_fixture()
        declarations = {n["id"]: n for n in document["declarations"]}
        slot = self.special_members(document, "callable_model::MoveOnly")[
            "copy_constructor"
        ]
        self.assertEqual(slot["state"], "user_declared")
        self.assertIsNone(slot["deleted"])
        self.assertTrue(declarations[slot["declaration_ids"][0]]["deleted"])
        private = self.callables(
            document, "callable_model::InaccessibleCtor::InaccessibleCtor"
        )[0]
        self.assertEqual(private["access"], "private")
        self.assertTrue(private["defaulted"])
        self.assertFalse(private["deleted"])
        self.assertFalse(private["user_provided"])

    def test_overrides_include_implicit_virtual_destructor_targets(self):
        self.header.write_text(
            "struct Base { virtual ~Base()=default; virtual Base* run()=0; };\nstruct Middle:Base {};\nstruct Leaf:Middle { ~Leaf()=default; Leaf* run() final; };\n"
        )
        nodes = self.declarations(self.success(self.invoke()))
        self.assertTrue(nodes["Base"]["abstract"])
        self.assertFalse(nodes["Leaf"]["abstract"])
        self.assertEqual(
            nodes["Leaf::run"]["overridden_declaration_ids"], [nodes["Base::run"]["id"]]
        )
        self.assertEqual(
            nodes["Leaf::~Leaf"]["overridden_implicit_destructor_record_ids"],
            [nodes["Middle"]["id"]],
        )
        middle = next(
            s for s in nodes["Middle"]["special_members"] if s["kind"] == "destructor"
        )
        self.assertTrue(middle["virtual"])

    def test_validator_reconstructs_nearest_overrides_with_fresh_digest(self):
        self.header.write_text(
            "struct A { virtual void f(int); virtual ~A()=default; };\n"
            "struct B:A { void f(int); void f(double); };\n"
            "struct C:B { void f(int); ~C()=default; };\n"
        )
        document = self.success(self.invoke())
        for name, key in (
            ("C::f", "overridden_declaration_ids"),
            ("C::~C", "overridden_implicit_destructor_record_ids"),
        ):
            with self.subTest(name=name):
                changed = copy.deepcopy(document)
                node = self.declarations(changed)[name]
                self.assertTrue(node[key])
                node[key] = []
                changed["provenance"]["graph_digest"] = VALIDATOR.graph_digest(changed)
                with self.assertRaisesRegex(ValueError, "override targets"):
                    VALIDATOR.validate(SCHEMA, changed)

    def test_partial_specialization_display_uses_written_parameters(self):
        self.header.write_text(
            "namespace model { template<class T> struct Choice {}; "
            "template<class Element> struct Choice<Element *> {}; }\n"
        )
        nodes = self.declarations(self.success(self.invoke()))
        partial = nodes["model::Choice<Element *>"]
        self.assertEqual(partial["pattern_spelling"], "model::Choice<Element *>")

    def legacy_comparison(self, case_id):
        sys.path.insert(0, str(ROOT / "tools/icg_baseline"))
        try:
            import differential
            import native
        finally:
            sys.path.pop(0)
        corpus = json.loads((differential.REFERENCE.parent / "corpus.json").read_text())
        case = next(case for case in corpus["cases"] if case["id"] == case_id)
        self.header.write_bytes((ROOT / case["header"]).read_bytes())
        document = self.success(self.invoke())
        snapshot = differential.REFERENCE / case_id / "cold.json"
        artifacts = json.loads(snapshot.read_text())["artifacts"]
        metadata = next(
            item for item in artifacts.values() if item["group"] == "legacy-metadata"
        )
        legacy = differential.b.artifact_text(snapshot, metadata)
        report = differential.compare(document, legacy, case_id)
        return differential, native, document, legacy, report, case

    def test_real_legacy_metadata_matches_fields_and_rejects_changed_layout(self):
        differential, _, document, legacy, report, _ = self.legacy_comparison(
            "embedded"
        )
        self.assertEqual(sum(map(len, report["records"].values())), 6)
        self.assertEqual(len(report["enums"]), 2)
        for before, after in (
            ("8, NULL", "9, NULL"),
            ("{{5, 27}", "{{4, 28}"),
            ('"d", "double"', '"d", "float"'),
            ("ATTRIBUTES attrTopClass[]", "UNRECOGNIZED attrTopClass[]"),
            ('"TopClass::one", 0, 0x40000000', '"TopClass::one", 1, 0x40000000'),
            ('"TopClass::one", 0, 0x40000000', '"TopClass::one", 0, 0x0'),
            ('"TopClass::one"', '"TopClass::wrong"'),
            ('{"", 0, 0x0}', '{"", 1, 0x0}'),
            (
                "ENUM_ATTR enumTopClass__PublicEnum[]",
                "UNKNOWN enumTopClass__PublicEnum[]",
            ),
        ):
            with self.subTest(before=before):
                self.assertIn(before, legacy)
                with self.assertRaises(ValueError):
                    differential.compare(
                        document, legacy.replace(before, after), "embedded"
                    )

    def test_compiled_legacy_metadata_matches_native_layout_and_facts(self):
        if LAYOUT_COMPILER is None:
            self.skipTest("native conformance requires --layout-compiler")
        for case_id in ("anonymous-enum", "deleted-constructor", "embedded"):
            with self.subTest(case=case_id):
                _, native, document, legacy, report, case = self.legacy_comparison(
                    case_id
                )
                evidence = native.capture(
                    document, legacy, report, case, self.root / case_id, LAYOUT_COMPILER
                )
                observed = evidence["observations"]
                self.assertEqual(len(observed["records"]), len(report["records"]))
                self.assertTrue(evidence["input_sha256"])
                self.assertTrue(
                    all(command["returncode"] == 0 for command in evidence["commands"])
                )
                if case_id != "embedded":
                    continue
                record_index = next(
                    i
                    for i, item in enumerate(observed["records"])
                    if item["name"] == "TopClass"
                )
                mutations = [
                    (["records", record_index, "size_bytes"], 24),
                    (["records", record_index, "legacy_size_bytes"], 24),
                    (["records", record_index, "alignment_bytes"], 4),
                    (["records", record_index, "fields", 2, "size_bytes"], 4),
                    (["records", record_index, "fields", 2, "offset_bytes"], 9),
                    (["records", record_index, "fields", 2, "units_map_units"], "1"),
                    (["records", record_index, "fields", 0, "shift"], 26),
                    (["records", record_index, "native_fields", 0, "width"], 4),
                    (["records", record_index, "native_fields", 0, "offset_bits"], 1),
                    (["enums", 0, "rows", 0, "native_value"], "3"),
                    (["enums", 0, "rows", 0, "value"], "3"),
                    (["enums", 0, "rows", 0, "mods"], 0),
                    (["enums", 0, "signed"], True),
                    (["enums", 0, "size_bytes"], 8),
                    (["enums", 0, "rows"], []),
                    (["records"], []),
                ]
                for path, value in mutations:
                    with self.subTest(path=path):
                        changed = copy.deepcopy(observed)
                        target = changed
                        for key in path[:-1]:
                            target = target[key]
                        self.assertNotEqual(target[path[-1]], value)
                        target[path[-1]] = value
                        with self.assertRaises(ValueError):
                            native.validate(document, report, changed)
                # A legitimately regenerated digest cannot mask a layout error
                # in a future producer: compare the facts with native evidence.
                changed = copy.deepcopy(document)
                self.declarations(changed)["TopClass"]["size_bits"] = 192
                changed["provenance"]["graph_digest"] = VALIDATOR.graph_digest(changed)
                VALIDATOR.validate(SCHEMA, changed)
                with self.assertRaisesRegex(ValueError, "native size_bytes"):
                    native.validate(changed, report, observed)

    def test_native_probe_rejects_bad_size_thunk_and_unmodeled_metadata(self):
        if LAYOUT_COMPILER is None:
            self.skipTest("native conformance requires --layout-compiler")
        differential, native, document, legacy, report, case = self.legacy_comparison(
            "embedded"
        )
        output = self.root / "native-failure"
        output.mkdir()
        for before, after, diagnostic in (
            ("return sizeof(TopClass) ;", "return 1 ;", "native legacy_size_bytes"),
            (
                "NULL,  NULL, NULL, NULL, NULL, NULL, NULL, NULL",
                '"unexpected",  NULL, NULL, NULL, NULL, NULL, NULL, NULL',
                "unsupported compiled ATTRIBUTES metadata",
            ),
        ):
            with self.subTest(before=before):
                self.assertIn(before, legacy)
                changed = legacy.replace(before, after)
                # Both corruptions used to be invisible to the text comparison.
                self.assertEqual(
                    differential.compare(document, changed, "embedded"), report
                )
                (output / "native.json").write_text('{"stale": true}')
                with self.assertRaisesRegex(ValueError, diagnostic):
                    native.capture(
                        document, changed, report, case, output, LAYOUT_COMPILER
                    )
                self.assertFalse((output / "native.json").exists())
                self.assertTrue((output / "commands.json").is_file())

    def test_pod_uses_language_traits_on_linux_and_darwin_targets(self):
        self.header.write_text("""
struct Deleted { Deleted() = delete; int value; };
class Private { Private() = default; public: int value; };
struct Explicit { explicit Explicit() = default; int value; };
struct Defaulted { Defaulted() = default; int value; };
struct NonTrivial { NonTrivial(); int value; };
enum PodTraits {
    DeletedPod = __is_pod(Deleted), PrivatePod = __is_pod(Private),
    ExplicitPod = __is_pod(Explicit), DefaultedPod = __is_pod(Defaulted),
    NonTrivialPod = __is_pod(NonTrivial)
};
""")
        # No platform headers: exercise the Darwin ABI even on a Linux host.
        # CXXRecordDecl::isPOD() is a TR1/layout query; it can disagree with
        # the C++17 language trait for deleted/private/defaulted constructors.
        for target in (
            "x86_64-unknown-linux-gnu",
            "x86_64-apple-darwin",
            "arm64-apple-darwin",
        ):
            with self.subTest(target=target):
                nodes = self.declarations(
                    self.success(self.invoke(["--target=" + target]))
                )
                traits = {
                    item["name"]: bool(int(item["value"]))
                    for item in nodes["PodTraits"]["enumerators"]
                }
                for name in (
                    "Deleted",
                    "Private",
                    "Explicit",
                    "Defaulted",
                    "NonTrivial",
                ):
                    self.assertEqual(nodes[name]["pod"], traits[name + "Pod"], name)
                    self.assertEqual(nodes[name]["pod"], name != "NonTrivial", name)

    def lifecycle_comparison(self):
        if LAYOUT_COMPILER is None:
            self.skipTest("lifecycle conformance requires --layout-compiler")
        sys.path.insert(0, str(ROOT / "tools/icg_baseline"))
        try:
            import lifecycle
        finally:
            sys.path.pop(0)
        self.header.write_bytes(lifecycle.HEADER.read_bytes())
        return lifecycle, self.success(self.invoke()), lifecycle.reference()

    def test_captured_lifecycle_wrappers_match_facts_and_observed_events(self):
        lifecycle, document, legacy = self.lifecycle_comparison()
        evidence = lifecycle.check(
            document,
            legacy,
            self.root / "lifecycle",
            LAYOUT_COMPILER,
            sanitize=LIFECYCLE_SANITIZERS,
            leak_check=LIFECYCLE_LEAK_CHECK,
        )
        observed = evidence["observations"]
        self.assertEqual(len(observed["executions"]), 12)
        private = next(
            item
            for item in observed["records"]
            if item["name"] == "IcgLifecyclePrivateDestructor"
        )
        self.assertTrue(private["default_placement"])
        self.assertFalse(private["default_constructible"])
        self.assertFalse(private["destructible"])
        self.assertEqual(
            evidence["policy"]["IcgLifecycleDeleted"]["allocate"], "raw_storage"
        )
        for path, value in (
            (["records", 2, "default_placement"], True),
            (["records", 3, "symbols", "allocate"], True),
            (["records", 4, "symbols", "destruct"], True),
            (["records", 5, "virtual_destructor"], False),
            (["executions", 0, "events"], []),
            (["executions", 4, "events", 1, "offset_bytes"], 0),
            (["executions", 4, "events", 3, "value"], 0),
            (["executions", 2, "zeroed"], False),
            (
                ["executions", 11, "events"],
                [{"kind": 2, "value": 0, "offset_bytes": 0}],
            ),
        ):
            with self.subTest(path=path):
                changed = copy.deepcopy(observed)
                target = changed
                for key in path[:-1]:
                    target = target[key]
                self.assertNotEqual(target[path[-1]], value)
                target[path[-1]] = value
                with self.assertRaises(ValueError):
                    lifecycle.validate(document, changed)
        # Regenerating a legitimate producer digest must not hide wrong facts.
        for name, key, value in (
            ("IcgLifecycleDeleted::IcgLifecycleDeleted", "deleted", False),
            (
                "IcgLifecyclePrivateDestructor::~IcgLifecyclePrivateDestructor",
                "access",
                "public",
            ),
        ):
            with self.subTest(name=name):
                changed = copy.deepcopy(document)
                self.declarations(changed)[name][key] = value
                changed["provenance"]["graph_digest"] = VALIDATOR.graph_digest(changed)
                VALIDATOR.validate(SCHEMA, changed)
                with self.assertRaisesRegex(ValueError, "traits differ"):
                    lifecycle.validate(changed, observed)

    def test_compiled_lifecycle_mutations_fail_without_success_report(self):
        lifecycle, document, legacy = self.lifecycle_comparison()
        output = self.root / "lifecycle-failure"
        output.mkdir()
        for before, after, message in (
            (
                "new(&temp[ii]) IcgLifecycleTracked();",
                "new(&temp[ii]) IcgLifecycleTracked(); temp[ii].value = -1;",
                "lifecycle event",
            ),
            (
                "temp[ii].~IcgLifecycleTracked();",
                "if (ii + 1 < num) temp[ii].~IcgLifecycleTracked();",
                "lifecycle event",
            ),
            (
                "temp[ii].~IcgLifecycleTracked();",
                "temp[num - ii - 1].~IcgLifecycleTracked();",
                "lifecycle event",
            ),
        ):
            with self.subTest(after=after):
                self.assertIn(before, legacy)
                (output / "lifecycle.json").write_text('{"stale":true}')
                with self.assertRaisesRegex(ValueError, message):
                    lifecycle.check(
                        document,
                        legacy.replace(before, after),
                        output,
                        LAYOUT_COMPILER,
                        sanitize=LIFECYCLE_SANITIZERS,
                        leak_check=LIFECYCLE_LEAK_CHECK,
                    )
                self.assertFalse((output / "lifecycle.json").exists())
        added = (
            legacy
            + '\nextern "C" void io_src_destruct_IcgLifecyclePrivateDestructor(void*, int) {}\n'
        )
        with self.assertRaisesRegex(ValueError, "symbols or exact-operation traits"):
            lifecycle.check(
                document,
                added,
                output,
                LAYOUT_COMPILER,
                sanitize=LIFECYCLE_SANITIZERS,
                leak_check=LIFECYCLE_LEAK_CHECK,
            )

    def test_lifecycle_leak_sanitizer_detects_destructor_without_deallocation(self):
        if not LIFECYCLE_LEAK_CHECK:
            self.skipTest("LeakSanitizer runs in the explicit Linux reference lane")
        lifecycle, document, legacy = self.lifecycle_comparison()
        before = "delete (IcgLifecycleTracked*)address;"
        self.assertIn(before, legacy)
        changed = legacy.replace(
            before, "((IcgLifecycleTracked*)address)->~IcgLifecycleTracked();"
        )
        output = self.root / "lifecycle-leak"
        with self.assertRaisesRegex(ValueError, "LeakSanitizer: detected memory leaks"):
            lifecycle.check(
                document,
                changed,
                output,
                LAYOUT_COMPILER,
                sanitize=True,
                leak_check=True,
            )
        self.assertFalse((output / "lifecycle.json").exists())

    def test_memorymanager_rules_use_validated_facts_not_only_digests(self):
        _, document, _ = self.lifecycle_comparison()
        sys.path.insert(0, str(ROOT / "tools/icg_baseline"))
        try:
            import memorymanager as mm
        finally:
            sys.path.pop(0)
        expected = mm.expected(document)
        facts = self.root / "facts.json"
        observed = self.root / "memorymanager.json"
        facts.write_text(json.dumps(document))
        observed.write_text(json.dumps(expected))
        self.assertEqual(mm.validate(facts, observed)["executions"], 9)
        # Synthetic observations test rule rejection; the configured simulation
        # supplies the independent real observations in CI.
        for path, value in (
            (["executions", 0, "allocation", "allocator"], "new"),
            (["executions", 0, "allocation", "size_bytes"], 8),
            (["executions", 0, "allocation", "cpp"], False),
            (["executions", 0, "allocation", "named"], False),
            (["executions", 0, "delete_status"], False),
            (["executions", 0, "unregistered"], False),
            (["executions", 3, "allocation", "dimensions"], [1]),
            (["executions", 3, "events", 3, "registered"], True),
            (["executions", 6, "events_after_unregister"], 2),
            (["executions", 7, "events"], []),
            (["rejections", 0, "null"], False),
            (["allocation_delta"], 1),
        ):
            changed = copy.deepcopy(expected)
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            observed.write_text(json.dumps(changed))
            with (
                self.subTest(path=path),
                self.assertRaisesRegex(mm.b.BaselineError, "observations differ"),
            ):
                mm.validate(facts, observed)
        observed.write_text(json.dumps(expected))
        changed = copy.deepcopy(document)
        destructor = self.declarations(changed)[
            "IcgLifecycleTracked::~IcgLifecycleTracked"
        ]
        destructor["access"] = "private"
        changed["provenance"]["graph_digest"] = VALIDATOR.graph_digest(changed)
        VALIDATOR.validate(SCHEMA, changed)
        facts.write_text(json.dumps(changed))
        with self.assertRaisesRegex(mm.b.BaselineError, "policy differs"):
            mm.validate(facts, observed)

    def test_incomplete_record_special_member_states_are_unknown(self):
        self.header.write_text("struct Forward; void use(Forward*);\n")
        slots = self.special_members(self.success(self.invoke()), "Forward")
        self.assertTrue(
            all(
                s["state"] == "unknown" and s["deleted"] is None for s in slots.values()
            )
        )

    def test_callable_identity_determinism_relocation_and_named_reordering(self):
        self.header.write_text(
            "namespace { struct Local { Local()=default; Local(int); int operator+(int) const; }; void f(int); void f(double); }\n"
        )
        first_result = self.invoke()
        first = self.success(first_result)
        self.assertEqual(first_result.stdout, self.invoke().stdout)
        self.assertTrue(
            all(
                n["identity_kind"] == "source"
                for n in first["declarations"]
                if n["kind"] == "callable"
            )
        )
        with tempfile.TemporaryDirectory(
            prefix="icg-callables-relocated-"
        ) as relocated:
            shutil.copy2(self.header, Path(relocated) / self.header.name)
            second = self.success(
                self.invoke(cwd=relocated, options=["--source-root", relocated])
            )
            for key in ("declarations", "types"):
                self.assertEqual(first[key], second[key])
        self.header.write_text("void f(int); void f(double);\n")
        first_ids = {n["id"] for n in self.success(self.invoke())["declarations"]}
        self.header.write_text("void f(double); void f(int);\n")
        self.assertEqual(
            first_ids, {n["id"] for n in self.success(self.invoke())["declarations"]}
        )

    def test_static_functions_retain_linkage_and_translation_unit_identity(self):
        self.header.write_text(
            "static int f(int value=2); int f(int renamed); namespace { void hidden(); }\n"
        )
        first = self.success(self.invoke())
        function = self.callables(first, "f")[0]
        self.assertTrue(function["static"])
        self.assertEqual(function["linkage"], "internal")
        self.assertEqual(function["language_linkage"], "none")
        self.assertEqual(function["identity_kind"], "source")
        with tempfile.TemporaryDirectory(prefix="icg-static-relocated-") as relocated:
            shutil.copy2(self.header, Path(relocated) / self.header.name)
            second = self.success(
                self.invoke(cwd=relocated, options=["--source-root", relocated])
            )
            self.assertEqual(first["declarations"], second["declarations"])
        other = self.root / "other.hh"
        shutil.copy2(self.header, other)
        second = self.success(self.invoke(input="other.hh"))
        self.assertNotEqual(function["id"], self.callables(second, "f")[0]["id"])

    def test_language_linkage_blocks_are_transparent_and_explicit(self):
        self.header.write_text((HERE / "fixtures/linkage.hh").read_text())
        nodes = self.declarations(self.success(self.invoke()))
        self.assertEqual(nodes["c_function"]["language_linkage"], "c")
        self.assertEqual(
            nodes["linkage_fixture::namespaced_c_function"]["language_linkage"], "c"
        )
        self.assertEqual(nodes["cxx_function"]["language_linkage"], "c++")
        self.assertEqual(nodes["explicit_cxx_function"]["language_linkage"], "c++")
        self.assertEqual(
            nodes["linkage_fixture::namespaced_cxx_function"]["language_linkage"], "c++"
        )
        self.assertIn("CTime::day", nodes)
        self.assertIn("CTime::seconds", nodes)
        self.assertNotIn("LinkageSpec", {node["kind"] for node in nodes.values()})

    def test_defaulted_special_member_can_also_be_implicitly_deleted(self):
        self.header.write_text(
            "struct Model { const int value = 1; Model& operator=(const Model&) = default; };\n"
        )
        node = self.declarations(self.success(self.invoke()))["Model::operator="]
        self.assertTrue(node["defaulted"])
        self.assertTrue(node["deleted"])
        self.assertFalse(node["user_provided"])

    def test_actual_trick_simtime_header_extracts_through_linkage_blocks(self):
        source_root = ROOT / "include"
        result = subprocess.run(
            [
                str(EXTRACTOR),
                "--diagnostics-format=json",
                "--source-root",
                str(source_root),
                *(arg for root in PATH_ROOTS for arg in ("--path-root", root)),
                str(source_root / "trick/simtime_proto.h"),
                "--",
                "-I",
                str(source_root),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        document = self.success(result)
        functions = [
            node for node in document["declarations"] if node["kind"] == "callable"
        ]
        self.assertEqual(len(functions), 6)
        self.assertTrue(all(node["language_linkage"] == "c" for node in functions))
        self.assertIn("GMTTIME", self.declarations(document))

    def test_invalid_utf8_comment_fails_without_replacement_or_facts(self):
        self.header.write_bytes(
            b"/** caf\xe9 latin1 */\nstruct Model { int value; };\n"
        )
        result = self.invoke()
        report = self.failure(result, "ICG_INVALID_ENCODING")
        diagnostic = next(
            d for d in report["diagnostics"] if d["code"] == "ICG_INVALID_ENCODING"
        )
        self.assertIn("Comment", diagnostic["message"])
        self.assertIn("byte offset", diagnostic["message"])
        self.assertNotIn("\ufffd", result.stderr)

    def test_callable_type_dependencies_do_not_select_unrelated_header_functions(self):
        (self.root / "types.hh").write_text(
            "struct Used { int value; }; template<class T> void unrelated(T);\n"
        )
        self.header.write_text('#include "types.hh"\nUsed process(const Used&);\n')
        nodes = self.declarations(self.success(self.invoke()))
        self.assertIn("Used::value", nodes)
        self.assertNotIn("unrelated", nodes)

    def test_unsupported_callable_signatures_and_abis_fail_closed(self):
        for source in (
            "template<class T> T f(T);",
            "struct R { template<class T> R(T); };",
            "auto f() { return 1; }",
            "void f(int (*callback)(int));",
            "struct R {}; void f(int R::*);",
            "__attribute__((ms_abi)) int f(int);",
            "__attribute__((regparm(2))) int f(int);",
        ):
            with self.subTest(source=source):
                self.header.write_text(source)
                self.failure(self.invoke(["--target=x86_64-unknown-linux-gnu"]))

    def test_native_special_member_traits_match_the_focused_facts(self):
        if LAYOUT_COMPILER is None:
            self.skipTest("Pass --layout-compiler for native special-member probes")
        document = self.callable_fixture()
        assertions = []
        for name, trait, kind in (
            ("Plain", "is_default_constructible", "default_constructor"),
            ("Reference", "is_default_constructible", "default_constructor"),
            ("Reference", "is_copy_assignable", "copy_assignment"),
            ("Reference", "is_move_assignable", "move_assignment"),
            ("Constant", "is_default_constructible", "default_constructor"),
        ):
            slot = self.special_members(document, f"callable_model::{name}")[kind]
            self.assertEqual(slot["state"], "implicit")
            value = "false" if slot["deleted"] else "true"
            assertions.append(
                f'static_assert(std::{trait}<callable_model::{name}>::value == {value}, "{name}/{kind}");'
            )
        throws = self.special_members(document, "callable_model::ContainsThrows")[
            "default_constructor"
        ]
        assertions.append(
            f'static_assert(std::is_nothrow_default_constructible<callable_model::ContainsThrows>::value == {throws["noexcept"]}, "exception specification");'
        )
        assertions.extend([
            'static_assert(std::is_move_constructible<callable_model::UserDtor>::value, "copy can bind an rvalue despite suppressed move declaration");',
            'static_assert(!std::is_default_constructible<callable_model::InaccessibleCtor>::value, "nondeleted is not accessible");',
            'static_assert(!std::is_copy_constructible<callable_model::MoveOnly>::value, "deleted copy");',
            'static_assert(std::is_move_constructible<callable_model::MoveOnly>::value, "defaulted move");',
            'static_assert(!std::is_destructible<callable_model::DeletedDtor>::value, "deleted destructor");',
            'static_assert(std::is_abstract<callable_model::Base>::value, "abstract base");',
        ])
        probe, executable = self.root / "traits.cpp", self.root / "traits-probe"
        probe.write_text(
            '#include "record.hh"\n#include <type_traits>\n'
            + "\n".join(assertions)
            + "\nint main() {}\n"
        )
        result = subprocess.run(
            [
                str(LAYOUT_COMPILER),
                "-std=c++17",
                "-Wall",
                "-Wextra",
                "-Wpedantic",
                "-Werror",
                str(probe),
                "-o",
                str(executable),
            ],
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(
            [str(executable)], text=True, capture_output=True, timeout=30, check=False
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def inheritance_fixture(self, flags=()):
        self.header.write_text((HERE / "fixtures/inheritance.hh").read_text())
        return self.success(self.invoke(flags))

    def test_direct_bases_preserve_order_alias_access_and_source(self):
        document = self.inheritance_fixture(["--target=x86_64-unknown-linux-gnu"])
        nodes = self.declarations(document)
        derived = nodes["inheritance::Derived"]
        self.assertEqual(
            [b["declaration_id"] for b in derived["bases"]],
            [nodes["inheritance::Root"]["id"], nodes["inheritance::Other"]["id"]],
        )
        self.assertEqual([b["offset_bits"] for b in derived["bases"]], [0, 64])
        self.assertEqual([b["access"] for b in derived["bases"]], ["public", "public"])
        self.assertEqual(
            [b["written_access"] for b in derived["bases"]], ["none", "none"]
        )
        types = {t["id"]: t for t in document["types"]}
        self.assertEqual(types[derived["bases"][0]["type_id"]]["kind"], "alias")
        self.assertEqual(
            derived["field_ids"], [nodes["inheritance::Derived::tail"]["id"]]
        )
        private = nodes["inheritance::Private"]["bases"][0]
        protected = nodes["inheritance::Protected"]["bases"][0]
        self.assertEqual(
            (private["access"], private["written_access"]), ("private", "none")
        )
        self.assertEqual(
            (protected["access"], protected["written_access"]),
            ("protected", "protected"),
        )
        self.assertTrue(
            all(
                base["source"]["end"]["offset"] > base["source"]["spelling"]["offset"]
                for base in derived["bases"]
            )
        )

    def test_virtual_bases_use_complete_object_offsets_not_fixed_edges(self):
        nodes = self.declarations(
            self.inheritance_fixture(["--target=x86_64-unknown-linux-gnu"])
        )
        root_id = nodes["inheritance::Root"]["id"]
        for name in ("VLeft", "VRight"):
            edge = nodes[f"inheritance::{name}"]["bases"][0]
            self.assertTrue(edge["virtual"])
            self.assertIsNone(edge["offset_bits"])
        for name in ("VLeft", "VRight", "Diamond", "Bigger"):
            table = nodes[f"inheritance::{name}"]["virtual_base_offsets"]
            self.assertEqual(len(table), 1)
            self.assertEqual(table[0]["declaration_id"], root_id)
            self.assertIsNotNone(table[0]["offset_bits"])
        diamond = nodes["inheritance::Diamond"]
        bigger = nodes["inheritance::Bigger"]
        self.assertNotEqual(
            diamond["virtual_base_offsets"][0]["offset_bits"],
            bigger["virtual_base_offsets"][0]["offset_bits"],
        )
        self.assertLess(diamond["non_virtual_size_bits"], diamond["size_bits"])
        nested = nodes["inheritance::NestedVirtual"]
        self.assertEqual(
            {v["declaration_id"] for v in nested["virtual_base_offsets"]},
            {root_id, nodes["inheritance::VLeft"]["id"]},
        )

    def test_repeated_and_mixed_diamonds_preserve_distinct_paths(self):
        nodes = self.declarations(self.inheritance_fixture())
        repeated = nodes["inheritance::Repeated"]
        self.assertEqual(repeated["virtual_base_offsets"], [])
        self.assertEqual(len(repeated["bases"]), 2)
        self.assertNotEqual(
            repeated["bases"][0]["offset_bits"], repeated["bases"][1]["offset_bits"]
        )
        self.assertEqual(repeated["field_ids"], [])
        mixed = nodes["inheritance::Mixed"]
        self.assertEqual(len(mixed["bases"]), 2)
        self.assertEqual(len(mixed["virtual_base_offsets"]), 1)
        self.assertNotEqual(
            mixed["bases"][0]["offset_bits"],
            mixed["virtual_base_offsets"][0]["offset_bits"],
        )

    def test_empty_bases_packing_and_tail_padding_are_not_summed(self):
        nodes = self.declarations(
            self.inheritance_fixture(["--target=x86_64-unknown-linux-gnu"])
        )
        empty = nodes["inheritance::EmptyDerived"]
        self.assertEqual(empty["bases"][0]["offset_bits"], 0)
        self.assertEqual(nodes["inheritance::EmptyDerived::value"]["offset_bits"], 0)
        self.assertEqual(empty["size_bits"], 32)
        self.assertEqual(nodes["inheritance::PackedBase"]["size_bits"], 24)
        self.assertEqual(nodes["inheritance::PackedChild::third"]["offset_bits"], 24)
        self.assertLess(
            nodes["inheritance::TailDerived::third"]["offset_bits"],
            nodes["inheritance::TailBase"]["size_bits"],
        )

    def test_base_dependency_closure_selects_included_definitions_only(self):
        (self.root / "base.hh").write_text(
            "namespace N { struct Base { int value; }; struct Unused { void run(); }; }\n"
        )
        self.header.write_text(
            '#include "base.hh"\nstruct Derived : N::Base { char own; };\n'
        )
        nodes = self.declarations(self.success(self.invoke()))
        self.assertNotIn("N::Unused", nodes)
        self.assertEqual(
            nodes["Derived"]["bases"][0]["declaration_id"], nodes["N::Base"]["id"]
        )
        self.assertEqual(len(nodes["Derived"]["field_ids"]), 1)
        self.assertEqual(nodes["N::Base"]["semantic_parent_id"], nodes["N"]["id"])

    def test_forward_records_have_no_invented_base_layout(self):
        self.header.write_text("struct Forward;\n")
        node = self.declarations(self.success(self.invoke()))["Forward"]
        self.assertEqual(node["bases"], [])
        self.assertEqual(node["virtual_base_offsets"], [])
        for key in (
            "data_size_bits",
            "non_virtual_size_bits",
            "non_virtual_alignment_bits",
        ):
            self.assertIsNone(node[key])

    def test_base_macros_anonymous_alias_and_relocation(self):
        self.header.write_text(
            "typedef struct { int value; } Base;\n#define BASE public Base\n"
            "struct Derived : BASE { int own; };\n"
        )
        first_result = self.invoke()
        first = self.success(first_result)
        nodes = self.declarations(first)
        self.assertTrue(nodes["Derived"]["bases"][0]["source"]["macro_expansion"])
        self.assertEqual(first_result.stdout, self.invoke().stdout)
        with tempfile.TemporaryDirectory(prefix="icg-bases-relocated-") as relocated:
            shutil.copy2(self.header, Path(relocated) / self.header.name)
            second = self.success(
                self.invoke(cwd=relocated, options=["--source-root", relocated])
            )
            for key in ("declarations", "types"):
                self.assertEqual(first[key], second[key])

    def test_unsupported_base_members_and_dependent_bases_fail_closed(self):
        for source in (
            "struct Base { template<class T> void method(T); }; struct Derived : Base {};",
            "template<class T> struct Derived : T {}; struct Bad : Derived<int> {};",
            "template<class... T> struct Derived : T... {}; struct Bad : Derived<int, float> {};",
            "template<class T> struct Base { static int value; }; struct Derived : Base<int> {};",
            "struct Forward; struct Derived : Forward {};",
        ):
            with self.subTest(source=source):
                self.header.write_text(source)
                self.failure(self.invoke())

    def test_layout_compiler_preserves_driver_symlink_name(self):
        driver = self.root / "clang++"
        driver.symlink_to(EXTRACTOR)
        self.assertEqual(layout_compiler_path(driver), driver.absolute())
        self.assertNotEqual(layout_compiler_path(driver), driver.resolve())
        for invalid in (self.root / "missing", self.header, self.root):
            with (
                self.subTest(path=invalid),
                self.assertRaises(argparse.ArgumentTypeError),
            ):
                layout_compiler_path(invalid)

    def test_host_compiler_inheritance_layout_matches_real_objects(self):
        if LAYOUT_COMPILER is None:
            self.skipTest(
                "Pass --layout-compiler to compare native object layouts; CTest always supplies it"
            )
        document = self.inheritance_fixture()
        records = {
            n["id"]: n for n in document["declarations"] if n["kind"] == "record"
        }
        statements = [
            '#include "record.hh"',
            "#include <cstdio>",
            "#include <cstdint>",
            "#include <climits>",
            "int main() {",
        ]
        checks = 0
        for index, node in enumerate(records.values()):
            name, variable = node["qualified_name"], f"object{index}"
            statements.append(f"{name} {variable}{{}}; (void){variable};")
            expressions = [
                (f"sizeof({name}) * CHAR_BIT", node["size_bits"]),
                (f"alignof({name}) * CHAR_BIT", node["alignment_bits"]),
            ]
            virtual = {
                v["declaration_id"]: int(v["offset_bits"])
                for v in node["virtual_base_offsets"]
            }
            # Walk distinct legal cast paths on real objects. A virtual edge
            # resets to the most-derived table; never add a base's own vbase offset.
            stack = [(node, f"&{variable}", 0)]
            while stack:
                owner, expression, offset = stack.pop()
                for base in owner["bases"]:
                    if base["access"] != "public":
                        continue
                    target = records[base["declaration_id"]]
                    cast = f"static_cast<{target['qualified_name']}*>({expression})"
                    expected = (
                        virtual[target["id"]]
                        if base["virtual"]
                        else offset + int(base["offset_bits"])
                    )
                    distance = f"(reinterpret_cast<std::uintptr_t>({cast}) - reinterpret_cast<std::uintptr_t>(&{variable})) * CHAR_BIT"
                    expressions.append((distance, expected))
                    stack.append((target, cast, expected))
            for expression, expected in expressions:
                statements.append(
                    f'if (({expression}) != {expected}) {{ std::printf("layout check {checks}: {name} failed\\n"); return 1; }}'
                )
                checks += 1
        statements.append("return 0; }")
        probe = self.root / "layout.cpp"
        probe.write_text("\n".join(statements))
        executable = self.root / "layout-probe"
        warning_option = "-Wno-error=inaccessible-base"
        warning_check = subprocess.run(
            [
                str(LAYOUT_COMPILER),
                "-std=c++17",
                "-Werror",
                warning_option,
                "-x",
                "c++",
                "-fsyntax-only",
                "-",
            ],
            input="int probe;\n",
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if warning_check.returncode:
            self.assertIn("inaccessible-base", warning_check.stderr)
            # GCC 8 has no dedicated option; the fixture narrowly scopes its
            # legacy -Wextra exception to Mixed, not the whole translation unit.
            warning_option = "-DICG_LAYOUT_LEGACY_BASE_WARNING"
        result = subprocess.run(
            [
                str(LAYOUT_COMPILER),
                "-std=c++17",
                "-Wall",
                "-Wextra",
                "-Wpedantic",
                "-Werror",
                # Mixed intentionally has two Root subobjects. Individual cast
                # paths are legal; preserve its expected ambiguity warning.
                warning_option,
                str(probe),
                "-o",
                str(executable),
            ],
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        result = subprocess.run(
            [str(executable)], text=True, capture_output=True, timeout=30, check=False
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertGreater(checks, len(records) * 3)

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
        self.assertEqual(
            first["provenance"]["graph_digest"], second["provenance"]["graph_digest"]
        )
        self.assertNotEqual(
            first["provenance"]["input_digest"], second["provenance"]["input_digest"]
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
        self.assertEqual(
            first["provenance"]["graph_digest"], second["provenance"]["graph_digest"]
        )
        self.header.write_text(self.header.read_text() + "\n// changed\n")
        third = self.success(self.invoke())
        self.assertNotEqual(
            first["provenance"]["input_digest"], third["provenance"]["input_digest"]
        )
        self.assertNotEqual(
            first["provenance"]["graph_digest"], third["provenance"]["graph_digest"]
        )

    def test_environment_inputs_are_recorded(self):
        env = dict(os.environ, CPATH=str(self.root))
        document = self.success(self.invoke(env=env))
        self.assertEqual(document["provenance"]["environment"]["CPATH"], str(self.root))

    def template_fixture(self):
        self.header.write_text((HERE / "fixtures/templates.hh").read_text())
        return self.success(self.invoke())

    def test_class_template_fixture_preserves_arguments_defaults_and_packs(self):
        document = self.template_fixture()
        nodes = self.declarations(document)
        array = nodes["templates::Array<int, 3>"]
        primary = nodes["templates::Array"]
        self.assertEqual(array["primary_template_id"], primary["id"])
        self.assertEqual(array["template_arguments"][1]["value"], "3")
        self.assertEqual(primary["template_parameters"][1]["default_spelling"], "3")
        self.assertEqual(
            nodes["templates::Pack<>"]["template_arguments"],
            [{"kind": "pack", "elements": []}],
        )
        self.assertEqual(
            len(
                nodes["templates::Pack<int, const double *>"]["template_arguments"][0][
                    "elements"
                ]
            ),
            2,
        )
        self.assertEqual(
            [
                a["value"]
                for a in nodes["templates::Numbers<-2, 0, 7>"]["template_arguments"][0][
                    "elements"
                ]
            ],
            ["-2", "0", "7"],
        )
        self.assertEqual(
            nodes["templates::Null<nullptr>"]["template_arguments"][0]["kind"],
            "null_pointer",
        )
        by_id = {n["id"]: n for n in document["declarations"]}
        for pattern in (n for n in by_id.values() if n["kind"] == "class_template"):
            self.assertNotIn("size_bits", pattern)
            self.assertEqual(
                pattern["capabilities"][0]["reason_code"], "DEPENDENT_TEMPLATE_PATTERN"
            )
        for field in (n for n in by_id.values() if n["kind"] == "field"):
            parent = by_id[field["semantic_parent_id"]]
            self.assertTrue(
                field["qualified_name"].startswith(parent["qualified_name"] + "::")
            )

    def test_partial_specialization_retains_primary_and_deduced_arguments(self):
        document = self.template_fixture()
        nodes = self.declarations(document)
        partial = nodes["templates::Choice<int *>"]
        by_id = {n["id"]: n for n in document["declarations"]}
        types = {n["id"]: n for n in document["types"]}
        selected = by_id[partial["instantiation_pattern_id"]]
        self.assertEqual(selected["template_kind"], "partial_specialization")
        self.assertEqual(
            selected["primary_template_id"], partial["primary_template_id"]
        )
        self.assertEqual(
            types[partial["template_arguments"][0]["type_id"]]["kind"], "pointer"
        )
        self.assertEqual(
            types[partial["instantiation_arguments"][0]["type_id"]]["spelling"], "int"
        )
        explicit = nodes["templates::Choice<bool>"]
        self.assertEqual(explicit["specialization_kind"], "explicit_specialization")
        self.assertIsNone(explicit["instantiation_pattern_id"])
        self.assertIsNone(explicit["instantiation_arguments"])

    def test_explicit_instantiations_and_uninstantiated_pointer_are_distinct(self):
        nodes = self.declarations(self.template_fixture())
        for name, kind in (
            ("templates::Array<short, 2>", "explicit_instantiation_declaration"),
            ("templates::Array<long, 4>", "explicit_instantiation_definition"),
        ):
            self.assertEqual(nodes[name]["specialization_kind"], kind)
            self.assertIsNotNone(nodes[name]["point_of_instantiation"])
        opaque = nodes["templates::Opaque<int>"]
        self.assertEqual(opaque["specialization_kind"], "undeclared")
        self.assertFalse(opaque["complete"])
        self.assertIsNone(opaque["size_bits"])
        self.assertIsNone(opaque["instantiation_pattern_id"])

    def test_recursive_partial_packs_and_dependent_bases_instantiate_concretely(self):
        self.header.write_text(
            "template<class... T> struct Tuple {};\n"
            "template<class T, class... Rest> struct Tuple<T, Rest...> { T first; Tuple<Rest...> rest; };\n"
            "struct A { int a; }; struct B { double b; };\n"
            "template<class... Bases> struct Derived : virtual Bases... {};\n"
            "struct Model { Tuple<int, double> tuple; Derived<A, B> bases; };\n"
        )
        nodes = self.declarations(self.success(self.invoke()))
        self.assertIn("Tuple<int, double>::first", nodes)
        self.assertIn("Tuple<double>::first", nodes)
        self.assertTrue(nodes["Tuple<>"]["complete"])
        derived = nodes["Derived<A, B>"]
        self.assertEqual(len(derived["bases"]), 2)
        self.assertTrue(
            all(b["virtual"] and b["offset_bits"] is None for b in derived["bases"])
        )
        self.assertEqual(len(derived["virtual_base_offsets"]), 2)

    def test_template_parameter_defaults_redeclarations_and_template_template_packs(
        self,
    ):
        self.header.write_text(
            "template<class T> struct Box { T value; };\n"
            "template<class T=int, int N=2, template<class> class C=Box> struct Settings;\n"
            "template<class T, int N, template<class> class C> struct Settings { C<T> value; T array[N]; };\n"
            "template<template<class> class... C> struct Templates {};\n"
            "struct Model { Settings<> settings; Templates<Box, Box> templates; };\n"
        )
        nodes = self.declarations(self.success(self.invoke()))
        params = nodes["Settings"]["template_parameters"]
        self.assertEqual([p["kind"] for p in params], ["type", "non_type", "template"])
        self.assertEqual([p["default_spelling"] for p in params], ["int", "2", "Box"])
        self.assertTrue(
            all(p["default_source"]["spelling"]["line"] == 2 for p in params)
        )
        pack = next(
            n
            for n in nodes.values()
            if n.get("specialization_kind") and n["name"] == "Templates"
        )
        self.assertEqual(
            [a["kind"] for a in pack["template_arguments"][0]["elements"]],
            ["template", "template"],
        )

    def test_template_integrals_keep_signedness_enum_bool_and_full_width(self):
        self.header.write_text(
            "enum class Flag : unsigned char { High=255 };\n"
            "template<Flag F, bool B, unsigned long long N, long long S> struct Values {};\n"
            "struct Model { Values<Flag::High, true, 18446744073709551615ULL, (-9223372036854775807LL-1)> values; };\n"
        )
        document = self.success(self.invoke())
        record = next(
            n for n in document["declarations"] if n.get("specialization_kind")
        )
        args = record["template_arguments"]
        self.assertEqual(
            [a["value"] for a in args],
            ["255", "1", "18446744073709551615", "-9223372036854775808"],
        )
        self.assertEqual([a["signed"] for a in args], [False, False, False, True])

    def test_template_instantiated_anonymous_members_have_distinct_relocatable_ids(
        self,
    ):
        self.header.write_text(
            "#define INNER struct { T value; } inner;\n"
            "namespace { template<class T> struct Box { INNER T method(T) const; }; }\n"
            "struct Model { Box<int> first; Box<double> second; };\n"
        )
        first = self.success(self.invoke())
        records = [
            n
            for n in first["declarations"]
            if n["kind"] == "record" and n.get("anonymous")
        ]
        self.assertEqual(len(records), 2)
        self.assertNotEqual(records[0]["id"], records[1]["id"])
        self.assertNotEqual(records[0]["field_ids"], records[1]["field_ids"])
        self.assertEqual(self.invoke().stdout, self.invoke().stdout)
        with tempfile.TemporaryDirectory(
            prefix="icg-template-relocation-"
        ) as relocated:
            shutil.copy2(self.header, Path(relocated) / self.header.name)
            second = self.success(
                self.invoke(cwd=relocated, options=["--source-root", relocated])
            )
        self.assertEqual(
            first["provenance"]["graph_digest"], second["provenance"]["graph_digest"]
        )

    def test_template_aliases_canonicalize_arguments_without_duplicate_instances(self):
        self.header.write_text(
            "template<class T> struct Box { T value; }; using Int = int;\n"
            "struct Model { Box<Int> a; Box<int> b; Box<const int> c; };\n"
        )
        document = self.success(self.invoke())
        records = [n for n in document["declarations"] if n.get("specialization_kind")]
        self.assertEqual(len(records), 2)
        nodes = self.declarations(document)
        self.assertEqual(nodes["Model::a"]["type_id"], nodes["Model::b"]["type_id"])
        self.assertNotEqual(nodes["Model::a"]["type_id"], nodes["Model::c"]["type_id"])

    def test_nested_class_templates_and_instantiated_member_contexts(self):
        self.header.write_text(
            "struct Owner { template<class T> struct Box { T value; }; };\n"
            "template<class T> struct Outer { template<class U> struct Inner { T first; U second; }; };\n"
            "struct Model { Owner::Box<int> a; Outer<int>::Inner<double> b; };\n"
        )
        document = self.success(self.invoke())
        nodes = self.declarations(document)
        self.assertIn(
            nodes["Owner::Box"]["id"], nodes["Owner"]["nested_declaration_ids"]
        )
        self.assertIn("Outer<int>::Inner<double>::first", nodes)
        self.assertIn("Outer<int>::Inner<double>::second", nodes)

    def test_header_template_dependency_closure_and_explicit_instantiation(self):
        (self.root / "types.hh").write_text(
            "template<class T> struct Box { T value; }; template<class T> struct Unused { static int bad; };\n"
        )
        self.header.write_text(
            '#include "types.hh"\nextern template struct Box<int>;\n'
        )
        document = self.success(self.invoke())
        nodes = self.declarations(document)
        self.assertIn("Box<int>", nodes)
        self.assertNotIn("Unused", nodes)

    def test_unsupported_template_arguments_and_instantiated_members_fail_closed(self):
        for source in (
            "template<class T> using Alias = T; struct Model { Alias<int> value; };",
            "template<class T> struct Box { static int value; }; struct Model { Box<int> value; };",
            "template<class T> struct Box { template<class U> void method(U); }; struct Model { Box<int> value; };",
            "template<class T> struct Box {}; struct Model { Box<int(*)(int)> value; };",
            "template<class T> struct Box { void f(T value=T()); }; struct Model { Box<int> value; };",
        ):
            with self.subTest(source=source):
                self.header.write_text(source)
                self.failure(self.invoke())

    def test_template_patterns_classify_dependent_bodies_without_instantiating_them(
        self,
    ):
        self.header.write_text(
            "template<class T> struct Pattern { typename T::type value; template<class U> void method(U); };\n"
        )
        document = self.success(self.invoke())
        self.assertEqual(document["types"], [])
        self.assertEqual(len(document["declarations"]), 1)
        node = document["declarations"][0]
        self.assertEqual(node["kind"], "class_template")
        self.assertEqual(
            node["capabilities"],
            [
                {
                    "name": "template-pattern",
                    "status": "unknown",
                    "reason_code": "DEPENDENT_TEMPLATE_PATTERN",
                }
            ],
        )
        self.assertNotIn("field_ids", node)
        self.assertNotIn("size_bits", node)

    def test_template_explicit_specialization_redeclarations_and_special_members(self):
        self.header.write_text(
            "template<class T> struct Box { Box() = default; ~Box() = default; T value; };\n"
            "template<> struct Box<int>; template<> struct Box<int> { int explicit_value; };\n"
            "struct Model { Box<double> implicit; Box<int> explicit_value; };\n"
        )
        document = self.success(self.invoke())
        nodes = self.declarations(document)
        self.assertEqual(
            len([n for n in document["declarations"] if n.get("specialization_kind")]),
            2,
        )
        explicit = nodes["Box<int>"]
        self.assertEqual(explicit["specialization_kind"], "explicit_specialization")
        self.assertTrue(explicit["complete"])
        record = nodes["Box<double>"]
        methods = [
            n for n in document["declarations"] if n["id"] in record["callable_ids"]
        ]
        self.assertEqual(
            {m["callable_kind"] for m in methods}, {"constructor", "destructor"}
        )
        self.assertTrue(all(m["defaulted"] for m in methods))

    def test_template_dependent_out_of_line_member_context_fails_closed(self):
        self.header.write_text(
            "template<class T> struct Outer { template<class U> struct Inner; };\n"
            "template<class T> template<class U> struct Outer<T>::Inner<U*> { U* value; };\n"
        )
        report = self.failure(self.invoke())
        self.assertTrue(
            any(
                "Dependent record contexts" in d["message"]
                for d in report["diagnostics"]
            )
        )

    def test_template_auto_integral_and_nullptr_arguments_are_concrete(self):
        self.header.write_text(
            "template<auto Value> struct Constant {};\n"
            "struct Model { Constant<3> integer; Constant<nullptr> null_value; };\n"
        )
        document = self.success(self.invoke())
        arguments = [
            n["template_arguments"][0]
            for n in document["declarations"]
            if n.get("specialization_kind")
        ]
        self.assertEqual({a["kind"] for a in arguments}, {"integral", "null_pointer"})

    def test_template_pattern_preserves_comments_and_record_annotations(self):
        self.header.write_text(
            "/** pattern documentation */\n"
            'template<class T> struct [[clang::annotate("pattern-tag")]] Box { T value; };\n'
        )
        node = self.declarations(self.success(self.invoke()))["Box"]
        self.assertEqual(
            {a["syntax"] for a in node["annotations"]}, {"comment", "clang-annotate"}
        )
        self.assertTrue(any(a["payload"] == "pattern-tag" for a in node["annotations"]))
        self.assertEqual(len(node["annotations"]), 2)

    def test_native_template_layout_matches_instantiated_facts(self):
        if LAYOUT_COMPILER is None:
            self.skipTest("Pass --layout-compiler for native template layout probes")
        document = self.template_fixture()
        checks = ['#include "record.hh"', "#include <cstddef>"]
        nodes = {n["id"]: n for n in document["declarations"]}
        for node in nodes.values():
            if node["kind"] != "record" or not node["complete"]:
                continue
            name = node["qualified_name"]
            checks.append(
                f'static_assert(sizeof({name})*8 == {node["size_bits"]}, "size");'
            )
            checks.append(
                f'static_assert(alignof({name})*8 == {node["alignment_bits"]}, "alignment");'
            )
            if node["standard_layout"]:
                for identifier in node["field_ids"]:
                    field = nodes[identifier]
                    if not field["bitfield"]:
                        # Aliases avoid commas inside the offsetof macro's type argument.
                        alias = "Record" + str(len(checks))
                        checks.extend([
                            f"using {alias} = {name};",
                            f'static_assert(offsetof({alias}, {field["name"]})*8 == {field["offset_bits"]}, "offset");',
                        ])
        source = self.root / "template-layout.cpp"
        source.write_text("\n".join(checks) + "\n")
        result = subprocess.run(
            [
                str(LAYOUT_COMPILER),
                "-std=c++17",
                "-Wall",
                "-Wextra",
                "-Wpedantic",
                "-Werror",
                "-c",
                str(source),
                "-o",
                str(self.root / "template-layout.o"),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreater(len(checks), 30)

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
    parser.add_argument("--path-root", action="append", default=[])
    parser.add_argument("--layout-compiler", type=layout_compiler_path)
    parser.add_argument("--llvm-major", type=int, choices=range(17, 24))
    parser.add_argument("--lifecycle-sanitizers", action="store_true")
    parser.add_argument("--lifecycle-leak-check", action="store_true")
    args, remaining = parser.parse_known_args()
    EXTRACTOR = args.extractor.resolve(strict=True)
    PATH_ROOTS = args.path_root
    LAYOUT_COMPILER = args.layout_compiler
    LLVM_MAJOR = args.llvm_major
    LIFECYCLE_SANITIZERS = args.lifecycle_sanitizers or args.lifecycle_leak_check
    LIFECYCLE_LEAK_CHECK = args.lifecycle_leak_check
    unittest.main(argv=[sys.argv[0], *remaining])
