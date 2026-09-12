#!/usr/bin/env python3
"""Compile candidate, immutable legacy, and independent native metadata probes."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools/icg_baseline"))
import array_metadata  # noqa: E402
import differential  # noqa: E402
import enum_metadata  # noqa: E402
import integer_metadata  # noqa: E402
import lifecycle as lifecycle_baseline  # noqa: E402
import lifecycle_codegen  # noqa: E402
import memorymanager  # noqa: E402
import native  # noqa: E402
import scalar_metadata  # noqa: E402
import template_metadata  # noqa: E402
import template_structured  # noqa: E402

from tools.icg_emit import emit  # noqa: E402
from tools.icg_policy import cases, resolve, rules, template_characterize  # noqa: E402

EXTRACTOR = None
COMPILER = None
ARTIFACTS = None
LIFECYCLE_LEAK_CHECK = False


class EmitterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if EXTRACTOR is None or COMPILER is None:
            raise RuntimeError(
                "Emitter tests require --extractor and --compiler. "
                "Run python tools/icg_emit/test_emit.py --extractor "
                "build/icg-extract/trick-icg-extract --compiler /path/to/c++ "
                "or ctest --test-dir build/icg-extract -R icg_emit_integration "
                "--output-on-failure."
            )

    def setUp(self):
        if ARTIFACTS is None:
            self.temp = tempfile.TemporaryDirectory()
            self.addCleanup(self.temp.cleanup)
            self.work = Path(self.temp.name).resolve()
        else:
            ARTIFACTS.mkdir(parents=True, exist_ok=True)
            self.work = Path(
                tempfile.mkdtemp(prefix=self._testMethodName + "-", dir=ARTIFACTS)
            ).resolve()
        self.env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("TRICK_")
            and k not in ("CPATH", "CPLUS_INCLUDE_PATH", "C_INCLUDE_PATH")
        }

    def extract(self, header, *, outputs=None, template_fields=()):
        p = subprocess.run(
            [str(EXTRACTOR), "--source-root", str(header.parent), str(header), "--"],
            capture_output=True,
            env=self.env,
        )
        self.assertEqual(p.returncode, 0, p.stderr.decode())
        facts = json.loads(p.stdout)
        ids = sorted(
            n["id"]
            for n in facts["declarations"]
            if n["kind"] == "field" and n["qualified_name"] in template_fields
        )
        self.assertEqual(len(ids), len(template_fields))
        request = resolve.request_for(facts, outputs=outputs, template_field_ids=ids)
        return facts, request, resolve.resolve(facts, request)

    def model(
        self,
        source=cases.HEADER + "struct Model { int x; };\n",
        *,
        outputs=None,
        template_fields=(),
    ):
        header = self.work / "model.hh"
        header.write_text(source)
        return self.extract(header, outputs=outputs, template_fields=template_fields)

    def test_template_legacy_candidate_native_gate(self):
        report = template_metadata.capture(EXTRACTOR, self.work, COMPILER)
        self.assertEqual(
            (
                report["compared_tables"],
                report["compared_fields"],
                report["excluded_fields"],
            ),
            (4, 6, 6),
        )
        self.assertEqual(report["status"], "compared")

    def test_template_first_use_paths_and_repeated_requests(self):
        for name, (
            body,
            symbol,
            requested,
            path,
        ) in template_characterize.CASES.items():
            with self.subTest(case=name):
                facts, request, model = self.model(
                    template_characterize.PREFIX + body + "\n",
                    outputs=["template-attributes"],
                    template_fields=requested,
                )
                (instance,) = model["template_instances"]
                nodes = {n["id"]: n for n in facts["declarations"]}
                self.assertEqual(instance["symbol"], symbol)
                self.assertEqual(
                    instance["requested_field_ids"], request["template_field_ids"]
                )
                self.assertEqual(
                    [nodes[i]["qualified_name"] for i in instance["dependency_path"]],
                    path,
                )
                # Graph serialization order must never become legacy visitation order.
                changed = deepcopy(facts)
                changed["declarations"].reverse()
                changed["types"].reverse()
                changed["provenance"]["selection"]["roots"].reverse()
                self.assertEqual(
                    resolve.resolve(changed, request)["template_instances"],
                    model["template_instances"],
                )

    def test_template_unselected_consumer_file_is_rejected(self):
        definitions = self.work / "definitions.hh"
        definitions.write_text(
            cases.HEADER + "template<class T> struct Box { T value; };\n"
        )
        first = self.work / "first.hh"
        first.write_text(
            cases.HEADER
            + '#include "definitions.hh"\nstruct First { Box<int> first; };\n'
        )
        header = self.work / "model.hh"
        header.write_text(
            cases.HEADER + '#include "first.hh"\nstruct Model { Box<int> chosen; };\n'
        )
        process = subprocess.run(
            [
                str(EXTRACTOR),
                "--source-root",
                str(self.work),
                "--select-file",
                str(definitions),
                "--select-file",
                str(header),
                str(header),
                "--",
            ],
            capture_output=True,
            env=self.env,
            check=True,
        )
        facts = json.loads(process.stdout)
        chosen = next(
            n["id"]
            for n in facts["declarations"]
            if n["qualified_name"] == "Model::chosen"
        )
        request = resolve.request_for(
            facts, outputs=["template-attributes"], template_field_ids=[chosen]
        )
        with self.assertRaisesRegex(rules.PolicyError, "every captured user file"):
            resolve.resolve(facts, request)

    def test_template_cross_file_first_use_is_rejected(self):
        included = self.work / "included.hh"
        included.write_text(
            cases.HEADER
            + "template<class T> struct Box { T value; };\nstruct First { Box<int> first; };\n"
        )
        with self.assertRaisesRegex(rules.PolicyError, "ICG_POLICY_TEMPLATE"):
            self.model(
                cases.HEADER
                + '#include "included.hh"\nstruct Model { Box<int> chosen; };\n',
                outputs=["template-attributes"],
                template_fields=["Model::chosen"],
            )

    def test_template_arrays_annotations_and_explicit_selection(self):
        source = (
            "template<class A, class B> struct Pair {\n"
            "A a; /* trick_units(m) */\nB b; /* *o (rad) angles */\n};\n"
            "template<class T> struct Unsupported { T* p; };\n"
            "struct Model { Pair<unsigned int[2], double[2][3]> chosen; Unsupported<int> other; };"
        )
        facts, request, model = self.model(
            cases.HEADER + source,
            outputs=["template-attributes"],
            template_fields=["Model::chosen"],
        )
        self.assertEqual(len(model["template_instances"]), 1)
        instance = model["template_instances"][0]
        self.assertEqual(instance["cpp_type"], "Pair<unsigned int[2], double[2][3]>")
        symbol = instance["symbol"]
        self.compile(
            emit.render(facts, request, model),
            f"""
