import json
import tempfile
import unittest
from pathlib import Path

import compare_versions as comparison
import validate as ir

ROOT = Path(__file__).resolve().parents[2]
IR = ROOT / "trick_source/codegen/TrickCodeGen/ir"


class CompareVersionsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.lanes = {}
        self.schema = json.loads((IR / "extracted-facts.schema.json").read_text())
        fixture = json.loads((IR / "fixtures/minimal-record.json").read_text())
        for major in comparison.VERSIONS:
            directory = Path(self.temporary.name) / str(major)
            directory.mkdir()
            self.lanes[major] = directory
            fixture["provenance"]["frontend_version"] = f"clang version {major}.0.0"
            # Provenance may differ; it is not a cross-version parse cache key.
            fixture["provenance"]["working_directory"] = f"/build/{major}"
            for name in comparison.FIXTURES:
                (directory / f"{name}.json").write_text(json.dumps(fixture))

    def mutate(self, change, *, refresh=True):
        path = self.lanes[23] / "record.json"
        document = json.loads(path.read_text())
        change(document)
        if refresh:
            document["provenance"]["graph_digest"] = ir.graph_digest(document)
        path.write_text(json.dumps(document))

    def test_complete_valid_matrix_passes(self):
        report = comparison.compare(self.schema, self.lanes)
        self.assertEqual(set(report), set(comparison.FIXTURES))
        self.assertEqual(set(report["record"]), {str(v) for v in comparison.VERSIONS})

    def test_missing_version_fails(self):
        del self.lanes[22]
        with self.assertRaisesRegex(ValueError, "each LLVM major"):
            comparison.compare(self.schema, self.lanes)

    def test_missing_or_duplicate_fixture_fails(self):
        path = self.lanes[23] / "record.json"
        copy = path.read_text()
        path.unlink()
        with self.assertRaisesRegex(ValueError, "found 0"):
            comparison.compare(self.schema, self.lanes)
        path.write_text(copy)
        nested = path.parent / "duplicate"
        nested.mkdir()
        (nested / path.name).write_text(copy)
        with self.assertRaisesRegex(ValueError, "found 2"):
            comparison.compare(self.schema, self.lanes)

    def test_mislabeled_version_fails(self):
        self.mutate(
            lambda d: d["provenance"].update(frontend_version="clang version 17.0.6")
        )
        with self.assertRaisesRegex(ValueError, "wrong frontend"):
            comparison.compare(self.schema, self.lanes)

    def test_different_target_fails_even_with_equal_graph(self):
        self.mutate(
            lambda d: d["provenance"].update(target_triple="aarch64-apple-darwin")
        )
        with self.assertRaisesRegex(ValueError, "differs from LLVM 17"):
            comparison.compare(self.schema, self.lanes)

    def test_stale_digest_is_rejected(self):
        self.mutate(lambda d: d["types"][0].update(spelling="changed"), refresh=False)
        with self.assertRaisesRegex(ValueError, "graph_digest does not match"):
            comparison.compare(self.schema, self.lanes)

    def test_display_change_with_fresh_digest_is_not_normalized_away(self):
        self.mutate(lambda d: d["types"][0].update(spelling="changed"))
        with self.assertRaisesRegex(ValueError, "differs from LLVM 17"):
            comparison.compare(self.schema, self.lanes)

    def test_layout_change_with_fresh_digest_is_not_normalized_away(self):
        self.mutate(lambda d: d["declarations"][0].update(size_bits=128))
        with self.assertRaisesRegex(ValueError, "differs from LLVM 17"):
            comparison.compare(self.schema, self.lanes)

    def test_invalid_graph_cannot_pass_using_reference_digest(self):
        self.mutate(
            lambda d: d["declarations"][1].update(type_id="type:missing"), refresh=False
        )
        with self.assertRaisesRegex(ValueError, "unknown|missing"):
            comparison.compare(self.schema, self.lanes)


if __name__ == "__main__":
    unittest.main()
