"""Integrity checks for independently captured scoped-enum references."""

import contextlib
import io
import json
import unittest
from pathlib import Path

import baseline as b
import legacy

HERE = Path(__file__).with_name("enums")


class EnumReferenceTests(unittest.TestCase):
    def test_fixture_and_manifest_fingerprints_match(self):
        provenance = json.loads((HERE / "reference/provenance.json").read_text())
        self.assertEqual(provenance["capture_status"], "success")
        self.assertEqual(
            b.digest((HERE / "corpus.json").read_bytes()), provenance["manifest_sha256"]
        )
        for case in legacy.load_corpus(HERE / "corpus.json", legacy.ROOT)["cases"]:
            self.assertEqual(
                b.digest((legacy.ROOT / case["header"]).read_bytes()),
                provenance["source_sha256"][case["header"]],
            )
            self.assertEqual(
                provenance["observations"][case["id"]],
                {
                    "cold": "success",
                    "warm": "success",
                    "forced": "success",
                    "cold_warm_equal": True,
                    "cold_forced_equal": False,
                },
            )

    def test_snapshots_sidecars_and_forced_append(self):
        manifest = legacy.load_corpus(HERE / "corpus.json", legacy.ROOT)
        for case in manifest["cases"]:
            snapshots = []
            for label in legacy.PASSES:
                path = HERE / f"reference/{case['id']}/{label}.json"
                with (
                    self.subTest(case=case["id"], label=label),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    self.assertEqual(b.compare(path, path), 0)
                    snapshot = json.loads(path.read_text())
                    self.assertEqual(snapshot["artifact_spec"], manifest["artifacts"])
                    self.assertEqual(snapshot["case"], case["id"])
                    groups = {item["group"] for item in snapshot["artifacts"].values()}
                    self.assertTrue(
                        {
                            item["id"]
                            for item in manifest["artifacts"]
                            if item["required"]
                        }
                        <= groups
                    )
                    snapshots.append((path, snapshot))
            self.assertEqual(snapshots[0][1], snapshots[1][1])
            cold_path, cold = snapshots[0]
            forced_path, forced = snapshots[2]
            self.assertEqual(set(cold["artifacts"]), set(forced["artifacts"]))
            changed = [
                name
                for name, item in cold["artifacts"].items()
                if item != forced["artifacts"][name]
            ]
            self.assertEqual(changed, ["build/classes.resource"])
            name = changed[0]
            self.assertEqual(
                b.artifact_text(forced_path, forced["artifacts"][name]),
                2 * b.artifact_text(cold_path, cold["artifacts"][name]),
            )


if __name__ == "__main__":
    unittest.main()