init_attr{symbol}_c_intf();
auto* rows = attr{symbol};
if (rows[0].type != TRICK_UNSIGNED_INTEGER || rows[0].index[0].size != 2 || std::string(rows[0].units) != "m") throw std::runtime_error("first member");
if (rows[1].num_index != 2 || rows[1].index[0].size != 2 || rows[1].index[1].size != 3 || rows[1].io != 5 || std::string(rows[1].units) != "rad") throw std::runtime_error("second member");
""",
        )
        with self.assertRaisesRegex(rules.PolicyError, "ICG_POLICY_TYPE"):
            resolve.resolve(facts, resolve.request_for(facts))
        for changed in (
            dict(request, template_field_ids=[]),
            dict(request, template_field_ids=request["template_field_ids"] * 2),
            dict(request, outputs=resolve.OUTPUTS),
            dict(request, template_field_ids=["decl:" + "0" * 64]),
        ):
            with self.assertRaises(rules.PolicyError):
                resolve.resolve(facts, changed)

    def test_template_structured_closure_and_compiled_layout(self):
        facts = json.loads(
            template_metadata.extract(EXTRACTOR, ROOT, self.work).read_text()
        )
        model, candidate = template_structured.generate(facts, self.work / "generated")
        instances = {i["cpp_type"]: i for i in model["template_instances"]}
        self.assertEqual(set(instances), set(template_structured.BINDINGS))
        parent = instances[template_structured.OUTER]
        children = [instances[name] for name in ("Foo<int>", "Foo<double[2]>")]
        self.assertEqual(
            parent["dependency_record_ids"], sorted(c["record_id"] for c in children)
        )
        self.assertTrue(all(c["requested_field_ids"] == [] for c in children))
        included = [d for d in parent["fields"] if d["decision"] == "include"]
        for field, child in zip(included, children, strict=True):
            self.assertEqual(
                field["metadata"]["storage"]["record_id"], child["record_id"]
            )
            self.assertEqual(field["metadata"]["storage"]["type_name"], child["symbol"])
        # Compile complete legacy and candidate sources on every compiler lane.
        # The configured gate links both to the real MemoryManager and runs them.
        for name, source in (
            ("legacy", template_structured.reference()),
            ("candidate", candidate),
        ):
            cpp = self.work / (name + ".cpp")
            cpp.write_text(source)
            process = subprocess.run(
                [
                    str(COMPILER),
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-I" + str(ROOT / "include"),
                    "-c",
                    str(cpp),
                    "-o",
                    str(cpp.with_suffix(".o")),
                ],
                capture_output=True,
                env=self.env,
            )
            self.assertEqual(process.returncode, 0, process.stderr.decode())
        request = model["request"]
        for mutate in (
            lambda m: m["template_instances"].pop(0),
            lambda m: m["template_instances"][-1].update(dependency_record_ids=[]),
            lambda m: m["template_instances"][-1]["fields"][0]["metadata"][
                "storage"
            ].update(type_name="wrong_child"),
            lambda m: m["template_instances"][-1]["fields"][0]["metadata"][
                "storage"
            ].update(record_id=parent["record_id"]),
        ):
            changed = deepcopy(model)
            mutate(changed)
            changed["digest"] = resolve.model_digest(changed)
            with self.assertRaisesRegex(rules.PolicyError, "ICG_POLICY_CONSISTENCY"):
                emit.write(facts, request, changed, self.work / "forbidden.cpp")
        self.assertFalse((self.work / "forbidden.cpp").exists())

    def test_template_policy_mutations_require_exact_replay(self):
        facts = json.loads(
            template_metadata.extract(EXTRACTOR, ROOT, self.work).read_text()
        )
        request = template_metadata.request_for(facts)
        model = resolve.resolve(facts, request)
        for mutate in (
            lambda i: i.update(symbol="invented"),
            lambda i: i.update(field_id=request["template_field_ids"][0]),
            lambda i: i.update(cpp_type="TTT1<double, int>"),
            lambda i: i.update(dependency_path=[request["template_field_ids"][0]]),
            lambda i: i.update(requested_field_ids=["decl:" + "0" * 64]),
            lambda i: i["argument_type_ids"].reverse(),
            lambda i: i["fields"][0]["metadata"].update(units_map_key="wrong"),
            lambda i: i["fields"][0]["metadata"]["storage"].update(dimensions=[7]),
        ):
            changed = deepcopy(model)
            # Mutate the array instance, whose request ID is not assumed to sort first.
            instance = changed["template_instances"][0]
            old = deepcopy(instance)
            mutate(instance)
            if instance == old:
                instance["field_id"] = "decl:" + "0" * 64
            changed["digest"] = resolve.model_digest(changed)
            with self.assertRaisesRegex(rules.PolicyError, "ICG_POLICY_CONSISTENCY"):
                emit.write(facts, request, changed, self.work / "forbidden.cpp")
        self.assertFalse((self.work / "forbidden.cpp").exists())

    def test_template_unsupported_or_ambiguous_uses_publish_nothing(self):
        prefix = "template<class T> struct Box { T value; };\n"
        for source in (
            prefix + "struct Model { Box<int*> chosen; };",
            prefix + "struct Value { int x; }; struct Model { Box<Value> chosen; };",
            prefix
            + "template<class T> struct Huge { T values[536870912]; }; struct Model { Box<Huge<int>> chosen; };",
            prefix + "struct Model { const Box<int> chosen; };",
            prefix
            + "class Model { Box<int> chosen; public: int get() const { return chosen.value; } };",
            prefix + "struct Model { Box<int> chosen; /* ** */\n};",
            "template<class T=int> struct Box { T value; }; struct Model { Box<> chosen; };",
            "template<class T, int N> struct Box { T value[N]; }; struct Model { Box<int, 2> chosen; };",
            "template<class T> struct Box { T value; }; template<> struct Box<int> { int value; }; struct Model { Box<int> chosen; };",
            "namespace n { template<class T> struct Box { T value; }; } struct Model { n::Box<int> chosen; };",
            "/* PURPOSE: (excluded) ICG: (No) */\n"
            + prefix
            + "struct Model { Box<int> chosen; };",
        ):
            with self.subTest(source=source), self.assertRaises(rules.PolicyError):
                emit.write(
                    *self.model(
                        source
                        if source.startswith("/* PURPOSE:")
                        else cases.HEADER + source,
                        outputs=["template-attributes"],
                        template_fields=["Model::chosen"],
                    ),
                    self.work / "forbidden.cpp",
                )
        self.assertFalse((self.work / "forbidden.cpp").exists())

    def test_template_emitted_mutations_fail_independent_native_probe(self):
        facts = json.loads(
            template_metadata.extract(EXTRACTOR, ROOT, self.work).read_text()
        )
        _, candidate = template_metadata.generate(facts, self.work / "generated")
        report = dict(
            records=template_metadata.EXPECTED,
            enums={},
            record_bindings=template_metadata.BINDINGS,
        )
        symbol = template_metadata.BINDINGS["TTT1<int, double>"]["symbol"]
        for label, changed in (
            ("extent", candidate.replace("{{2, 0}", "{{7, 0}", 1)),
            ("offset", candidate.replace("  8, NULL", "  0, NULL", 1)),
            (
                "units",
                candidate.replace(
                    'map->add_param("TTT1<int, double>_aa", "1")',
                    'map->add_param("TTT1<int, double>_aa", "rad")',
                ),
            ),
            ("table", candidate.replace("attr" + symbol + "[]", "attrWrong[]")),
            (
                "linkage",
                candidate.replace("init_attr" + symbol + "_c_intf", "wrong_c_intf"),
            ),
        ):
            self.assertNotEqual(changed, candidate)
            with self.subTest(label=label), self.assertRaises(ValueError):
                native.capture(
                    facts,
                    changed,
                    report,
                    dict(id="template-members"),
                    self.work / label,
                    COMPILER,
                    source_name="candidate.cpp",
                )

    def test_template_overlay_dispatches_candidate_and_cannot_fall_back(self):
        facts = json.loads(
            template_metadata.extract(EXTRACTOR, ROOT, self.work).read_text()
        )
        _, candidate = template_metadata.generate(facts, self.work / "generated")
        symbol = template_metadata.BINDINGS["TTT1<int, double>"]["symbol"]
        # This containing-record reference stays outside the renamed legacy block.
        original = (
            template_metadata.reference()
            + f"\nATTRIBUTES* containing_record() {{ init_attr{symbol}(); return attr{symbol}; }}\n"
        )
        changed = candidate.replace("  8, NULL", "  0, NULL")
        replacement = template_metadata.overlay(
            original, changed, template_metadata.SYMBOLS
        )
        self.compile(
            replacement,
            'if (containing_record()[1].offset != 0) throw std::runtime_error("legacy fallback");',
        )
        # Corrupt the candidate after overlay validation to retain the independent
        # link-level proof that renamed legacy definitions cannot satisfy it.
        prefix, installed = replacement.split(template_metadata.MARKER, 1)
        missing = installed.replace("attr" + symbol + "[]", "attrWrong[]")
        with self.assertRaisesRegex(ValueError, "native link failed"):
            self.compile(
                prefix + template_metadata.MARKER + missing,
                "containing_record();",
                "missing",
            )
        with self.assertRaisesRegex(
            template_metadata.b.BaselineError, "already installed"
        ):
            template_metadata.overlay(replacement, candidate, template_metadata.SYMBOLS)

    def test_template_overlay_checks_candidate_tables_before_writing(self):
        facts_path = template_metadata.extract(EXTRACTOR, ROOT, self.work)
        facts = json.loads(facts_path.read_text())
        model, candidate = template_structured.generate(facts, self.work / "generated")
        symbol = template_structured.SYMBOL
        match = re.search(
            rf"^ATTRIBUTES attr{symbol}\[\].*?}};\n",
            candidate,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match)
        table = match[0]
        target = self.work / "sim/build/io_TemplateTest.cpp"
        target.parent.mkdir(parents=True)
        original = template_structured.reference()
        target.write_text(original)
        for label, changed in (
            ("empty", ""),
            ("renamed", candidate.replace("attr" + symbol + "[]", "attrWrong[]")),
            ("dropped", candidate.replace(table, "")),
            (
                "declaration-only",
                candidate.replace(table, f"ATTRIBUTES attr{symbol}[];"),
            ),
            ("repeated", candidate + "\n" + table),
        ):
            output = self.work / label
            with (
                self.subTest(label=label),
                self.assertRaisesRegex(
                    template_metadata.b.BaselineError,
                    "template candidate table definitions mismatch",
                ),
            ):
                template_metadata.install_candidate(
                    facts_path,
                    target.parents[1],
                    output,
                    generator=lambda _facts, _output: (model, changed),
                    symbols=template_structured.SYMBOLS,
                )
            self.assertEqual(target.read_text(), original)
            self.assertFalse((output / "overlay.cpp").exists())
            self.assertFalse((output / "overlay.json").exists())
        installed, replacement = template_metadata.install_candidate(
            facts_path,
            target.parents[1],
            self.work / "valid",
            generator=lambda _facts, _output: (model, candidate),
            symbols=template_structured.SYMBOLS,
        )
        self.assertEqual(installed, target)
        self.assertEqual(target.read_text(), replacement)
        self.assertTrue(replacement.endswith(candidate))

    def test_lifecycle_legacy_candidate_native_gate(self):
        report = lifecycle_codegen.capture(
            EXTRACTOR,
            COMPILER,
            self.work,
            sanitize=LIFECYCLE_LEAK_CHECK,
            leak_check=LIFECYCLE_LEAK_CHECK,
        )
        self.assertEqual(
            (report["records"], report["lookups"], report["executions"]), (6, 18, 12)
        )
        self.assertEqual(report["status"], "compared")

    def test_lifecycle_output_and_operation_access_are_explicit(self):
        source = (
            "namespace demo { inline namespace v1 { class Model {\n"
            "friend void init_attrdemo__v1__Model(); Model() {}\n"
            "public: ~Model() {} }; }}"
        )
        documents = self.model(source, outputs=["lifecycle"])
        candidate = emit.render(*documents)
        self.assertNotIn("void* io_src_allocate_", candidate)
        self.assertIn("void io_src_delete_demo__v1__Model", candidate)
        self.assertNotIn("ATTRIBUTES attr", candidate)
        self.compile(candidate, "io_src_delete_demo__v1__Model(nullptr);")
        (self.work / "model.hh").write_text(
            source.replace("Model() {}", "public: Model() {}")
        )
        with self.assertRaisesRegex(ValueError, "ICG lifecycle trait mismatch"):
            self.compile(candidate, "", "changed-access")

    def test_lifecycle_combines_with_metadata_only_when_requested(self):
        source = "struct Model { int x = 5; };"
        documents = self.model(source)
        self.assertNotIn("io_src_allocate_", emit.render(*documents))
        facts = documents[0]
        request = resolve.request_for(facts, outputs=[*resolve.OUTPUTS, "lifecycle"])
        model = resolve.resolve(facts, request)
        self.compile(
            emit.render(facts, request, model),
            """
