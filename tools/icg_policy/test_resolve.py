#!/usr/bin/env python3
"""Rule tests, actual extraction, native access checks, and digest-safe mutations."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.icg_policy import cases, characterize, resolve, rules  # noqa: E402

EXTRACTOR = None
COMPILER = None


class RuleTests(unittest.TestCase):
    def test_pinned_schema_is_valid(self):
        resolve.Draft202012Validator.check_schema(
            json.loads(resolve.SCHEMA.read_text())
        )

    def test_defaults_and_aliases(self):
        self.assertEqual(rules.annotation(None)["io"], 15)
        self.assertEqual(rules.annotation("/**< trick_units(r) */")["units"], "rad")
        self.assertEqual(rules.annotation("// *i (cm) distance")["io"], 10)
        self.assertEqual(
            rules.annotation("/* trick_io(io) */")["diagnostics"],
            ["LEGACY_INVALID_UNITS_DEFAULT"],
        )

    def test_all_permissions_and_unknown_value(self):
        for _, source, tables, _ in cases.cases():
            if "f0_0" not in source:
                continue
            for line in source.splitlines():
                if not line.startswith("int "):
                    continue
                name = line.split()[1].rstrip(";")
                result = rules.annotation(line[line.index("/*") :])
                self.assertEqual(
                    result["io"], tables["Model"].get(name, {"io": 0})["io"]
                )
        self.assertEqual(rules.annotation("/* trick_io( io ) */")["io"], 0)
        self.assertEqual(
            rules.annotation("/* trick_io(--) trick_units(1) */")["io"], 15
        )

    def test_unsupported_annotation_is_not_silently_repaired(self):
        for value in (
            "/* trick_units(r */",
            "/* trick_io() */",
            "/* trick_units(kg*m/s2) */",
            "/* trick_units(no_such_unit) */",
            "/* trick_units(1) company_io(i) */",
            "/* trick_io(i) trick_io(o) */",
            "/* trick_chkpnt_io(--) trick_units(1) */",
        ):
            with self.subTest(value=value), self.assertRaises(rules.PolicyError):
                rules.annotation(value)

    def test_schema_and_policy_are_versioned_independently(self):
        facts = json.loads(
            (
                ROOT
                / "trick_source/codegen/TrickCodeGen/ir/fixtures/minimal-record.json"
            ).read_text()
        )
        request = resolve.request_for(facts)
        request["policy_version"] = "scalar-metadata-0"
        with self.assertRaisesRegex(rules.PolicyError, "ICG_POLICY_REQUEST"):
            resolve.resolve(facts, request)


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        if EXTRACTOR is None:
            self.skipTest("use --extractor for actual frontend tests")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name).resolve()
        self.env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("TRICK_")
            and k not in ("CPATH", "CPLUS_INCLUDE_PATH", "C_INCLUDE_PATH")
        }

    def extract(self, source, overrides=None, options=()):
        header = self.work / "model.hh"
        header.write_text(source)
        env = dict(
            self.env,
            **{
                k: v.replace("$HEADER", str(header))
                for k, v in (overrides or {}).items()
            },
        )
        command = [
            str(EXTRACTOR),
            "--source-root",
            str(self.work),
            *options,
            str(header),
            "--",
        ]
        p = subprocess.run(
            command, env=env, capture_output=True, check=False, cwd=self.work
        )
        self.assertEqual(p.returncode, 0, p.stderr.decode())
        return json.loads(p.stdout)

    def model(self, source=cases.HEADER + "struct Model { int x; };\n", overrides=None):
        facts = self.extract(source, overrides)
        request = resolve.request_for(facts)
        model = resolve.resolve(facts, request)
        resolve.validate(facts, request, model)
        return facts, request, model

    def test_characterized_cases(self):
        for name, source, expected, env in cases.cases():
            with self.subTest(case=name):
                facts, _, model = self.model(source, env)
                self.assertEqual(characterize.observed(facts, model), expected)

    def test_characterized_legacy_repairs_are_explicit_policy_rejections(self):
        for name, source, _, env, code in cases.rejections():
            with self.subTest(case=name):
                facts = self.extract(source, env)
                with self.assertRaisesRegex(rules.PolicyError, code):
                    resolve.resolve(facts, resolve.request_for(facts))

    def test_determinism_and_no_ambient_policy(self):
        facts, request, model = self.model()
        previous = os.environ.get("TRICK_ICG_IGNORE_TYPES")
        os.environ["TRICK_ICG_IGNORE_TYPES"] = "Model"
        try:
            self.assertEqual(resolve.resolve(facts, request), model)
            self.assertEqual(resolve.digest(facts), model["facts"]["document_digest"])
        finally:
            if previous is None:
                del os.environ["TRICK_ICG_IGNORE_TYPES"]
            else:
                os.environ["TRICK_ICG_IGNORE_TYPES"] = previous

    def test_mutations_fail_before_digest_even_after_rehash(self):
        facts, request, model = self.model(
            cases.HEADER
            + "class Model { friend void init_attrModel(); int x; /* trick_units(r) */\n};\n"
        )
        field = next(
            i
            for i, d in enumerate(model["declarations"])
            if d["metadata"] and "annotation" in d["metadata"]
        )
        mutations = [
            lambda m: m["declarations"][field]["metadata"]["annotation"].update(io=0),
            lambda m: m["declarations"][field]["metadata"]["annotation"].update(
                units="cm"
            ),
            lambda m: m["declarations"][field].update(
                decision="omit", rule="NOT_REQUESTED"
            ),
            lambda m: m["declarations"][field]["metadata"]["access"].update(
                friend_indices=[]
            ),
            lambda m: m["declarations"][field]["metadata"]["access"].update(
                allowed=False
            ),
            lambda m: m["declarations"][field]["metadata"].update(comment_index=None),
            lambda m: m["files"][0].update(no_comment=True),
            lambda m: m["declarations"].pop(),
            lambda m: m["facts"].update(input_digest="0" * 64),
            lambda m: m["settings"]["environment"].update(
                TRICK_ICG_IGNORE_TYPES="Model"
            ),
        ]
        for mutation in mutations:
            changed = deepcopy(model)
            mutation(changed)
            changed["digest"] = resolve.model_digest(changed)
            with self.assertRaisesRegex(rules.PolicyError, "ICG_POLICY_CONSISTENCY"):
                resolve.validate(facts, request, changed)

    def test_facts_digest_is_not_a_substitute_for_validation(self):
        facts, request, _ = self.model()
        field = next(n for n in facts["declarations"] if n["kind"] == "field")
        field["semantic_parent_id"] = "decl:" + "0" * 64
        facts["provenance"]["graph_digest"] = resolve.ir.graph_digest(facts)
        with self.assertRaises(ValueError):
            resolve.resolve(facts, request)

    def test_requested_scope_cannot_widen(self):
        (self.work / "other.hh").write_text("struct Other { int y; };\n")
        facts = self.extract('#include "other.hh"\nstruct Model { int x; };\n')
        request = resolve.request_for(facts)
        other = next(
            f["id"] for f in facts["files"] if f["path"]["portable"] == "other.hh"
        )
        request["file_ids"] = sorted(request["file_ids"] + [other])
        with self.assertRaisesRegex(rules.PolicyError, "ICG_POLICY_REQUEST"):
            resolve.resolve(facts, request)

    def test_narrower_request_changes_identity_and_omits_unrelated_declarations(self):
        other = self.work / "other.hh"
        other.write_text("struct Other { int y; };\n")
        facts = self.extract(
            '#include "other.hh"\nstruct Model { int x; };\n',
            options=(
                "--select-file",
                str(other),
                "--select-file",
                str(self.work / "model.hh"),
            ),
        )
        broad = resolve.request_for(facts)
        a = resolve.resolve(facts, broad)
        narrow = deepcopy(broad)
        narrow["file_ids"] = [
            next(f["id"] for f in facts["files"] if f["path"]["portable"] == "model.hh")
        ]
        b = resolve.resolve(facts, narrow)
        self.assertNotEqual(a["input_digest"], b["input_digest"])
        self.assertEqual(set(characterize.observed(facts, b)), {"Model"})
        with self.assertRaisesRegex(rules.PolicyError, "ICG_POLICY_CONSISTENCY"):
            resolve.validate(facts, broad, b)

    def test_unsupported_required_type_fails_but_explicit_io_omission_is_allowed(self):
        for declaration in ("int *x;", "const int x = 1;", "int x[2];"):
            facts = self.extract(cases.HEADER + f"struct Model {{ {declaration} }};\n")
            with self.assertRaisesRegex(rules.PolicyError, "ICG_POLICY_TYPE"):
                resolve.resolve(facts, resolve.request_for(facts))
        facts, _, model = self.model(
            cases.HEADER + "struct Model { int *x; /* ** */\n};\n"
        )
        self.assertEqual(characterize.observed(facts, model), {"Model": {}})

    def test_templates_and_inheritance_reject_without_partial_output(self):
        for source in (
            "template<class T> struct Box { T x; }; struct Model { Box<int> x; };",
            "struct Base { int x; }; struct Model : Base { int y; };",
        ):
            facts = self.extract(source)
            with self.assertRaises(rules.PolicyError):
                resolve.resolve(facts, resolve.request_for(facts))

    def test_cli_failures_publish_nothing(self):
        facts = self.extract("struct Model { int *x; };\n")
        (self.work / "facts.json").write_text(json.dumps(facts))
        (self.work / "request.json").write_text(json.dumps(resolve.request_for(facts)))
        p = subprocess.run(
            [
                sys.executable,
                str(Path(resolve.__file__)),
                str(self.work / "facts.json"),
                "--request",
                str(self.work / "request.json"),
            ],
            capture_output=True,
        )
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(p.stdout, b"")
        self.assertIn(b"ICG_POLICY_TYPE", p.stderr)

    def test_environment_path_evidence_and_symlink_change(self):
        alias = self.work / "alias.hh"
        alias.symlink_to(self.work / "model.hh")
        facts, request, model = self.model(
            overrides={"TRICK_ICG_NOCOMMENT": str(alias)}
        )
        self.assertEqual(
            model["settings"]["paths"][0]["resolved"], str(self.work / "model.hh")
        )
        alias.unlink()
        with self.assertRaisesRegex(rules.PolicyError, "ICG_POLICY_CONSISTENCY"):
            resolve.validate(facts, request, model)

    def test_compilation_checks_operation_specific_friend_permission(self):
        if COMPILER is None:
            self.skipTest("use --compiler for native access checks")
        for declaration, allowed in (
            ("friend void init_attrModel();", True),
            ("friend void init_attrModel(int);", False),
            ("friend void init_attrModelExtra();", False),
            ("friend void init_attrModel() noexcept;", False),
            ("", False),
        ):
            with self.subTest(friend=declaration):
                facts, _, model = self.model(
                    cases.HEADER + f"class Model {{ {declaration} int x; }};\n"
                )
                decision = next(
                    n
                    for n in model["declarations"]
                    if n["metadata"] and "access" in n["metadata"]
                )
                self.assertEqual(decision["metadata"]["access"]["allowed"], allowed)
                self.assertEqual(decision["decision"], "include")
                unit = self.work / "probe.cpp"
                unit.write_text(
                    '#include "model.hh"\nvoid init_attrModel() { (void)sizeof(((Model*)nullptr)->x); }\n'
                )
                p = subprocess.run(
                    [str(COMPILER), "-std=c++17", "-fsyntax-only", str(unit)],
                    capture_output=True,
                )
                self.assertEqual(p.returncode == 0, allowed, p.stderr.decode())

    def test_unselected_unsupported_declarations_do_not_become_policy_exclusions(self):
        other = self.work / "other.hh"
        other.write_text("extern int ignored_global; struct Other { static int x; };\n")
        facts, _, model = self.model('#include "other.hh"\nstruct Model { int x; };\n')
        self.assertEqual(set(characterize.observed(facts, model)), {"Model"})
        # Broadening extraction requires unsupported facts, before policy runs.
        p = subprocess.run(
            [
                str(EXTRACTOR),
                "--source-root",
                str(self.work),
                "--select-file",
                str(other),
                str(self.work / "model.hh"),
                "--",
            ],
            env=self.env,
            capture_output=True,
        )
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(p.stdout, b"")
        self.assertIn(b"ICG_UNSUPPORTED_DECLARATION", p.stderr)
        other.write_text("struct Broken : MissingBase {};\n")
        p = subprocess.run(
            [
                str(EXTRACTOR),
                "--source-root",
                str(self.work),
                str(self.work / "model.hh"),
                "--",
            ],
            env=self.env,
            capture_output=True,
        )
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(p.stdout, b"")

    def test_invalid_request_shapes_fail_closed(self):
        facts, _, _ = self.model()
        for request in (None, [], {}, {"file_ids": []}):
            with self.assertRaisesRegex(rules.PolicyError, "ICG_POLICY_REQUEST"):
                resolve.resolve(facts, request)

    def test_real_header_exclusions_and_alias(self):
        header = ROOT / "test/SIM_test_ip/models/test_ip/include/EmbeddedClasses.hh"
        p = subprocess.run(
            [str(EXTRACTOR), "--source-root", str(ROOT), str(header), "--"],
            env=self.env,
            capture_output=True,
        )
        self.assertEqual(p.returncode, 0, p.stderr.decode())
        facts = json.loads(p.stdout)
        model = resolve.resolve(facts, resolve.request_for(facts))
        result = characterize.observed(facts, model)
        self.assertEqual(
            set(result),
            {
                "TopClass",
                "TopClass__PublicEmbed",
                "TopClass__PublicEmbed__PublicEmbed2",
                "TopClass__PublicEmbed__PublicEmbed2__PublicEmbed3",
            },
        )
        self.assertEqual(result["TopClass"]["d"], dict(units="rad", io=15))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--extractor", type=Path)
    parser.add_argument("--compiler", type=Path)
    args, rest = parser.parse_known_args()
    EXTRACTOR = args.extractor.resolve() if args.extractor else None
    COMPILER = args.compiler
    unittest.main(argv=[sys.argv[0], *rest])
