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

    def test_minimal_record_is_valid(self):
        ir.validate(self.schema, self.fixture)

    def test_schema_rejects_unknown_fields_and_wrong_version(self):
        for mutation in (
            lambda value: value.update(schema_version=1),
            lambda value: value.update(schema_version=2),
            lambda value: value.update(schema_version=3),
            lambda value: value.update(schema_version=5),
            lambda value: value.update(clang_ast={}),
        ):
            document = copy.deepcopy(self.fixture)
            mutation(document)
            with self.assertRaises(ValidationError):
                ir.validate(self.schema, document)

    def test_graph_rejects_duplicate_and_dangling_ids(self):
        duplicate = copy.deepcopy(self.fixture)
        duplicate["types"].append(copy.deepcopy(duplicate["types"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate type ID"):
            ir.validate(self.schema, duplicate)

        dangling = copy.deepcopy(self.fixture)
        dangling["declarations"][1]["type_id"] = "type:missing"
        with self.assertRaisesRegex(ValueError, "dangling reference"):
            ir.validate(self.schema, dangling)

    def test_graph_rejects_missing_source_file(self):
        document = copy.deepcopy(self.fixture)
        document["declarations"][0]["source"]["spelling"]["file_id"] = "file:missing"
        with self.assertRaisesRegex(ValueError, "dangling reference"):
            ir.validate(self.schema, document)

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
        ir.validate(self.schema, self.pointer_document())

    def test_structural_edges_are_required_and_kind_specific(self):
        missing = self.pointer_document()
        del missing["types"][-1]["pointee_id"]
        with self.assertRaisesRegex(ValueError, "missing structural fields"):
            ir.validate(self.schema, missing)
        extra = self.pointer_document()
        extra["types"][-1]["element_id"] = "type:int"
        with self.assertRaisesRegex(ValueError, "invalid structural fields"):
            ir.validate(self.schema, extra)

    def test_canonical_type_links_are_not_cycles_or_wrong_kinds(self):
        document = self.pointer_document()
        document["types"][-1]["canonical_id"] = "type:int"
        with self.assertRaisesRegex(ValueError, "canonical kind"):
            ir.validate(self.schema, document)
        document = self.pointer_document()
        document["types"][-1]["canonical_id"] = "type:int"
        document["types"][0]["canonical_id"] = "type:pointer"
        with self.assertRaisesRegex(ValueError, "not self-canonical"):
            ir.validate(self.schema, document)

    def test_recursive_type_edges_are_rejected(self):
        document = self.pointer_document()
        document["types"][-1]["pointee_id"] = "type:pointer"
        with self.assertRaisesRegex(ValueError, "structural type cycle"):
            ir.validate(self.schema, document)

    def test_record_type_reference_has_correct_declaration_kind(self):
        document = copy.deepcopy(self.fixture)
        document["types"][1]["declaration_id"] = "decl:sample.value"
        with self.assertRaisesRegex(ValueError, "wrong declaration kind"):
            ir.validate(self.schema, document)

    def test_record_member_ownership_and_order_uniqueness(self):
        document = copy.deepcopy(self.fixture)
        document["declarations"][0]["field_ids"].append("decl:sample.value")
        with self.assertRaisesRegex(ValueError, "duplicate field_ids"):
            ir.validate(self.schema, document)
        document = copy.deepcopy(self.fixture)
        document["declarations"][0]["field_ids"] = []
        with self.assertRaisesRegex(ValueError, "inconsistent field ownership"):
            ir.validate(self.schema, document)

    def test_incomplete_record_cannot_claim_layout(self):
        document = copy.deepcopy(self.fixture)
        document["declarations"][0]["complete"] = False
        with self.assertRaisesRegex(ValueError, "incomplete record"):
            ir.validate(self.schema, document)

    def test_arrays_are_one_dimension_per_node(self):
        document = self.pointer_document()
        array = document["types"][-1]
        array.update(kind="array", element_id="type:int", extent=[2, 3])
        del array["pointee_id"]
        with self.assertRaises(ValidationError):
            ir.validate(self.schema, document)
        array["extent"] = 2
        ir.validate(self.schema, document)
        array["extent"] = None
        ir.validate(self.schema, document)
        array["qualifiers"]["const"] = True
        with self.assertRaisesRegex(ValueError, "array qualifiers"):
            ir.validate(self.schema, document)

    def test_rooted_paths_are_relative_unique_and_mapped(self):
        for value in ("/absolute.hh", "../escape.hh", "a/../b.hh", "a//b.hh"):
            document = copy.deepcopy(self.fixture)
            document["files"][0]["path"]["portable"] = value
            with self.assertRaises((ValueError, ValidationError)):
                ir.validate(self.schema, document)
        document = copy.deepcopy(self.fixture)
        document["files"][0]["path"]["root"] = "missing"
        with self.assertRaisesRegex(ValueError, "dangling reference"):
            ir.validate(self.schema, document)
        document = copy.deepcopy(self.fixture)
        duplicate = copy.deepcopy(document["files"][0])
        duplicate["id"] = "file:duplicate"
        document["files"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate rooted file path"):
            ir.validate(self.schema, document)

    def test_layout_quantities_use_exact_canonical_json_integers(self):
        for value in (0, 9007199254740991, "9007199254740992", "18446744073709551615"):
            document = copy.deepcopy(self.fixture)
            document["declarations"][0]["size_bits"] = value
            ir.validate(self.schema, document)
        for value in (9007199254740992, "1", "0", "09007199254740992", -1):
            document = copy.deepcopy(self.fixture)
            document["declarations"][0]["size_bits"] = value
            with self.assertRaises((ValueError, ValidationError)):
                ir.validate(self.schema, document)

    def test_alias_underlying_type_must_match_canonical_target(self):
        document = self.pointer_document()
        alias = copy.deepcopy(document["declarations"][0])
        for key in ("type_id", "complete", "field_ids", "nested_declaration_ids"):
            alias.pop(key)
        alias.update(
            id="decl:alias",
            canonical_declaration_id="decl:alias",
            kind="alias",
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
        ir.validate(self.schema, document)
        alias["underlying_type_id"] = "type:pointer"
        with self.assertRaisesRegex(ValueError, "inconsistent alias target"):
            ir.validate(self.schema, document)

    def test_enumerator_source_references_are_checked(self):
        document = copy.deepcopy(self.fixture)
        source = copy.deepcopy(document["declarations"][0]["source"])
        source["spelling"]["file_id"] = "file:absent"
        document["declarations"][0]["enumerators"] = [
            {
                "name": "Value",
                "signed_value": "1",
                "unsigned_value": "1",
                "source": source,
            }
        ]
        with self.assertRaisesRegex(ValueError, "dangling reference"):
            ir.validate(self.schema, document)

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
        ir.validate(self.schema, self.namespace_document())
        document = self.namespace_document()
        document["declarations"][-1]["declaration_ids"] = []
        with self.assertRaisesRegex(ValueError, "namespace ownership"):
            ir.validate(self.schema, document)
        document = self.namespace_document()
        del document["declarations"][0]["semantic_parent_id"]
        with self.assertRaisesRegex(ValueError, "invalid namespace member"):
            ir.validate(self.schema, document)

    def test_namespace_blocks_and_member_order_are_validated(self):
        document = self.namespace_document()
        document["declarations"][-1]["reopening_sources"][0]["spelling"]["file_id"] = (
            "file:absent"
        )
        with self.assertRaisesRegex(ValueError, "dangling reference"):
            ir.validate(self.schema, document)
        document = self.namespace_document()
        document["declarations"][-1]["reopening_sources"][0]["spelling"]["line"] += 1
        with self.assertRaisesRegex(ValueError, "not its first block"):
            ir.validate(self.schema, document)
        document = self.namespace_document()
        namespace = document["declarations"][-1]
        namespace["declaration_ids"].insert(0, namespace["id"])
        namespace["declaration_ids"].sort(reverse=True)
        with self.assertRaisesRegex(ValueError, "members are not sorted"):
            ir.validate(self.schema, document)

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
        ir.validate(self.schema, document)
        alias["target_namespace_id"] = "decl:sample"
        with self.assertRaisesRegex(ValueError, "invalid namespace alias target"):
            ir.validate(self.schema, document)
        alias["target_namespace_id"] = alias["id"]
        with self.assertRaisesRegex(ValueError, "context/alias cycle"):
            ir.validate(self.schema, document)

    def test_context_cycles_and_wrong_parent_kinds_are_rejected(self):
        for edge in ("semantic_parent_id", "lexical_parent_id"):
            document = self.namespace_document()
            namespace = document["declarations"][-1]
            namespace[edge] = namespace["id"]
            if edge == "semantic_parent_id":
                namespace["declaration_ids"].append(namespace["id"])
                namespace["declaration_ids"].sort()
            with self.assertRaisesRegex(ValueError, "context/alias cycle"):
                ir.validate(self.schema, document)
        document = self.namespace_document()
        document["declarations"][0]["lexical_parent_id"] = "decl:sample.value"
        with self.assertRaisesRegex(ValueError, "invalid declaration context"):
            ir.validate(self.schema, document)

    def test_identity_origin_and_anonymous_naming_are_consistent(self):
        document = self.namespace_document()
        document["declarations"][-1]["identity_kind"] = "source"
        with self.assertRaisesRegex(ValueError, "must inherit source identity"):
            ir.validate(self.schema, document)
        for node in document["declarations"]:
            node["identity_kind"] = "source"
        ir.validate(self.schema, document)
        document["declarations"][-1]["anonymous"] = True
        with self.assertRaisesRegex(ValueError, "inconsistent anonymous naming"):
            ir.validate(self.schema, document)
        document = self.namespace_document()
        namespace = document["declarations"][-1]
        namespace.update(name="", anonymous=True)
        with self.assertRaisesRegex(ValueError, "requires source identity"):
            ir.validate(self.schema, document)
        document = self.namespace_document()
        document["declarations"][0]["usr"] = None
        with self.assertRaisesRegex(ValueError, "no USR"):
            ir.validate(self.schema, document)

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
        ir.validate(self.schema, document)
        document["declarations"][1]["type_id"] = "type:int"
        with self.assertRaisesRegex(ValueError, "must have an unnamed record type"):
            ir.validate(self.schema, document)
        document = self.anonymous_storage_document()
        document["declarations"][-1]["anonymous"] = False
        with self.assertRaisesRegex(ValueError, "must have an unnamed record type"):
            ir.validate(self.schema, document)
        document = self.anonymous_storage_document()
        document["declarations"][0]["nested_declaration_ids"] = []
        with self.assertRaisesRegex(ValueError, "belongs to another context"):
            ir.validate(self.schema, document)
        document = self.anonymous_storage_document()
        document["declarations"][1]["identity_kind"] = "usr"
        with self.assertRaisesRegex(
            ValueError, "anonymous storage requires source identity"
        ):
            ir.validate(self.schema, document)

    def test_nested_declaration_ownership_is_bidirectional(self):
        document = self.anonymous_storage_document()
        document["declarations"][1].update(name="named", anonymous_member=False)
        document["declarations"][0]["nested_declaration_ids"] = []
        with self.assertRaisesRegex(ValueError, "nested declaration ownership"):
            ir.validate(self.schema, document)


if __name__ == "__main__":
    unittest.main()