init_attrModel_c_intf();
auto* values = static_cast<Model*>(io_src_allocate_Model(3));
if (!values || values[0].x != 5 || values[2].x != 5) throw std::runtime_error("initialization");
io_src_destruct_Model(values, 3);
std::free(values);
io_src_delete_Model(new Model);
if (io_src_allocate_Model(0) || io_src_allocate_Model(-1)) throw std::runtime_error("invalid count");
""",
        )

    def test_lifecycle_policy_mutations_cannot_be_rehashed_into_permission(self):
        documents = self.model(
            "class Model { friend void init_attrModel(); Model() {} public: ~Model() {} };",
            outputs=["lifecycle"],
        )
        facts, request, model = documents
        index = next(
            i for i, d in enumerate(model["declarations"]) if d["decision"] == "include"
        )
        for change in (
            lambda r: r["allocate"].update(action="construct"),
            lambda r: r["default_constructor"].update(available=True),
            lambda r: r["destructor"].update(declaration_ids=[]),
            lambda r: r["destruct"].update(action="noop"),
            lambda r: r["delete"].update(symbol="io_src_delete_Other"),
        ):
            changed = deepcopy(model)
            change(changed["declarations"][index]["metadata"]["lifecycle"])
            changed["digest"] = resolve.model_digest(changed)
            with self.assertRaisesRegex(rules.PolicyError, "ICG_POLICY_CONSISTENCY"):
                emit.write(facts, request, changed, self.work / "forbidden.cpp")
        self.assertFalse((self.work / "forbidden.cpp").exists())

    def test_lifecycle_respects_selection_and_checks_io_omitted_storage(self):
        source = cases.HEADER + "struct Model { int* p; /* trick_io(**) */\n};"
        facts, _, _ = self.model(source)
        request = resolve.request_for(facts, outputs=[*resolve.OUTPUTS, "lifecycle"])
        with self.assertRaisesRegex(rules.PolicyError, "ICG_POLICY_TYPE"):
            resolve.resolve(facts, request)
        documents = self.model(
            "/* PURPOSE: (excluded) ICG: (No) */\nstruct Model {};",
            outputs=["lifecycle"],
        )
        with self.assertRaisesRegex(rules.PolicyError, "ICG_EMIT_EMPTY"):
            emit.write(*documents, self.work / "excluded.cpp")
        self.assertFalse((self.work / "excluded.cpp").exists())

    def test_lifecycle_unsupported_profiles_publish_nothing(self):
        for source, code in (
            ("struct alignas(32) Model { int x; };", "ICG_POLICY_LIFECYCLE_STORAGE"),
            ("union Model { int x; };", "ICG_POLICY_LIFECYCLE_STORAGE"),
            ("struct Model { virtual void f() {} };", "ICG_POLICY_LIFECYCLE_DELETE"),
            (
                "struct Model { static void* operator new(unsigned long size); };",
                "ICG_POLICY_LIFECYCLE_ALLOCATION",
            ),
            ("struct Model { int* p; };", "ICG_POLICY_TYPE"),
        ):
            with (
                self.subTest(source=source),
                self.assertRaisesRegex(rules.PolicyError, code),
            ):
                emit.write(
                    *self.model(source, outputs=["lifecycle"]),
                    self.work / "forbidden.cpp",
                )
        self.assertFalse((self.work / "forbidden.cpp").exists())

    def test_lifecycle_generated_mutations_fail_native_comparison(self):
        facts, request, model = self.extract(
            lifecycle_baseline.HEADER, outputs=["lifecycle"]
        )
        candidate = emit.render(facts, request, model)
        for index, (before, after) in enumerate((
            ("void io_src_destruct_IcgLifecycleTracked(", "void missing_destruct("),
            ("for (int i = 0; i < num; ++i)", "for (int i = num - 1; i >= 0; --i)"),
            ("object->~T();", "(void)object;"),
            ('extern "C" {', 'extern "C++" {'),
        )):
            with self.subTest(mutation=before):
                self.assertIn(before, candidate)
                output = self.work / f"mutation-{index}"
                output.mkdir()
                (output / "lifecycle.json").write_text('{"stale":true}')
                with self.assertRaises(ValueError):
                    lifecycle_baseline.check(
                        facts,
                        candidate.replace(before, after),
                        output,
                        COMPILER,
                        source_name="candidate.cpp",
                    )
                self.assertFalse((output / "lifecycle.json").exists())

    def test_lifecycle_overlay_cannot_fall_back_to_legacy_exports(self):
        facts, request, model = self.extract(
            lifecycle_baseline.HEADER, outputs=["lifecycle"]
        )
        candidate = emit.render(facts, request, model)
        legacy = lifecycle_baseline.reference()
        symbols = {
            f"io_src_{operation}_{name}"
            for name, rule in lifecycle_baseline.policies(facts).items()
            for operation in ("allocate", "destruct", "delete")
            if rule[operation] != "absent"
        }
        overlay = memorymanager.lifecycle_overlay(legacy, candidate, symbols)
        lifecycle_baseline.check(
            facts, overlay, self.work / "overlay", COMPILER, source_name="candidate.cpp"
        )
        missing = candidate.replace(
            "io_src_allocate_IcgLifecycleTracked", "missing_allocate"
        )
        with self.assertRaisesRegex(ValueError, "missing owning-allocation wrappers"):
            lifecycle_baseline.check(
                facts,
                memorymanager.lifecycle_overlay(legacy, missing, symbols),
                self.work / "missing",
                COMPILER,
                source_name="candidate.cpp",
            )

    def test_lifecycle_candidate_scalar_delete_releases_storage(self):
        if not LIFECYCLE_LEAK_CHECK:
            self.skipTest("requires the Linux lifecycle leak-check lane")
        facts, request, model = self.extract(
            lifecycle_baseline.HEADER, outputs=["lifecycle"]
        )
        candidate = emit.render(facts, request, model)
        before = "delete static_cast<::IcgLifecycleTracked*>(address);"
        self.assertIn(before, candidate)
        with self.assertRaisesRegex(ValueError, "LeakSanitizer: detected memory leaks"):
            lifecycle_baseline.check(
                facts,
                candidate.replace(
                    before,
                    "static_cast<::IcgLifecycleTracked*>(address)->~IcgLifecycleTracked();",
                ),
                self.work / "leak",
                COMPILER,
                sanitize=True,
                leak_check=True,
                source_name="candidate.cpp",
            )
        self.assertFalse((self.work / "leak/lifecycle.json").exists())

    def legacy_case(self, case_id):
        corpus = json.loads((differential.REFERENCE.parent / "corpus.json").read_text())
        case = next(c for c in corpus["cases"] if c["id"] == case_id)
        facts, request, model = self.extract(ROOT / case["header"])
        snapshot = differential.REFERENCE / case_id / "cold.json"
        artifact = next(
            a
            for a in json.loads(snapshot.read_text())["artifacts"].values()
            if a["group"] == "legacy-metadata"
        )
        legacy = differential.b.artifact_text(snapshot, artifact)
        report = differential.compare(facts, legacy, case_id)
        return facts, request, model, legacy, report, case

    def compile(self, candidate, body, directory="probe", *, compile_flags=()):
        work = self.work / directory
        work.mkdir(parents=True, exist_ok=True)
        (work / "candidate.cpp").write_text(candidate)
        (work / "probe.cpp").write_text(
            '#include "candidate.cpp"\n#include <iostream>\n#include <string>\n#include <stdexcept>\nint main() {\n'
            + body
            + '\nstd::cout << "{}";\n}\n'
        )
        return native.execute(
            [
                work / "probe.cpp",
                ROOT / "trick_source/sim_services/UnitsMap/UnitsMap.cpp",
            ],
            work,
            COMPILER,
            compile_flags=compile_flags,
        )

    def test_candidate_legacy_and_native_agree(self):
        for case_id in ("anonymous-enum", "deleted-constructor", "embedded"):
            with self.subTest(case=case_id):
                facts, request, model, legacy, report, case = self.legacy_case(case_id)
                candidate = emit.render(facts, request, model)
                self.assertEqual(
                    differential.compare(facts, candidate, case_id), report
                )
                old = native.capture(
                    facts,
                    legacy,
                    report,
                    case,
                    self.work / case_id / "legacy",
                    COMPILER,
                )
                new = native.capture(
                    facts,
                    candidate,
                    report,
                    case,
                    self.work / case_id / "candidate",
                    COMPILER,
                    source_name="candidate.cpp",
                )
                self.assertEqual(old["observations"], new["observations"])

    def test_mutated_candidate_output_fails_compiled_comparison(self):
        facts, request, model, _, report, case = self.legacy_case("embedded")
        candidate = emit.render(facts, request, model)
        for index, (before, after) in enumerate((
            ("8, NULL", "9, NULL"),
            ("{{5, 27}", "{{4, 28}"),
            ('"TopClass::one", 0, 0x40000000', '"TopClass::one", 1, 0x40000000'),
            ('"d", "double", "rad"', '"d", "double", "cm"'),
            ("15,TRICK_DOUBLE", "10,TRICK_DOUBLE"),
            ('"d", "double"', '"lost", "double"'),
            ("Language_CPP, 0,\n  8", "Language_CPP, 4,\n  8"),
            ("size_t io_src_sizeof_TopClass()", "size_t missing_size()"),
            ("void init_attrTopClass_c_intf()", "void missing_init()"),
            (re.search(r'\{"d",.*?NULL\},\n', candidate, re.S)[0], ""),
            ("15,TRICK_VOID", "10,TRICK_VOID"),
        )):
            with self.subTest(mutation=before):
                self.assertIn(before, candidate)
                directory = self.work / f"mutation-{index}"
                directory.mkdir(exist_ok=True)
                (directory / "native.json").write_text('{"stale": true}')
                with self.assertRaises(ValueError):
                    native.capture(
                        facts,
                        candidate.replace(before, after),
                        report,
                        case,
                        directory,
                        COMPILER,
                        source_name="candidate.cpp",
                    )
                self.assertFalse((directory / "native.json").exists())

    def test_cpp_linkage_cannot_satisfy_c_interface(self):
        facts, request, model, _, report, case = self.legacy_case("embedded")
        candidate = emit.render(facts, request, model).replace(
            "void init_attrTopClass_c_intf()",
            'extern "C++" void init_attrTopClass_c_intf()',
        )
        with self.assertRaisesRegex(ValueError, "native link failed"):
            native.capture(
                facts,
                candidate,
                report,
                case,
                self.work / "cpp-linkage",
                COMPILER,
                source_name="candidate.cpp",
            )

    def test_scoped_enum_legacy_candidate_native_gate_and_rejection(self):
        # This also exercises extraction command/evidence retention and the
        # separate native observation of legacy's unsigned-narrow mismatch.
        result = enum_metadata.capture(EXTRACTOR, self.work, COMPILER)
        self.assertEqual(result["scoped-enums"]["status"], "compared")
        self.assertEqual(result["unsigned-narrow"]["status"], "rejected")
        self.assertFalse((self.work / "unsigned-narrow/candidate.cpp").exists())

    def test_enum_mutations_fail_native_comparison(self):
        case, legacy = enum_metadata.reference("scoped-enums")
        facts, request, model = self.extract(ROOT / case["header"])
        report = enum_metadata.report_for(facts, legacy)
        candidate = emit.render(facts, request, model)
        for index, (before, after) in enumerate((
            (
                '{"icg_enum::last", 127, 0x40000000}',
                '{"icg_enum::Byte::last", 127, 0x40000000}',
            ),
            ('{"icg_enum::last", 127, 0x40000000}', '{"icg_enum::last", 127, 0x0}'),
            (
                '{"icg_enum::last", 127, 0x40000000}',
                '{"icg_enum::last", 126, 0x40000000}',
            ),
            (
                '{"icg_enum::zero", 0, 0x0},\n{"icg_enum::alias", 0, 0x0}',
                '{"icg_enum::alias", 0, 0x0},\n{"icg_enum::zero", 0, 0x0}',
            ),
            ('{"icg_enum::alias", 0, 0x0},\n', ""),
            (
                'enumicg_enum__Empty[] = {\n{"", 0, 0x0}',
                'enumicg_enum__Empty[] = {\n{"", 1, 0x0}',
            ),
            ("ENUM_ATTR enumicg_enum__Byte[]", "ENUM_ATTR missing_enum[]"),
            ("size_t io_src_sizeof_icg_enum__Byte()", "size_t missing_enum_size()"),
        )):
            with self.subTest(mutation=before):
                self.assertIn(before, candidate)
                directory = self.work / f"enum-mutation-{index}"
                directory.mkdir()
                (directory / "native.json").write_text('{"stale":true}')
                with self.assertRaises(ValueError):
                    native.capture(
                        facts,
                        candidate.replace(before, after),
                        report,
                        case,
                        directory,
                        COMPILER,
                        source_name="candidate.cpp",
                    )
                self.assertFalse((directory / "native.json").exists())

    def test_enum_only_and_empty_enum_compile(self):
        candidate = emit.render(
            *self.model(
                "enum class E { negative = -1, alias = -1 }; enum class Empty {};"
            )
        )
        self.compile(
            candidate,
            """
