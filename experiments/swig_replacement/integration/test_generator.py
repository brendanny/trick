"""Tests for the semantic boundary of the experimental generator."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent

class GeneratorTests(unittest.TestCase):
    def generate(self, source, methods=()):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "model.hh").write_text(source)
        (root / "policy.json").write_text(json.dumps({"version": 1, "records": [
            {"name": "Model", "allocation": "new", "methods": list(methods)}]}))
        output = root / "generated"
        output.mkdir()
        (output / "sentinel").write_text("preserve on failure")
        result = subprocess.run([sys.executable, str(ROOT / "generate.py"), "--header", str(root / "model.hh"),
                                 "--policy", str(root / "policy.json"), "--output", str(output)], capture_output=True, text=True)
        return result, output

    def rejected(self, source, diagnostic, methods=()):
        result, output = self.generate(source, methods)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(diagnostic, result.stderr)
        self.assertEqual([p.name for p in output.iterdir()], ["sentinel"])

    def test_extracts_fields_units_and_overloads(self):
        result, output = self.generate("""struct Model {
double x; /* m position */
double a[3]; /**< trick_units(m/s2) acceleration */
Model(); Model(double value);
double change(double value); int change(int value);
};""", ("change",))
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((output / "declarations.json").read_text())["records"][0]
        self.assertEqual([(f["name"], f["kind"], f["units"]) for f in record["fields"]],
                         [("x", "double", "m"), ("a", "array", "m/s2")])
        self.assertEqual(len(record["constructors"]), 2)
        self.assertEqual({m["arguments"][0]["type"] for m in record["methods"]}, {"double", "int"})

    def test_rejects_pointer_graph(self):
        self.rejected("struct Model { double* p; };", "unsupported field Model.p")

    def test_rejects_inheritance(self):
        self.rejected("struct Base {}; struct Model : Base { double x; };", "inheritance generation")

    def test_rejects_deleted_default_constructor(self):
        self.rejected("struct Model { Model() = delete; Model(double); };", "unsupported selected constructor")

    def test_rejects_missing_selected_method(self):
        self.rejected("struct Model { double x; };", "missing methods", ("missing",))

    def test_rejects_parse_error_before_emission(self):
        self.rejected("struct Model { this is not c++; };", "Clang rejected")

    def test_rejects_bitfield(self):
        self.rejected("struct Model { unsigned int value : 2; };", "unsupported field")

    def test_rejects_multidimensional_array(self):
        self.rejected("struct Model { double value[2][3]; };", "unsupported field")

if __name__ == "__main__":
    unittest.main()
