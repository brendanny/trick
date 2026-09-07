import copy
import json
import unittest
from pathlib import Path

import validate as ir
from jsonschema import ValidationError

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "trick_source/codegen/TrickCodeGen/ir/extracted-facts.schema.json"
FIXTURE = ROOT / "trick_source/codegen/TrickCodeGen/ir/fixtures/minimal-record.json"


class ValidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA.read_text())
        cls.fixture = json.loads(FIXTURE.read_text())

    def validate(self, schema, document):
        # Structural mutation tests are independent of fingerprint integrity.
        # Refresh only after shape validation; digest-specific tests use ir.validate.
        ir.Draft202012Validator(schema).validate(document)
        value = copy.deepcopy(document)
        value["provenance"]["graph_digest"] = ir.graph_digest(value)
        ir.validate(schema, value)

    def template_document(self, argument_kind="type", pack=False):
        document = copy.deepcopy(self.fixture)
        record, field = document["declarations"]
        pattern = {
            key: copy.deepcopy(record[key])
            for key in (
                "name",
                "qualified_name",
                "source",
                "access",
                "origin",
                "definition",
                "annotations",
                "record_tag",
            )
        }
        parameter = {
            "kind": "non_type" if argument_kind == "integral" else "type",
            "name": "T",
            "pack": pack,
            "depth": 0,
            "index": 0,
            "source": copy.deepcopy(record["source"]),
            "parameters": [],
            "type_spelling": "int" if argument_kind == "integral" else None,
            "type_dependent": False if argument_kind == "integral" else None,
            "default_spelling": None,
            "default_source": None,
        }
        pattern.update(
            id="decl:template",
            canonical_declaration_id="decl:template",
            kind="class_template",
            usr="c:@ST>1#T@Sample",
            identity_kind="usr",
            template_kind="primary",
            primary_template_id=None,
            pattern_spelling=None,
            template_parameters=[parameter],
            capabilities=[
                {
                    "name": "template-pattern",
                    "status": "unknown",
                    "reason_code": "DEPENDENT_TEMPLATE_PATTERN",
                }
            ],
        )
        argument = {"kind": argument_kind, "type_id": "type:int"}
        if argument_kind == "integral":
            argument.update(value="3", signed=True, bit_width=32)
        if pack:
            argument = {"kind": "pack", "elements": [argument]}
        record.update(
            identity_kind="source",
            specialization_kind="implicit_instantiation",
            primary_template_id=pattern["id"],
            template_arguments=[argument],
            instantiation_pattern_id=pattern["id"],
            instantiation_arguments=[copy.deepcopy(argument)],
            point_of_instantiation=copy.deepcopy(record["source"]),
        )
        field["identity_kind"] = "source"
        document["declarations"].append(pattern)
        return document

    def test_template_primary_instantiation_and_pack_are_valid(self):
        for kind in ("type", "integral"):
            for pack in (False, True):
                with self.subTest(kind=kind, pack=pack):
                    self.validate(self.schema, self.template_document(kind, pack))
        document = self.template_document(pack=True)
        for key in ("template_arguments", "instantiation_arguments"):
            document["declarations"][0][key][0]["elements"] = []
        self.validate(self.schema, document)

    def test_template_primary_and_selected_pattern_references_are_checked(self):
        for key in ("primary_template_id", "instantiation_pattern_id"):
            document = self.template_document()
            document["declarations"][0][key] = "decl:missing"
            with self.assertRaisesRegex(ValueError, "dangling reference"):
                self.validate(self.schema, document)
            document["declarations"][0][key] = "decl:sample.value"
            with self.assertRaisesRegex(
                ValueError, "primary class template|same primary"
            ):
                self.validate(self.schema, document)
        document = self.template_document()
        document["declarations"][2]["name"] = "Different"
        with self.assertRaisesRegex(ValueError, "share name and semantic context"):
            self.validate(self.schema, document)

    def test_template_partial_selection_checks_deduced_arguments_and_primary(self):
        document = self.template_document()
        partial = copy.deepcopy(document["declarations"][2])
        partial.update(
            id="decl:partial",
            canonical_declaration_id="decl:partial",
            template_kind="partial_specialization",
            primary_template_id="decl:template",
            pattern_spelling="Sample<T*>",
        )
        document["declarations"].append(partial)
        document["declarations"][0]["instantiation_pattern_id"] = partial["id"]
        self.validate(self.schema, document)
        partial["primary_template_id"] = "decl:partial"
        with self.assertRaisesRegex(ValueError, "same primary|invalid primary"):
            self.validate(self.schema, document)
        partial["primary_template_id"] = "decl:template"
        partial["template_parameters"][0].update(
            kind="non_type", type_spelling="int", type_dependent=False
        )
        with self.assertRaisesRegex(ValueError, "kind disagrees"):
            self.validate(self.schema, document)

    def test_template_argument_shape_reference_and_kind_are_checked(self):
        for change, message in (
            ({"type_id": "type:missing"}, "dangling reference"),
            ({"value": "1"}, "inapplicable fields"),
            ({"kind": "integral"}, "missing or inapplicable fields"),
            ({"kind": "null_pointer", "type_id": "type:sample"}, "requires pointer"),
        ):
            document = self.template_document()
            document["declarations"][0]["template_arguments"][0].update(change)
            with (
                self.subTest(change=change),
                self.assertRaisesRegex(ValueError, message),
            ):
                self.validate(self.schema, document)
        document = self.template_document("integral")
        document["declarations"][2]["template_parameters"][0].update(
            kind="type", type_spelling=None, type_dependent=None
        )
        with self.assertRaisesRegex(ValueError, "kind disagrees"):
            self.validate(self.schema, document)

    def test_template_arity_and_pack_boundaries_are_checked(self):
        for arguments, message in (
            ([], "argument count"),
            ([{"kind": "pack", "elements": []}], "pack boundary"),
        ):
            document = self.template_document()
            document["declarations"][0]["template_arguments"] = arguments
            with self.assertRaisesRegex(ValueError, message):
                self.validate(self.schema, document)
        document = self.template_document(pack=True)
        document["declarations"][0]["template_arguments"][0]["elements"] = [
            {"kind": "pack", "elements": []}
        ]
        with self.assertRaisesRegex(ValueError, "nested packs"):
            self.validate(self.schema, document)

    def test_template_integer_range_signedness_and_type_are_checked(self):
        for change, message in (
            ({"value": "2147483648"}, "recorded range"),
            ({"value": "-2147483649"}, "recorded range"),
            ({"signed": False}, "consistent integral type"),
            ({"type_id": "type:sample"}, "requires an integral type"),
        ):
            document = self.template_document("integral")
            document["declarations"][0]["template_arguments"][0].update(change)
            with (
                self.subTest(change=change),
                self.assertRaisesRegex(ValueError, message),
            ):
                self.validate(self.schema, document)
        for value in ("-0", "+1", "01", 3):
            document = self.template_document("integral")
            document["declarations"][0]["template_arguments"][0]["value"] = value
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.validate(self.schema, document)

    def test_template_primary_instantiation_arguments_must_agree(self):
        document = self.template_document("integral")
        document["declarations"][0]["instantiation_arguments"][0]["value"] = "4"
        with self.assertRaisesRegex(ValueError, "arguments must match"):
            self.validate(self.schema, document)

    def test_template_parameter_signature_evidence_is_checked(self):
        for change, message in (
            ({"index": 1}, "indices"),
            ({"parameters": [{}]}, None),
            ({"type_spelling": "int"}, "only non-type"),
            ({"default_spelling": "int"}, "must be paired"),
        ):
            document = self.template_document()
            document["declarations"][2]["template_parameters"][0].update(change)
            with self.subTest(change=change):
                if message:
                    with self.assertRaisesRegex(ValueError, message):
                        self.validate(self.schema, document)
                else:
                    with self.assertRaises(ValidationError):
                        self.validate(self.schema, document)
        document = self.template_document(pack=True)
        parameter = document["declarations"][2]["template_parameters"][0]
        parameter.update(
            default_spelling="int", default_source=copy.deepcopy(parameter["source"])
        )
        with self.assertRaisesRegex(ValueError, "pack cannot have a default"):
            self.validate(self.schema, document)
        document = self.template_document()
        parameter = document["declarations"][2]["template_parameters"][0]
        parameter["source"]["spelling"]["file_id"] = "file:missing"
        with self.assertRaisesRegex(ValueError, "dangling reference"):
            self.validate(self.schema, document)

    def test_template_template_targets_and_nested_parameter_depth_are_checked(self):
        document = self.template_document()
        record, _, pattern = document["declarations"]
        parameter = pattern["template_parameters"][0]
        nested = copy.deepcopy(parameter)
        nested["depth"] = 1
        parameter.update(kind="template", parameters=[nested])
        for key in ("template_arguments", "instantiation_arguments"):
            record[key] = [{"kind": "template", "declaration_id": pattern["id"]}]
        self.validate(self.schema, document)
        nested["depth"] = 0
        with self.assertRaisesRegex(ValueError, "depth is inconsistent"):
            self.validate(self.schema, document)
        nested["depth"] = 1
        record["template_arguments"][0]["declaration_id"] = record["id"]
        with self.assertRaisesRegex(ValueError, "target must be a primary"):
            self.validate(self.schema, document)

    def test_template_semantic_arguments_reject_noncanonical_aliases(self):
        document = self.template_document()
        types = {n["id"]: n for n in document["types"]}
        declarations = {n["id"]: n for n in document["declarations"]}
        types["type:alias"] = {
            "id": "type:alias",
            "canonical_id": "type:int",
            "kind": "alias",
        }
        declarations["decl:sample"]["template_arguments"][0]["type_id"] = "type:alias"
        with self.assertRaisesRegex(ValueError, "require canonical types"):
            ir.validate_templates(types, declarations)

    def test_template_pattern_cannot_claim_instantiated_layout_or_capabilities(self):
        for change, message in (
            ({"size_bits": 32}, "must not claim instantiated facts"),
            ({"capabilities": []}, "classify its dependent pattern"),
            ({"primary_template_id": "decl:template"}, "cannot claim a partial"),
        ):
            document = self.template_document()
            document["declarations"][2].update(change)
            with (
                self.subTest(change=change),
                self.assertRaisesRegex(ValueError, message),
            ):
                self.validate(self.schema, document)
        document = self.template_document()
        document["declarations"][0]["capabilities"].append(
            copy.deepcopy(document["declarations"][2]["capabilities"][0])
        )
        with self.assertRaisesRegex(ValueError, "requires a class template"):
            self.validate(self.schema, document)

    def test_template_specialization_state_and_identity_are_checked(self):
        for change, message in (
            ({"identity_kind": "usr"}, "source identity"),
            (
                {"instantiation_pattern_id": None},
                "selected pattern and deduced arguments",
            ),
            ({"specialization_kind": "explicit_specialization"}, "selected pattern"),
            (
                {
                    "specialization_kind": "undeclared",
                    "instantiation_pattern_id": None,
                    "instantiation_arguments": None,
                },
                "cannot claim a complete layout",
            ),
        ):
            document = self.template_document()
            document["declarations"][0].update(change)
            with (
                self.subTest(change=change),
                self.assertRaisesRegex(ValueError, message),
            ):
                self.validate(self.schema, document)
        document = self.template_document()
        document["declarations"][0].update(
            specialization_kind="explicit_specialization",
            instantiation_pattern_id=None,
            instantiation_arguments=None,
        )
        self.validate(self.schema, document)

    def test_minimal_record_is_valid(self):
        ir.validate(self.schema, self.fixture)

    def test_graph_digest_rejects_stale_facts_and_unknown_versions(self):
        for mutate in (
            lambda d: d["files"][0].update(digest="1" * 64),
            lambda d: d["types"][0].update(spelling="signed int"),
            lambda d: d["declarations"][0].update(qualified_name="Other"),
            lambda d: d["provenance"].update(graph_digest="0" * 64),
        ):
            document = copy.deepcopy(self.fixture)
            mutate(document)
            with self.assertRaisesRegex(ValueError, "graph_digest does not match"):
                ir.validate(self.schema, document)
        for key in ("identity_version", "graph_digest_version"):
            document = copy.deepcopy(self.fixture)
            document["provenance"][key] = 2
            with self.assertRaises(ValidationError):
                ir.validate(self.schema, document)
            del document["provenance"][key]
            with self.assertRaises(ValidationError):
                ir.validate(self.schema, document)

    def test_graph_digest_projection_retains_rooted_facts_not_machine_evidence(self):
        document = copy.deepcopy(self.fixture)
        document["files"][0]["path"].update(
            spelled="/other/fixture.hh", real="/other/fixture.hh"
        )
        document["provenance"].update(
            working_directory="/other",
            arguments=["clang++", "-DUNUSED=1"],
            path_roots={"source": "/other", "resource-dir": "/other/sdk"},
            environment={"CPATH": "/other"},
            frontend_version="other frontend",
            target_triple="aarch64-apple-darwin",
            input_digest="1" * 64,
        )
        document["diagnostics"] = [
            {
                "severity": "warning",
                "code": "TEST_WARNING",
                "message": "/other/path",
                "source": None,
            }
        ]
        for key in ("files", "types", "declarations"):
            document[key].reverse()
        # Equal graph hashes do not assert equal invocation/target provenance.
        ir.validate(self.schema, document)
        self.assertEqual(ir.graph_digest(document), ir.graph_digest(self.fixture))
        for key, value in (("root", "vendor"), ("portable", "other.hh")):
            changed = copy.deepcopy(document)
            changed["files"][0]["path"][key] = value
            self.assertNotEqual(ir.graph_digest(document), ir.graph_digest(changed))

    def test_bitfield_reason_requires_matching_facts_and_capability_name(self):
        for key, value in (("bitfield", False), ("kind", "record")):
            document = self.bitfield_document()
            field = document["declarations"][1]
            field[key] = value
            if key == "bitfield":
                field["bit_width"] = None
                with self.assertRaisesRegex(ValueError, "requires a bitfield"):
                    self.validate(self.schema, document)
            else:
                # Directly test the reason prerequisite independent of kind shape.
                with self.assertRaisesRegex(ValueError, "requires a bitfield"):
                    ir.validate_capabilities(field)
        document = self.bitfield_document()
        field = document["declarations"][1]
        field["capabilities"].append({
            "name": "other",
            "status": "unsupported",
            "reason_code": "BITFIELD_NOT_ADDRESSABLE",
        })
        with self.assertRaisesRegex(ValueError, "requires a bitfield"):
            self.validate(self.schema, document)

    def test_capability_names_are_unique_and_kind_specific(self):
        document = copy.deepcopy(self.fixture)
        record, field = document["declarations"]
        record["capabilities"] *= 2
        with self.assertRaisesRegex(ValueError, "duplicate capability"):
            self.validate(self.schema, document)
        record["capabilities"].pop()
        field["capabilities"] = copy.deepcopy(record["capabilities"])
        with self.assertRaisesRegex(ValueError, "requires a record"):
            self.validate(self.schema, document)
        field["capabilities"] = []
        record["capabilities"].append({
            "name": "field-address",
            "status": "unknown",
            "reason_code": "NOT_CHECKED",
        })
        with self.assertRaisesRegex(ValueError, "requires a field"):
            self.validate(self.schema, document)

    def test_record_layout_capability_matches_completeness_in_both_directions(self):
        for complete in (False, True):
            document = copy.deepcopy(self.fixture)
            record = document["declarations"][0]
            if not complete:
                document["declarations"].pop()
                record.update(complete=False, definition=False, field_ids=[])
                for key in (
                    "size_bits",
                    "alignment_bits",
                    "data_size_bits",
                    "non_virtual_size_bits",
                    "non_virtual_alignment_bits",
                ):
                    record[key] = None
                for slot in record["special_members"]:
                    slot.update(
                        state="unknown",
                        deleted=None,
                        trivial=None,
                        virtual=None,
                        noexcept=None,
                    )
                record["capabilities"][0].update(
                    status="unknown", reason_code="INCOMPLETE_TYPE"
                )
            self.validate(self.schema, document)
            for capabilities in (
                [],
                [
                    {
                        "name": "frontend-record-layout",
                        "status": "unsupported",
                        "reason_code": "NOT_CHECKED",
                    }
                ],
                [
                    {
                        "name": "frontend-record-layout",
                        "status": "unknown" if complete else "supported",
                        "reason_code": "INCOMPLETE_TYPE" if complete else "SUPPORTED",
                    }
                ],
            ):
                changed = copy.deepcopy(document)
                changed["declarations"][0]["capabilities"] = capabilities
                with self.assertRaisesRegex(ValueError, "disagrees with completeness"):
                    self.validate(self.schema, changed)

    def test_schema_rejects_unknown_fields_and_wrong_version(self):
        for mutation in (
            lambda value: value.update(schema_version=1),
            lambda value: value.update(schema_version=2),
            lambda value: value.update(schema_version=3),
            lambda value: value.update(schema_version=4),
            lambda value: value.update(schema_version=5),
            lambda value: value.update(schema_version=6),
            lambda value: value.update(schema_version=7),
            lambda value: value.update(schema_version=8),
            lambda value: value.update(schema_version=10),
            lambda value: value.update(clang_ast={}),
        ):
            document = copy.deepcopy(self.fixture)
            mutation(document)
            with self.assertRaises(ValidationError):
                self.validate(self.schema, document)

    def test_graph_rejects_duplicate_and_dangling_ids(self):
        duplicate = copy.deepcopy(self.fixture)
        duplicate["types"].append(copy.deepcopy(duplicate["types"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate type ID"):
            self.validate(self.schema, duplicate)

        dangling = copy.deepcopy(self.fixture)
        dangling["declarations"][1]["type_id"] = "type:missing"
        with self.assertRaisesRegex(ValueError, "dangling reference"):
            self.validate(self.schema, dangling)

    def test_graph_rejects_missing_source_file(self):
        document = copy.deepcopy(self.fixture)
        document["declarations"][0]["source"]["spelling"]["file_id"] = "file:missing"
        with self.assertRaisesRegex(ValueError, "dangling reference"):
            self.validate(self.schema, document)

    def pointer_document(self):
        document = copy.deepcopy(self.fixture)
        pointer = {
            "id": "type:pointer",
            "kind": "pointer",
            "spelling": "int *",
            "canonical_id": "type:pointer",
            "pointee_id": "type:int",
            "qualifiers": {"const": False, "volatile": False, "restrict": False},
        }
        document["types"].append(pointer)
        document["declarations"][1]["type_id"] = pointer["id"]
        return document

    def test_valid_pointer_graph(self):
        self.validate(self.schema, self.pointer_document())

    def test_structural_edges_are_required_and_kind_specific(self):
        missing = self.pointer_document()
        del missing["types"][-1]["pointee_id"]
        with self.assertRaisesRegex(ValueError, "missing structural fields"):
            self.validate(self.schema, missing)
        extra = self.pointer_document()
        extra["types"][-1]["element_id"] = "type:int"
        with self.assertRaisesRegex(ValueError, "invalid structural fields"):
            self.validate(self.schema, extra)

    def test_canonical_type_links_are_not_cycles_or_wrong_kinds(self):
        document = self.pointer_document()
        document["types"][-1]["canonical_id"] = "type:int"
        with self.assertRaisesRegex(ValueError, "canonical kind"):
            self.validate(self.schema, document)
        document = self.pointer_document()
        document["types"][-1]["canonical_id"] = "type:int"
        document["types"][0]["canonical_id"] = "type:pointer"
        with self.assertRaisesRegex(ValueError, "not self-canonical"):
            self.validate(self.schema, document)

    def test_recursive_type_edges_are_rejected(self):
        document = self.pointer_document()
        document["types"][-1]["pointee_id"] = "type:pointer"
        with self.assertRaisesRegex(ValueError, "structural type cycle"):
            self.validate(self.schema, document)

    def test_record_type_reference_has_correct_declaration_kind(self):
        document = copy.deepcopy(self.fixture)
        document["types"][1]["declaration_id"] = "decl:sample.value"
        with self.assertRaisesRegex(ValueError, "wrong declaration kind"):
            self.validate(self.schema, document)

    def test_record_member_ownership_and_order_uniqueness(self):
        document = copy.deepcopy(self.fixture)
        document["declarations"][0]["field_ids"].append("decl:sample.value")
        with self.assertRaisesRegex(ValueError, "duplicate field_ids"):
            self.validate(self.schema, document)
        document = copy.deepcopy(self.fixture)
        document["declarations"][0]["field_ids"] = []
        with self.assertRaisesRegex(ValueError, "inconsistent field ownership"):
            self.validate(self.schema, document)

    def test_incomplete_record_cannot_claim_layout(self):
        document = copy.deepcopy(self.fixture)
        document["declarations"][0]["complete"] = False
        with self.assertRaisesRegex(ValueError, "incomplete record"):
            self.validate(self.schema, document)

    def test_arrays_are_one_dimension_per_node(self):
        document = self.pointer_document()
        array = document["types"][-1]
        array.update(kind="array", element_id="type:int", extent=[2, 3])
        del array["pointee_id"]
        with self.assertRaises(ValidationError):
            self.validate(self.schema, document)
        array["extent"] = 2
        self.validate(self.schema, document)
        array["extent"] = None
        self.validate(self.schema, document)
        array["qualifiers"]["const"] = True
        with self.assertRaisesRegex(ValueError, "array qualifiers"):
            self.validate(self.schema, document)

    def test_rooted_paths_are_relative_unique_and_mapped(self):
        for value in ("/absolute.hh", "../escape.hh", "a/../b.hh", "a//b.hh"):
            document = copy.deepcopy(self.fixture)
            document["files"][0]["path"]["portable"] = value
            with self.assertRaises((ValueError, ValidationError)):
                self.validate(self.schema, document)
        document = copy.deepcopy(self.fixture)
        document["files"][0]["path"]["root"] = "missing"
        with self.assertRaisesRegex(ValueError, "dangling reference"):
            self.validate(self.schema, document)
        document = copy.deepcopy(self.fixture)
        duplicate = copy.deepcopy(document["files"][0])
        duplicate["id"] = "file:duplicate"
        document["files"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate rooted file path"):
            self.validate(self.schema, document)

    def test_layout_quantities_use_exact_canonical_json_integers(self):
        for value in (0, 9007199254740991, "9007199254740992", "18446744073709551615"):
            document = copy.deepcopy(self.fixture)
            document["declarations"][0]["size_bits"] = value
            document["declarations"][0]["data_size_bits"] = value
            document["declarations"][0]["non_virtual_size_bits"] = value
            self.validate(self.schema, document)
        for value in (9007199254740992, "1", "0", "09007199254740992", -1):
            document = copy.deepcopy(self.fixture)
            document["declarations"][0]["size_bits"] = value
            with self.assertRaises((ValueError, ValidationError)):
                self.validate(self.schema, document)

    def test_alias_underlying_type_must_match_canonical_target(self):
        document = self.pointer_document()
        alias = copy.deepcopy(document["declarations"][0])
        for key in (
            "type_id",
            "complete",
            "field_ids",
            "nested_declaration_ids",
            "callable_ids",
            "special_members",
            "bases",
            "virtual_base_offsets",
            "data_size_bits",
            "non_virtual_size_bits",
            "non_virtual_alignment_bits",
        ):
            alias.pop(key)
        alias.update(
            id="decl:alias",
            canonical_declaration_id="decl:alias",
            kind="alias",
            capabilities=[],
            type_id="type:alias",
            underlying_type_id="type:int",
        )
        document["declarations"].append(alias)
        document["types"].append({
            "id": "type:alias",
            "kind": "alias",
            "spelling": "Alias",
            "canonical_id": "type:int",
            "declaration_id": "decl:alias",
            "qualifiers": {"const": False, "volatile": False, "restrict": False},
        })
        self.validate(self.schema, document)
        alias["underlying_type_id"] = "type:pointer"
        with self.assertRaisesRegex(ValueError, "inconsistent alias target"):
            self.validate(self.schema, document)

    def test_enumerator_source_references_are_checked(self):
        document = copy.deepcopy(self.fixture)
        source = copy.deepcopy(document["declarations"][0]["source"])
        source["spelling"]["file_id"] = "file:absent"
        document["declarations"][0]["enumerators"] = [
            {
                "name": "Value",
                "value": "1",
                "source": source,
                "annotations": [],
            }
        ]
        with self.assertRaisesRegex(ValueError, "dangling reference"):
            self.validate(self.schema, document)

    def namespace_document(self):
        document = copy.deepcopy(self.fixture)
        record = document["declarations"][0]
        namespace = {
            key: copy.deepcopy(record[key])
            for key in (
                "source",
                "access",
                "origin",
                "definition",
                "annotations",
                "capabilities",
            )
        }
        namespace.update(
            id="decl:namespace",
            canonical_declaration_id="decl:namespace",
            kind="namespace",
            capabilities=[],
            name="N",
            qualified_name="N",
            usr="c:@N@N",
            identity_kind="usr",
            anonymous=False,
            inline=False,
            declaration_ids=[record["id"]],
            reopening_sources=[copy.deepcopy(record["source"])],
        )
        record["semantic_parent_id"] = namespace["id"]
        record["lexical_parent_id"] = namespace["id"]
        document["declarations"].append(namespace)
        return document

    def test_namespace_ownership_is_bidirectional(self):
        self.validate(self.schema, self.namespace_document())
        document = self.namespace_document()
        document["declarations"][-1]["declaration_ids"] = []
        with self.assertRaisesRegex(ValueError, "namespace ownership"):
            self.validate(self.schema, document)
        document = self.namespace_document()
        del document["declarations"][0]["semantic_parent_id"]
        with self.assertRaisesRegex(ValueError, "invalid namespace member"):
            self.validate(self.schema, document)

    def test_namespace_blocks_and_member_order_are_validated(self):
        document = self.namespace_document()
        document["declarations"][-1]["reopening_sources"][0]["spelling"]["file_id"] = (
            "file:absent"
        )
        with self.assertRaisesRegex(ValueError, "dangling reference"):
            self.validate(self.schema, document)
        document = self.namespace_document()
        document["declarations"][-1]["reopening_sources"][0]["spelling"]["line"] += 1
        with self.assertRaisesRegex(ValueError, "not its first block"):
            self.validate(self.schema, document)
        document = self.namespace_document()
        namespace = document["declarations"][-1]
        namespace["declaration_ids"].insert(0, namespace["id"])
        namespace["declaration_ids"].sort(reverse=True)
        with self.assertRaisesRegex(ValueError, "members are not sorted"):
            self.validate(self.schema, document)

    def test_namespace_alias_targets_and_cycles_are_validated(self):
        document = self.namespace_document()
        alias = copy.deepcopy(document["declarations"][-1])
        for key in ("anonymous", "inline", "declaration_ids", "reopening_sources"):
            del alias[key]
        alias.update(
            id="decl:alias",
            canonical_declaration_id="decl:alias",
            kind="namespace_alias",
            name="Alias",
            qualified_name="Alias",
            target_namespace_id="decl:namespace",
        )
        document["declarations"].append(alias)
        self.validate(self.schema, document)
        alias["target_namespace_id"] = "decl:sample"
        with self.assertRaisesRegex(ValueError, "invalid namespace alias target"):
            self.validate(self.schema, document)
        alias["target_namespace_id"] = alias["id"]
        with self.assertRaisesRegex(ValueError, "context/alias cycle"):
            self.validate(self.schema, document)

    def test_context_cycles_and_wrong_parent_kinds_are_rejected(self):
        for edge in ("semantic_parent_id", "lexical_parent_id"):
            document = self.namespace_document()
            namespace = document["declarations"][-1]
            namespace[edge] = namespace["id"]
            if edge == "semantic_parent_id":
                namespace["declaration_ids"].append(namespace["id"])
                namespace["declaration_ids"].sort()
            with self.assertRaisesRegex(ValueError, "context/alias cycle"):
                self.validate(self.schema, document)
        document = self.namespace_document()
        document["declarations"][0]["lexical_parent_id"] = "decl:sample.value"
        with self.assertRaisesRegex(ValueError, "invalid declaration context"):
            self.validate(self.schema, document)

    def test_identity_origin_and_anonymous_naming_are_consistent(self):
        document = self.namespace_document()
        document["declarations"][-1]["identity_kind"] = "source"
        with self.assertRaisesRegex(ValueError, "must inherit source identity"):
            self.validate(self.schema, document)
        for node in document["declarations"]:
            node["identity_kind"] = "source"
        self.validate(self.schema, document)
        document["declarations"][-1]["anonymous"] = True
        with self.assertRaisesRegex(ValueError, "inconsistent anonymous naming"):
            self.validate(self.schema, document)
        document = self.namespace_document()
        namespace = document["declarations"][-1]
        namespace.update(name="", anonymous=True)
        with self.assertRaisesRegex(ValueError, "requires source identity"):
            self.validate(self.schema, document)
        document = self.namespace_document()
        document["declarations"][0]["usr"] = None
        with self.assertRaisesRegex(ValueError, "no USR"):
            self.validate(self.schema, document)

    def anonymous_storage_document(self):
        document = copy.deepcopy(self.fixture)
        outer, field = document["declarations"]
        nested = copy.deepcopy(outer)
        nested.update(
            id="decl:anonymous",
            canonical_declaration_id="decl:anonymous",
            name="",
            qualified_name="Sample::(anonymous)",
            anonymous=True,
            identity_kind="source",
            semantic_parent_id=outer["id"],
            type_id="type:anonymous",
            field_ids=[],
        )
        outer["nested_declaration_ids"] = [nested["id"]]
        field.update(
            name="",
            anonymous_member=True,
            identity_kind="source",
            type_id=nested["type_id"],
        )
        record_type = copy.deepcopy(document["types"][1])
        record_type.update(
            id=nested["type_id"],
            canonical_id=nested["type_id"],
            declaration_id=nested["id"],
        )
        document["types"].append(record_type)
        document["declarations"].append(nested)
        return document

    def test_anonymous_storage_requires_unnamed_record_in_same_context(self):
        document = self.anonymous_storage_document()
        self.validate(self.schema, document)
        document["declarations"][1]["type_id"] = "type:int"
        with self.assertRaisesRegex(ValueError, "must have an unnamed record type"):
            self.validate(self.schema, document)
        document = self.anonymous_storage_document()
        document["declarations"][-1]["anonymous"] = False
        with self.assertRaisesRegex(ValueError, "must have an unnamed record type"):
            self.validate(self.schema, document)
        document = self.anonymous_storage_document()
        document["declarations"][0]["nested_declaration_ids"] = []
        with self.assertRaisesRegex(ValueError, "belongs to another context"):
            self.validate(self.schema, document)
        document = self.anonymous_storage_document()
        document["declarations"][1]["identity_kind"] = "usr"
        with self.assertRaisesRegex(
            ValueError, "anonymous storage requires source identity"
        ):
            self.validate(self.schema, document)

    def test_nested_declaration_ownership_is_bidirectional(self):
        document = self.anonymous_storage_document()
        document["declarations"][1].update(name="named", anonymous_member=False)
        document["declarations"][0]["nested_declaration_ids"] = []
        with self.assertRaisesRegex(ValueError, "nested declaration ownership"):
            self.validate(self.schema, document)

    def enum_document(self):
        document = copy.deepcopy(self.fixture)
        record = document["declarations"][0]
        node = {
            key: copy.deepcopy(record[key])
            for key in (
                "source",
                "access",
                "origin",
                "annotations",
                "capabilities",
            )
        }
        node.update(
            id="decl:enum",
            canonical_declaration_id="decl:enum",
            kind="enum",
            capabilities=[],
            name="E",
            qualified_name="E",
            usr="c:@E@E",
            identity_kind="usr",
            anonymous=False,
            scoped=True,
            underlying_fixed=True,
            underlying_signed=True,
            complete=True,
            definition=True,
            size_bits=32,
            alignment_bits=32,
            type_id="type:enum",
            underlying_type_id="type:int",
            enumerators=[
                {
                    "name": "Value",
                    "value": "-1",
                    "source": copy.deepcopy(record["source"]),
                    "annotations": [],
                }
            ],
        )
        document["declarations"].append(node)
        document["types"].append({
            "id": "type:enum",
            "kind": "enum",
            "spelling": "E",
            "canonical_id": "type:enum",
            "declaration_id": node["id"],
            "qualifiers": {"const": False, "volatile": False, "restrict": False},
        })
        return document

    def test_enum_type_and_required_facts_are_validated(self):
        self.validate(self.schema, self.enum_document())
        for key in (
            "underlying_fixed",
            "underlying_signed",
            "underlying_type_id",
            "enumerators",
        ):
            document = self.enum_document()
            del document["declarations"][-1][key]
            with self.assertRaisesRegex(ValueError, "missing structural fields"):
                self.validate(self.schema, document)
        document = self.enum_document()
        document["types"][-1]["declaration_id"] = "decl:sample"
        with self.assertRaisesRegex(ValueError, "wrong declaration kind"):
            self.validate(self.schema, document)
        document = self.enum_document()
        document["declarations"][-1]["underlying_type_id"] = "type:enum"
        with self.assertRaisesRegex(ValueError, "not a supported integral type"):
            self.validate(self.schema, document)

    def test_enum_values_are_canonical_exact_and_range_checked(self):
        for value in ("-2147483648", "0", "2147483647"):
            document = self.enum_document()
            document["declarations"][-1]["enumerators"][0]["value"] = value
            self.validate(self.schema, document)
        for value in ("-0", "01", "+1", "-01", 1):
            document = self.enum_document()
            document["declarations"][-1]["enumerators"][0]["value"] = value
            with self.assertRaises(ValidationError):
                self.validate(self.schema, document)
        for value in ("2147483648", "-2147483649"):
            document = self.enum_document()
            document["declarations"][-1]["enumerators"][0]["value"] = value
            with self.assertRaisesRegex(ValueError, "outside its underlying range"):
                self.validate(self.schema, document)

    def test_unsigned_enum_range_and_signedness_are_checked(self):
        document = self.enum_document()
        node = document["declarations"][-1]
        node.update(underlying_signed=False, underlying_type_id="type:unsigned")
        underlying = copy.deepcopy(document["types"][0])
        underlying.update(
            id="type:unsigned", canonical_id="type:unsigned", spelling="unsigned int"
        )
        document["types"].append(underlying)
        for value in ("0", "4294967295"):
            node["enumerators"][0]["value"] = value
            self.validate(self.schema, document)
        for value in ("-1", "4294967296"):
            node["enumerators"][0]["value"] = value
            with self.assertRaisesRegex(ValueError, "outside its underlying range"):
                self.validate(self.schema, document)
        node["underlying_signed"] = True
        with self.assertRaisesRegex(ValueError, "underlying signedness"):
            self.validate(self.schema, document)

    def test_enum_definition_completeness_and_scoping_are_independent(self):
        document = self.enum_document()
        node = document["declarations"][-1]
        node.update(definition=False, enumerators=[])
        self.validate(self.schema, document)
        node["underlying_fixed"] = False
        with self.assertRaisesRegex(ValueError, "scoped enum must be named and fixed"):
            self.validate(self.schema, document)
        node["scoped"] = False
        with self.assertRaisesRegex(ValueError, "opaque enum must be fixed"):
            self.validate(self.schema, document)
        node.update(underlying_fixed=True, complete=False)
        with self.assertRaisesRegex(ValueError, "complete integral layout"):
            self.validate(self.schema, document)

    def test_enum_members_allow_duplicate_values_not_duplicate_names(self):
        document = self.enum_document()
        node = document["declarations"][-1]
        duplicate = copy.deepcopy(node["enumerators"][0])
        duplicate["name"] = "SameValue"
        node["enumerators"].append(duplicate)
        self.validate(self.schema, document)
        duplicate["name"] = "Value"
        with self.assertRaisesRegex(ValueError, "duplicate enumerator names"):
            self.validate(self.schema, document)
        node["enumerators"].pop()
        node["enumerators"][0]["annotations"] = [
            {
                "syntax": "comment",
                "payload": "note",
                "source": copy.deepcopy(node["source"]),
            }
        ]
        node["enumerators"][0]["annotations"][0]["source"]["spelling"]["file_id"] = (
            "file:missing"
        )
        with self.assertRaisesRegex(ValueError, "dangling reference"):
            self.validate(self.schema, document)

    def bitfield_document(self):
        document = copy.deepcopy(self.fixture)
        document["declarations"][1].update(
            bitfield=True,
            bit_width=3,
            capabilities=[
                {
                    "name": "field-address",
                    "status": "unsupported",
                    "reason_code": "BITFIELD_NOT_ADDRESSABLE",
                }
            ],
        )
        return document

    def test_bitfield_width_padding_and_layout_are_validated(self):
        self.validate(self.schema, self.bitfield_document())
        for mutation, message in (
            ({"bit_width": None}, "concrete 32-bit width"),
            ({"bit_width": 4294967296}, "concrete 32-bit width"),
            ({"bit_width": 0}, "zero-width bitfield must be unnamed"),
            ({"offset_bits": 31}, "exceeds its owning record layout"),
            ({"type_id": "type:sample"}, "not a supported integral type"),
            ({"name": ""}, "unnamed bitfield requires source identity"),
        ):
            document = self.bitfield_document()
            document["declarations"][1].update(mutation)
            with self.assertRaisesRegex(ValueError, message):
                self.validate(self.schema, document)
        document = self.bitfield_document()
        document["declarations"][1].update(
            name="", identity_kind="source", bit_width=0, offset_bits=32
        )
        self.validate(self.schema, document)

    def test_bitfield_cannot_claim_addressability_or_disappear_into_aggregate(self):
        for mutation in (
            {"capabilities": []},
            {"anonymous_member": True},
            {"bitfield": False},
        ):
            document = self.bitfield_document()
            document["declarations"][1].update(mutation)
            with self.assertRaises(ValueError):
                self.validate(self.schema, document)
        document = self.bitfield_document()
        document["declarations"][1]["capabilities"][0]["status"] = "supported"
        with self.assertRaisesRegex(ValueError, "explicitly non-addressable"):
            self.validate(self.schema, document)

    def test_enum_properties_cannot_be_attached_to_a_record(self):
        document = copy.deepcopy(self.fixture)
        document["declarations"][0]["scoped"] = True
        with self.assertRaisesRegex(ValueError, "enum-only fields"):
            self.validate(self.schema, document)

    def inheritance_document(self, virtual=False):
        document = copy.deepcopy(self.fixture)
        derived, field = document["declarations"]
        base = copy.deepcopy(derived)
        base.update(
            id="decl:base",
            canonical_declaration_id="decl:base",
            name="Base",
            qualified_name="Base",
            usr="c:@S@Base",
            type_id="type:base",
            field_ids=[],
        )
        base_type = copy.deepcopy(document["types"][1])
        base_type.update(
            id="type:base",
            canonical_id="type:base",
            declaration_id="decl:base",
            spelling="Base",
        )
        document["types"].append(base_type)
        document["declarations"].append(base)
        derived.update(
            size_bits=64, data_size_bits=64, non_virtual_size_bits=32 if virtual else 64
        )
        field["offset_bits"] = 0 if virtual else 32
        derived["bases"] = [
            {
                "declaration_id": "decl:base",
                "type_id": "type:base",
                "access": "public",
                "written_access": "none",
                "virtual": virtual,
                "offset_bits": None if virtual else 0,
                "source": copy.deepcopy(derived["source"]),
            }
        ]
        if virtual:
            derived["virtual_base_offsets"] = [
                {"declaration_id": "decl:base", "offset_bits": 32}
            ]
        return document

    def test_inheritance_types_and_targets_must_match(self):
        self.validate(self.schema, self.inheritance_document())
        for change, message in (
            ({"type_id": "type:int"}, "base type does not match"),
            ({"declaration_id": "decl:sample.value"}, "complete non-union record"),
        ):
            document = self.inheritance_document()
            document["declarations"][0]["bases"][0].update(change)
            with self.assertRaisesRegex(ValueError, message):
                self.validate(self.schema, document)
        document = self.inheritance_document()
        document["declarations"][-1]["record_tag"] = "union"
        with self.assertRaisesRegex(ValueError, "complete non-union record"):
            self.validate(self.schema, document)

    def test_base_access_default_and_written_access_agree(self):
        document = self.inheritance_document()
        node = document["declarations"][0]
        node["record_tag"] = "class"
        with self.assertRaisesRegex(ValueError, "inconsistent base access"):
            self.validate(self.schema, document)
        node["bases"][0]["access"] = "private"
        self.validate(self.schema, document)
        node["bases"][0]["written_access"] = "public"
        with self.assertRaisesRegex(ValueError, "inconsistent base access"):
            self.validate(self.schema, document)

    def test_virtual_edges_and_complete_object_offsets_are_distinct(self):
        self.validate(self.schema, self.inheritance_document(virtual=True))
        document = self.inheritance_document(virtual=True)
        document["declarations"][0]["bases"][0]["offset_bits"] = 32
        with self.assertRaisesRegex(ValueError, "virtual edge must not claim"):
            self.validate(self.schema, document)
        for offset in (None, 65):
            document = self.inheritance_document(virtual=True)
            document["declarations"][0]["virtual_base_offsets"][0]["offset_bits"] = (
                offset
            )
            with self.assertRaisesRegex(ValueError, "invalid complete-object offset"):
                self.validate(self.schema, document)
        document = self.inheritance_document()
        document["declarations"][0]["bases"][0]["offset_bits"] = None
        with self.assertRaisesRegex(
            ValueError, "nonvirtual base has an invalid offset"
        ):
            self.validate(self.schema, document)

    def test_duplicate_direct_bases_and_inheritance_cycles_are_rejected(self):
        document = self.inheritance_document()
        node = document["declarations"][0]
        node["bases"].append(copy.deepcopy(node["bases"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate direct bases"):
            self.validate(self.schema, document)
        document = self.inheritance_document()
        node = document["declarations"][0]
        node["bases"][0].update(declaration_id=node["id"], type_id=node["type_id"])
        with self.assertRaisesRegex(ValueError, "inheritance cycle"):
            self.validate(self.schema, document)

    def test_virtual_base_table_is_unique_and_matches_transitive_closure(self):
        for virtual in (False, True):
            document = self.inheritance_document(virtual=virtual)
            node = document["declarations"][0]
            node["virtual_base_offsets"] = (
                [] if virtual else [{"declaration_id": "decl:base", "offset_bits": 32}]
            )
            with self.assertRaisesRegex(
                ValueError, "inconsistent virtual base closure"
            ):
                self.validate(self.schema, document)
        document = self.inheritance_document(virtual=True)
        table = document["declarations"][0]["virtual_base_offsets"]
        table.append(copy.deepcopy(table[0]))
        with self.assertRaisesRegex(ValueError, "unique and sorted"):
            self.validate(self.schema, document)
        document = self.inheritance_document(virtual=True)
        original, middle = document["declarations"][0], document["declarations"][-1]
        deepest = copy.deepcopy(middle)
        deepest.update(
            id="decl:deep", canonical_declaration_id="decl:deep", type_id="type:deep"
        )
        deepest_type = copy.deepcopy(document["types"][-1])
        deepest_type.update(
            id="type:deep", canonical_id="type:deep", declaration_id="decl:deep"
        )
        document["declarations"].append(deepest)
        document["types"].append(deepest_type)
        middle["bases"] = [copy.deepcopy(original["bases"][0])]
        middle["bases"][0].update(declaration_id="decl:deep", type_id="type:deep")
        middle["virtual_base_offsets"] = [
            {"declaration_id": "decl:deep", "offset_bits": 16}
        ]
        with self.assertRaisesRegex(ValueError, "inconsistent virtual base closure"):
            self.validate(self.schema, document)
        original["virtual_base_offsets"].append({
            "declaration_id": "decl:deep",
            "offset_bits": 48,
        })
        self.validate(self.schema, document)

    def test_base_source_and_virtual_base_references_are_checked(self):
        document = self.inheritance_document()
        document["declarations"][0]["bases"][0]["source"]["spelling"]["file_id"] = (
            "file:missing"
        )
        with self.assertRaisesRegex(ValueError, "dangling reference"):
            self.validate(self.schema, document)
        document = self.inheritance_document(virtual=True)
        document["declarations"][0]["virtual_base_offsets"][0]["declaration_id"] = (
            "decl:missing"
        )
        with self.assertRaisesRegex(ValueError, "dangling reference"):
            self.validate(self.schema, document)

    def test_record_subobject_layout_is_required_and_bounded(self):
        for key in (
            "data_size_bits",
            "non_virtual_size_bits",
            "non_virtual_alignment_bits",
        ):
            document = self.inheritance_document()
            del document["declarations"][0][key]
            with self.assertRaisesRegex(ValueError, "missing structural fields"):
                self.validate(self.schema, document)
        for key, value in (
            ("data_size_bits", 65),
            ("non_virtual_size_bits", 65),
            ("non_virtual_alignment_bits", 0),
        ):
            document = self.inheritance_document()
            document["declarations"][0][key] = value
            with self.assertRaisesRegex(ValueError, "inconsistent record layout sizes"):
                self.validate(self.schema, document)
        document = self.inheritance_document()
        document["declarations"][0]["complete"] = False
        with self.assertRaisesRegex(ValueError, "incomplete record"):
            self.validate(self.schema, document)

    def callable_document(self, member=False):
        document = copy.deepcopy(self.fixture)
        owner = document["declarations"][0]
        parameter = {
            "name": "value",
            "type_id": "type:int",
            "original_type_id": "type:int",
            "source": copy.deepcopy(owner["source"]),
            "annotations": [],
            "has_default": False,
            "default_spelling": None,
            "default_source": None,
        }
        node = {
            key: copy.deepcopy(owner[key])
            for key in ("source", "origin", "annotations", "capabilities")
        }
        node.update(
            id="decl:f",
            canonical_declaration_id="decl:f",
            kind="callable",
            capabilities=[],
            name="f",
            qualified_name="Sample::f" if member else "f",
            usr="c:@F@f#I#",
            identity_kind="usr",
            access="public" if member else "none",
            definition=False,
            callable_kind="method" if member else "function",
            special_member_kind="none",
            return_type_id="type:int",
            parameters=[parameter],
            const=False,
            volatile=False,
            static=False,
            ref_qualifier="none",
            noexcept="false",
            virtual=False,
            pure=False,
            final=False,
            deleted=False,
            defaulted=False,
            explicit=False,
            constexpr=False,
            variadic=False,
            user_provided=True,
            calling_convention="c",
            linkage="external",
            overridden_declaration_ids=[],
            overridden_implicit_destructor_record_ids=[],
            redeclarations=[
                {
                    "source": copy.deepcopy(owner["source"]),
                    "parameters": [copy.deepcopy(parameter)],
                    "annotations": [],
                    "definition": False,
                }
            ],
        )
        if member:
            node["semantic_parent_id"] = owner["id"]
            node["lexical_parent_id"] = owner["id"]
            node["redeclarations"][0]["lexical_parent_id"] = owner["id"]
            owner["callable_ids"] = [node["id"]]
        document["declarations"].append(node)
        return document

    def test_callable_required_fields_and_ownership(self):
        for member in (False, True):
            self.validate(self.schema, self.callable_document(member))
        document = self.callable_document(True)
        document["declarations"][0]["callable_ids"] = []
        with self.assertRaisesRegex(ValueError, "callable ownership"):
            self.validate(self.schema, document)
        document = self.callable_document()
        del document["declarations"][-1]["noexcept"]
        with self.assertRaisesRegex(ValueError, "missing structural fields"):
            self.validate(self.schema, document)

    def test_callable_flags_are_kind_specific(self):
        for mutation in (
            {"static": True},
            {"const": True},
            {"pure": True},
            {"explicit": True},
            {"return_type_id": None},
            {"defaulted": True},
        ):
            document = self.callable_document()
            document["declarations"][-1].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.validate(self.schema, document)
        document = self.callable_document(True)
        document["declarations"][-1].update(static=True, virtual=True)
        with self.assertRaisesRegex(ValueError, "invalid instance-method flags"):
            self.validate(self.schema, document)

    def test_callable_default_evidence_is_all_or_nothing(self):
        for mutation in (
            {"has_default": True},
            {"default_spelling": "2"},
            {"default_source": self.fixture["declarations"][0]["source"]},
        ):
            document = self.callable_document()
            node = document["declarations"][-1]
            node["parameters"][0].update(mutation)
            node["redeclarations"][0]["parameters"] = copy.deepcopy(node["parameters"])
            with (
                self.subTest(mutation=mutation),
                self.assertRaisesRegex(ValueError, "default argument evidence"),
            ):
                self.validate(self.schema, document)

    def test_callable_redeclaration_signature_and_evidence_match(self):
        document = self.callable_document()
        node = document["declarations"][-1]
        prior = copy.deepcopy(node["redeclarations"][0])
        node["redeclarations"].insert(0, prior)
        prior["parameters"][0].update(
            type_id="type:sample", original_type_id="type:sample"
        )
        with self.assertRaisesRegex(ValueError, "redeclaration parameter types"):
            self.validate(self.schema, document)
        document = self.callable_document()
        document["declarations"][-1]["definition"] = True
        with self.assertRaisesRegex(ValueError, "definition evidence"):
            self.validate(self.schema, document)
        document = self.callable_document()
        document["declarations"][-1]["parameters"][0]["name"] = "renamed"
        with self.assertRaisesRegex(ValueError, "last redeclaration"):
            self.validate(self.schema, document)

    def test_callable_parameter_source_type_and_annotation_links(self):
        for field in ("type_id", "original_type_id"):
            document = self.callable_document()
            document["declarations"][-1]["parameters"][0][field] = "type:missing"
            with self.assertRaisesRegex(ValueError, "dangling reference"):
                self.validate(self.schema, document)
        document = self.callable_document()
        document["declarations"][-1]["redeclarations"][0]["parameters"][0]["source"][
            "spelling"
        ]["file_id"] = "file:missing"
        with self.assertRaisesRegex(ValueError, "dangling reference"):
            self.validate(self.schema, document)
        document = self.callable_document()
        node = document["declarations"][-1]
        node["parameters"][0]["original_type_id"] = "type:sample"
        node["redeclarations"][0]["parameters"] = copy.deepcopy(node["parameters"])
        with self.assertRaisesRegex(ValueError, "original parameter type"):
            self.validate(self.schema, document)

    def test_callable_override_targets_must_be_virtual_base_members(self):
        document = self.callable_document(True)
        node = document["declarations"][-1]
        node.update(virtual=True, overridden_declaration_ids=[node["id"]])
        with self.assertRaisesRegex(ValueError, "invalid overridden callable"):
            self.validate(self.schema, document)
        node["overridden_declaration_ids"] = []
        node.update(
            callable_kind="destructor",
            return_type_id=None,
            parameters=[],
            special_member_kind="destructor",
            overridden_implicit_destructor_record_ids=["decl:sample"],
        )
        node["redeclarations"][0]["parameters"] = []
        with self.assertRaises(ValueError):
            self.validate(self.schema, document)

    def test_special_member_summary_states_are_not_interchangeable(self):
        for mutation in (
            {"state": "unknown"},
            {"state": "suppressed"},
            {"state": "user_declared"},
            {"deleted": None},
            {"virtual": True},
        ):
            document = copy.deepcopy(self.fixture)
            document["declarations"][0]["special_members"][0].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.validate(self.schema, document)
        document = copy.deepcopy(self.fixture)
        document["declarations"][0]["special_members"].reverse()
        with self.assertRaisesRegex(ValueError, "six special-member kinds"):
            self.validate(self.schema, document)

    def test_user_special_member_links_must_match_record_callable_list(self):
        document = self.callable_document(True)
        node = document["declarations"][-1]
        node.update(
            callable_kind="constructor",
            return_type_id=None,
            parameters=[],
            special_member_kind="default_constructor",
        )
        node["redeclarations"][0]["parameters"] = []
        slot = document["declarations"][0]["special_members"][0]
        with self.assertRaisesRegex(ValueError, "special-member declaration links"):
            self.validate(self.schema, document)
        slot.update(
            state="user_declared",
            declaration_ids=[node["id"]],
            deleted=None,
            trivial=None,
            virtual=None,
            noexcept=None,
        )
        self.validate(self.schema, document)


if __name__ == "__main__":
    unittest.main()