static_assert(sizeof(enumE) / sizeof(enumE[0]) == 3, "aliases retained");
static_assert(sizeof(enumEmpty) / sizeof(enumEmpty[0]) == 1, "empty sentinel");
if (enumE[0].value != -1 || std::string(enumE[1].label) != "alias" ||
    std::string(enumEmpty[0].label) != "" || enumEmpty[0].value != 0 ||
    io_src_sizeof_Empty() != sizeof(Empty)) throw std::runtime_error("enum only");
""",
        )

    def test_compiled_policy_metadata(self):
        names = {
            "all-io",
            "aliases",
            "dash-units",
            "checkpoint-only-dash",
            "description",
            "line-description",
            "description-no-space",
        }
        for name, source, expected, _ in cases.cases():
            if name not in names:
                continue
            with self.subTest(case=name):
                candidate = emit.render(*self.model(source))
                rows = expected["Model"]
                checks = [
                    f'static_assert(sizeof(attrModel) / sizeof(attrModel[0]) == {len(rows) + 1}, "field count");',
                    "init_attrModel_c_intf();",
                ]
                for i, (member, row) in enumerate(rows.items()):
                    for key, value in {
                        "name": member,
                        "units": row["units"],
                        "des": row["description"],
                    }.items():
                        checks.append(
                            f'if (std::string(attrModel[{i}].{key}) != {json.dumps(value)}) throw std::runtime_error("{key}");'
                        )
                    for key in ("io", "mods"):
                        checks.append(
                            f'if (attrModel[{i}].{key} != {row[key]}) throw std::runtime_error("{key}");'
                        )
                    checks.append(
                        f'if (Trick::UnitsMap::units_map()->get_units("Model_{member}") != {json.dumps(row["units"])}) throw std::runtime_error("units map");'
                    )
                self.compile(candidate, "\n".join(checks), name)

    def test_array_legacy_candidate_native_gate(self):
        result = array_metadata.capture(EXTRACTOR, self.work, COMPILER)
        self.assertEqual(result["status"], "compared")
        self.assertEqual(sum(len(v) for v in result["records"].values()), 9)

    def test_integer_legacy_candidate_native_gate(self):
        result = integer_metadata.capture(EXTRACTOR, self.work, COMPILER)
        self.assertEqual(result["status"], "compared")
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual(sum(len(v) for v in result["records"].values()), 22)

    def test_integer_mutations_fail_compiled_comparison(self):
        case, _ = array_metadata.reference(integer_metadata.HERE)
        documents = self.extract(ROOT / case["header"])
        facts = documents[0]
        report = array_metadata.report_for(facts, integer_metadata.EXPECTED)
        candidate = emit.render(*documents)
        for index, (before, after) in enumerate((
            ("TRICK_CHARACTER,", "TRICK_UNSIGNED_CHARACTER,"),
            ("TRICK_UNSIGNED_CHARACTER,", "TRICK_CHARACTER,"),
            ("TRICK_SHORT,", "TRICK_UNSIGNED_SHORT,"),
            ("TRICK_UNSIGNED_SHORT,", "TRICK_SHORT,"),
            ("TRICK_UNSIGNED_LONG,", "TRICK_LONG,"),
            ("TRICK_LONG_LONG,", "TRICK_UNSIGNED_LONG_LONG,"),
            ("TRICK_UNSIGNED_LONG_LONG,", "TRICK_LONG_LONG,"),
            (
                "TRICK_UNSIGNED_LONG_LONG, sizeof(unsigned long long)",
                "TRICK_UNSIGNED_LONG_LONG, sizeof(unsigned int)",
            ),
            ("38, NULL, 2, {{2, 0}, {3, 0}", "38, NULL, 2, {{3, 0}, {2, 0}"),
            ('"signed_code", "signed char"', '"signed_code", "char"'),
        )):
            with self.subTest(mutation=before):
                self.assertIn(before, candidate)
                work = self.work / f"mutation-{index}"
                with self.assertRaisesRegex(
                    ValueError,
                    "compiled ATTRIBUTES differs|native field size/offset/width differs",
                ):
                    native.capture(
                        facts,
                        candidate.replace(before, after, 1),
                        report,
                        case,
                        work,
                        COMPILER,
                        source_name="candidate.cpp",
                    )
                self.assertFalse((work / "native.json").exists())

    def test_integer_template_tables_preserve_width_and_signedness(self):
        types = (
            "signed char",
            "unsigned char",
            "short",
            "unsigned short",
            "unsigned long",
            "long long",
            "unsigned long long",
        )
        kinds = (
            "TRICK_CHARACTER",
            "TRICK_UNSIGNED_CHARACTER",
            "TRICK_SHORT",
            "TRICK_UNSIGNED_SHORT",
            "TRICK_UNSIGNED_LONG",
            "TRICK_LONG_LONG",
            "TRICK_UNSIGNED_LONG_LONG",
        )
        source = (
            "template<class T> struct Box { T value; T values[2]; }; struct Model {"
        )
        source += (
            "".join(f"Box<{kind}> field{index};" for index, kind in enumerate(types))
            + "};"
        )
        candidate = emit.render(
            *self.model(
                source,
                outputs=["template-attributes"],
                template_fields=[f"Model::field{index}" for index in range(7)],
            )
        )
        checks = []
        for index, (kind, code) in enumerate(zip(types, kinds, strict=True)):
            symbol = f"Model_field{index}_Box_{kind.replace(' ', '_')}_"
            checks.append(f"init_attr{symbol}_c_intf();")
            for row in (0, 1):
                checks.append(
                    f'if (attr{symbol}[{row}].type != {code} || attr{symbol}[{row}].size != sizeof({kind}) || std::string(attr{symbol}[{row}].type_name) != "{kind}") throw std::runtime_error("template integer metadata");'
                )
            checks.append(
                f'if (attr{symbol}[1].num_index != 1 || attr{symbol}[1].index[0].size != 2) throw std::runtime_error("template integer shape");'
            )
        self.compile(candidate, "\n".join(checks))

    def test_integer_lifecycle_initialization_preserves_limits(self):
        candidate = emit.render(
            *self.model(
                "struct Model { signed char sc = -128; unsigned char uc = 255; short s = -32768; unsigned short us = 65535; unsigned long ul = ~0UL; long long ll = (-9223372036854775807LL - 1); unsigned long long ull = ~0ULL; };",
                outputs=[*resolve.OUTPUTS, "lifecycle"],
            )
        )
        self.compile(
            candidate,
            """
    auto* values = static_cast<Model*>(io_src_allocate_Model(2));
    if (!values) throw std::runtime_error("allocation failed");
    for (int i = 0; i < 2; ++i) {
        const auto& v = values[i];
        if (v.sc != -128 || v.uc != 255 || v.s != -32768 || v.us != 65535 ||
            v.ul != ~0UL || v.ll != (-9223372036854775807LL - 1) || v.ull != ~0ULL)
            throw std::runtime_error("integer constructor values");
    }
    io_src_destruct_Model(values, 2);
    free(values);
    """,
        )

    def test_plain_char_abi_guard_does_not_conflate_explicit_signedness(self):
        candidate = emit.render(*self.model("struct Model { char codes[2]; };"))
        with self.assertRaisesRegex(ValueError, "ICG plain-char signedness mismatch"):
            self.compile(candidate, "", compile_flags=("-funsigned-char",))
        candidate = emit.render(
            *self.model("struct Model { signed char sc; unsigned char uc; };")
        )
        self.compile(
            candidate,
            """
    if (attrModel[0].type != TRICK_CHARACTER || attrModel[1].type != TRICK_UNSIGNED_CHARACTER)
        throw std::runtime_error("explicit character signedness");
    """,
            directory="explicit",
            compile_flags=("-funsigned-char",),
        )

    def test_common_scalar_legacy_candidate_native_gate(self):
        result = scalar_metadata.capture(EXTRACTOR, self.work, COMPILER)
        self.assertEqual(result["status"], "compared")
        self.assertEqual(sum(len(v) for v in result["records"].values()), 13)

    def test_common_scalar_mutations_fail_compiled_comparison(self):
        case, _ = array_metadata.reference(scalar_metadata.HERE)
        documents = self.extract(ROOT / case["header"])
        facts = documents[0]
        report = array_metadata.report_for(facts, scalar_metadata.EXPECTED)
        candidate = emit.render(*documents)
        for index, (before, after) in enumerate((
            ("TRICK_BOOLEAN", "TRICK_CHARACTER"),
            ("TRICK_CHARACTER", "TRICK_BOOLEAN"),
            ("TRICK_FLOAT", "TRICK_INTEGER"),
            ("TRICK_LONG", "TRICK_DOUBLE"),
            ("TRICK_LONG, sizeof(long)", "TRICK_LONG, sizeof(int)"),
            ("16, NULL, 2, {{2, 0}, {3, 0}", "16, NULL, 2, {{3, 0}, {2, 0}"),
            (
                'map->add_param("ScalarModel_gain", "m")',
                'map->add_param("wrong_gain", "m")',
            ),
        )):
            with self.subTest(mutation=before):
                self.assertIn(before, candidate)
                work = self.work / f"mutation-{index}"
                with self.assertRaisesRegex(
                    ValueError,
                    "compiled ATTRIBUTES differs|native field size/offset/width differs",
                ):
                    native.capture(
                        facts,
                        candidate.replace(before, after, 1),
                        report,
                        case,
                        work,
                        COMPILER,
                        source_name="candidate.cpp",
                    )
                self.assertFalse((work / "native.json").exists())

    def test_common_scalars_in_template_tables(self):
        fields = ("flags", "samples", "codes", "counts")
        types = ("bool", "float", "char", "long")
        kinds = ("TRICK_BOOLEAN", "TRICK_FLOAT", "TRICK_CHARACTER", "TRICK_LONG")
        source = (
            "template<class T> struct Box { T value; T values[2]; }; struct Model {"
        )
        source += (
            "".join(f"Box<{kind}> {field};" for field, kind in zip(fields, types))
            + "};"
        )
        candidate = emit.render(
            *self.model(
                source,
                outputs=["template-attributes"],
                template_fields=["Model::" + field for field in fields],
            )
        )
        checks = []
        for field, kind, code in zip(fields, types, kinds, strict=True):
            symbol = f"Model_{field}_Box_{kind}_"
            checks.append(f"init_attr{symbol}_c_intf();")
            for index in (0, 1):
                checks.append(
                    f'if (attr{symbol}[{index}].type != {code} || attr{symbol}[{index}].size != sizeof({kind})) throw std::runtime_error("template scalar type/size");'
                )
            checks.append(
                f'if (attr{symbol}[1].index[0].size != 2) throw std::runtime_error("template array shape");'
            )
        self.compile(candidate, "\n".join(checks))

    def test_common_scalars_in_lifecycle_initialization(self):
        source = "struct Model { bool flag = true; float gain = 1.25F; char code = 'A'; long count = (1L << 40) + 9; };"
        candidate = emit.render(
            *self.model(source, outputs=[*resolve.OUTPUTS, "lifecycle"])
        )
        self.compile(
            candidate,
            """
