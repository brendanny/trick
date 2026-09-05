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
            lambda value: value.update(schema_version=2),
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


if __name__ == "__main__":
    unittest.main()
