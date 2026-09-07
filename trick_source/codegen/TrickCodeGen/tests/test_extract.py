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
PATH_ROOTS: list[str] = []
LAYOUT_COMPILER: Path | None = None


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
        self.assertEqual(document["schema_version"], 6)
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
            "struct Sample { void method(); };",
            "template<class T> struct Sample { T value; };",
            "namespace ns { void function(); }",
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
            "struct Sample {\nfriend struct Friend;\nstatic int value;\nvoid run();\nSample();\n};\n"
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
            'namespace N [[clang::annotate("third")]] { using Third = int; }\n'
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

    def test_unimplemented_namespace_members_fail_closed(self):
        for source in (
            "namespace N { struct Good {}; void function(); }",
            "namespace N { struct Good {}; } using namespace N;",
            "namespace N { struct Good {}; } using N::Good;",
            'extern "C++" { struct Good {}; }',
        ):
            with self.subTest(source=source):
                self.header.write_text(source)
                self.failure(self.invoke(), "ICG_UNSUPPORTED_DECLARATION")

    def test_anonymous_command_line_macro_has_no_fabricated_source_identity(self):
        self.header.write_text("typedef ANON Point;\n")
        self.failure(
            self.invoke(["-DANON=struct { int value; }"]), "ICG_IDENTITY_SOURCE"
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
            "template<int N> struct Bits { unsigned value:N; };",
            "template<class T> struct Model { enum class E : T { A }; };",
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
            "struct Base { virtual void method(); }; struct Derived : Base {};",
            "template<class T> struct Derived : T {};",
            "template<class... T> struct Derived : T... {};",
            "template<class T> struct Base {}; struct Derived : Base<int> {};",
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
                "-Wno-error=inaccessible-base",
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
    parser.add_argument("--path-root", action="append", default=[])
    parser.add_argument("--layout-compiler", type=layout_compiler_path)
    args, remaining = parser.parse_known_args()
    EXTRACTOR = args.extractor.resolve(strict=True)
    PATH_ROOTS = args.path_root
    LAYOUT_COMPILER = args.layout_compiler
    unittest.main(argv=[sys.argv[0], *remaining])