auto* values = static_cast<Model*>(io_src_allocate_Model(2));
if (!values) throw std::runtime_error("allocation failed");
for (int i = 0; i < 2; ++i) {
    if (!values[i].flag || values[i].gain != 1.25F || values[i].code != 'A' ||
        values[i].count != (1L << 40) + 9) throw std::runtime_error("scalar constructor values");
}
io_src_destruct_Model(values, 2);
free(values);
""",
        )

    def test_array_mutations_fail_compiled_comparison(self):
        case, _ = array_metadata.reference()
        documents = self.extract(ROOT / case["header"])
        facts = documents[0]
        report = array_metadata.report_for(facts)
        candidate = emit.render(*documents)
        for index, (before, after) in enumerate((
            ("16, NULL, 2, {{2, 0}, {3, 0}", "16, NULL, 2, {{3, 0}, {2, 0}"),
            ("16, NULL, 2, {{2, 0}", "16, NULL, 1, {{2, 0}"),
            ("16, NULL, 2, {{2, 0}", "16, NULL, 2, {{0, 0}"),
            ("16, NULL, 2, {{2, 0}", "16, NULL, 2, {{2, 1}"),
            (
                "16, NULL, 2, {{2, 0}, {3, 0}, {0, 0}",
                "16, NULL, 2, {{2, 0}, {3, 0}, {9, 0}",
            ),
            ("16, NULL, 2", "24, NULL, 2"),
            ("TRICK_DOUBLE, sizeof(double)", "TRICK_DOUBLE, sizeof(double[2][3])"),
            ("96, NULL, 8", "96, NULL, 7"),
            (
                'map->add_param("Aliases_rows", "rad")',
                'map->add_param("icg_array__Aliases_rows", "rad")',
            ),
            ('"positions",\n  15', '"positions",\n  10'),
            (
                '"counts",\n  5,TRICK_UNSIGNED_INTEGER, sizeof(unsigned int), 0, 0, Language_CPP, 4',
                '"counts",\n  5,TRICK_UNSIGNED_INTEGER, sizeof(unsigned int), 0, 0, Language_CPP, 0',
            ),
        )):
            with self.subTest(mutation=before):
                self.assertIn(before, candidate)
                directory = self.work / f"array-mutation-{index}"
                directory.mkdir()
                (directory / "native.json").write_text('{"stale":true}')
                with self.assertRaises(ValueError):
                    native.capture(
                        facts,
                        candidate.replace(before, after),
                        report,
                        case,
                        directory,
                        COMPILER,
                        source_name="candidate.cpp",
                    )
                self.assertFalse((directory / "native.json").exists())

    def test_private_array_checks_require_exact_init_friend(self):
        # Reference x inside the fixture so Clang's unused-private-field warning
        # cannot mask access checks. GCC 8 ignores unused attributes on fields.
        for friend, allowed in (
            ("friend void init_attrdemo__Model();", True),
            ("friend void init_attrdemo__Model(int);", False),
            ("", False),
        ):
            source = (
                cases.HEADER
                + f"namespace demo {{ using Row = double[3]; class Model {{ {friend}\nRow x[2]; /* trick_units(cm) */\npublic: double value() const {{ return x[0][0]; }}\n}}; }}"
            )
            candidate = emit.render(*self.model(source))
            self.assertEqual("offsetof(" in candidate, allowed)
            self.compile(
                candidate,
                'init_attrdemo__Model_c_intf(); if (Trick::UnitsMap::units_map()->get_units("Model_x") != "cm") throw std::runtime_error("namespace units key");',
            )
            if allowed:
                (self.work / "model.hh").write_text(source.replace(friend, ""))
                with self.assertRaisesRegex(
                    ValueError, "is private within this context|is a private member of"
                ):
                    self.compile(
                        candidate, "init_attrdemo__Model_c_intf();", "no-array-friend"
                    )

    def test_generated_private_access_uses_exact_friend_and_namespace(self):
        # The fixture's accessor keeps x used even when generated code omits it.
        for opening, closing, symbol in (
            ("", "", "Model"),
            ("namespace demo { inline namespace v1 {", "}}", "demo__v1__Model"),
        ):
            for friend, allowed in (
                (f"friend void init_attr{symbol}();", True),
                (f"friend void init_attr{symbol}(int);", False),
                (f"friend void init_attr{symbol}Extra();", False),
                ("", False),
            ):
                with self.subTest(scope=opening, friend=friend):
                    source = (
                        cases.HEADER
                        + f"#define TRICK_ICG {friend}\n{opening}\nclass Model {{ TRICK_ICG int x; public: int value() const {{ return x; }} }};\n{closing}\n"
                    )
                    candidate = emit.render(*self.model(source))
                    self.assertEqual("offsetof(" in candidate, allowed)
                    self.compile(candidate, f"init_attr{symbol}_c_intf();")
                    # Remove only the friendship after rendering. The positive
                    # generated operation must actually require compiler access.
                    if allowed:
                        (self.work / "model.hh").write_text(source.replace(friend, ""))
                        with self.assertRaisesRegex(
                            ValueError,
                            "is private within this context|is a private member of",
                        ):
                            self.compile(
                                candidate, f"init_attr{symbol}_c_intf();", "no-friend"
                            )

    def test_deterministic_atomic_writer_preserves_identical_file(self):
        documents = self.model()
        output = self.work / "out" / "candidate.cpp"
        self.assertTrue(emit.write(*documents, output))
        os.utime(output, ns=(1_000_000_000, 1_000_000_000))
        stat = output.stat()
        self.assertFalse(emit.write(*documents, output))
        self.assertEqual(
            (output.stat().st_ino, output.stat().st_mtime_ns),
            (stat.st_ino, stat.st_mtime_ns),
        )
        self.assertEqual(output.read_text(), emit.render(*documents))
        self.assertEqual(list(output.parent.iterdir()), [output])

    def test_rehashed_policy_mutation_publishes_no_output(self):
        facts, request, model = self.model()
        field = next(
            d
            for d in model["declarations"]
            if d["metadata"] and "annotation" in d["metadata"]
        )
        field["metadata"]["annotation"]["io"] = 10
        model["digest"] = resolve.model_digest(model)
        output = self.work / "candidate.cpp"
        with self.assertRaisesRegex(rules.PolicyError, "ICG_POLICY_CONSISTENCY"):
            emit.write(facts, request, model, output)
        self.assertFalse(output.exists())
        output.write_text("previous successful output\n")
        with self.assertRaises(rules.PolicyError):
            emit.write(facts, request, model, output)
        self.assertEqual(output.read_text(), "previous successful output\n")

    def test_changed_source_is_rejected_before_writing(self):
        documents = self.model()
        (self.work / "model.hh").write_text("struct Model { double x; };\n")
        with self.assertRaisesRegex(rules.PolicyError, "ICG_EMIT_SOURCE"):
            emit.write(*documents, self.work / "candidate.cpp")
        self.assertFalse((self.work / "candidate.cpp").exists())

    def test_unsupported_requests_publish_no_source(self):
        for source, code in (
            (
                "struct Model { int x[1][1][1][1][1][1][1][1][1]; };",
                "ICG_POLICY_ARRAY_RANK",
            ),
            ("struct Model { int x[2147483648ULL]; };", "ICG_POLICY_ARRAY_EXTENT"),
            (
                "/* PURPOSE: (ignored) ICG: (No) */\nstruct Model { int x; };\n",
                "ICG_EMIT_EMPTY",
            ),
            (
                "enum E : unsigned long long { huge = 0xffffffffffffffffULL };",
                "ICG_POLICY_ENUM_VALUE",
            ),
            (
                "enum class E : unsigned char { value = 255 };",
                "ICG_POLICY_ENUM_SIGN_EXTENSION",
            ),
            (
                "class Model { friend void init_attrModel() noexcept; int x; };",
                "ICG_EMIT_INIT",
            ),
            ("class Model { friend int init_attrModel(); int x; };", "ICG_EMIT_INIT"),
            ("struct Model { virtual ~Model() = default; int x; };", "ICG_EMIT_RECORD"),
            (
                "struct __attribute__((packed)) Model { unsigned int x : 3; };",
                "ICG_EMIT_BITFIELD",
            ),
        ):
            with (
                self.subTest(source=source),
                self.assertRaisesRegex(rules.PolicyError, code),
            ):
                emit.write(*self.model(source), self.work / "candidate.cpp")
        self.assertFalse((self.work / "candidate.cpp").exists())

    def test_input_and_symlink_outputs_are_rejected(self):
        documents = self.model()
        output = self.work / "candidate.cpp"
        output.symlink_to(self.work / "model.hh")
        for path in (output, self.work / "model.hh"):
            with self.assertRaisesRegex(rules.PolicyError, "ICG_EMIT_OUTPUT"):
                emit.write(*documents, path)

    def test_cli_failure_has_empty_stdout_and_no_candidate(self):
        facts, request, model = self.model()
        request = deepcopy(request)
        request["policy_version"] = "scalar-metadata-1"
        for name, value in (
            ("facts", facts),
            ("request", request),
            ("resolved", model),
        ):
            (self.work / f"{name}.json").write_text(json.dumps(value))
        p = subprocess.run(
            [
                sys.executable,
                str(Path(emit.__file__)),
                str(self.work / "facts.json"),
                "--request",
                str(self.work / "request.json"),
                "--resolved",
                str(self.work / "resolved.json"),
                "--output",
                str(self.work / "candidate.cpp"),
            ],
            capture_output=True,
        )
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(p.stdout, b"")
        self.assertFalse((self.work / "candidate.cpp").exists())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--extractor", type=Path, required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--lifecycle-leak-check", action="store_true")
    parser.add_argument(
        "--artifacts",
        type=Path,
        help="retain source, commands and observations, including failures",
    )
    args, rest = parser.parse_known_args()
    EXTRACTOR = args.extractor.resolve()
    # Preserve the C++ driver name when clang++ is a symlink to clang.
    COMPILER = args.compiler.absolute()
    ARTIFACTS = args.artifacts.resolve() if args.artifacts else None
    LIFECYCLE_LEAK_CHECK = args.lifecycle_leak_check
    unittest.main(argv=[sys.argv[0], *rest])
