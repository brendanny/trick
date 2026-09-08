#!/usr/bin/env python3
"""Capture independently failing constructs and a successful warning on the real extractor."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import validate as ir

# Separate TUs isolate rejection contracts; failed-parent-identity deliberately
# combines an earlier rejection with later template dependencies.
CASES = {
    "static-member": (
        b"struct A { static int value; };",
        1,
        ["ICG_UNSUPPORTED_DECLARATION"],
    ),
    "failed-parent-identity": (
        b"template<class T> struct A { using ref = int&; };\n"
        b"struct Broken { static int bad; };\n"
        b"using Int = A<int>::ref; using Char = A<char>::ref;\n",
        1,
        ["ICG_UNSUPPORTED_DECLARATION"],
    ),
    "friend-definition": (
        b"struct A { friend void f() {} };",
        1,
        ["ICG_UNSUPPORTED_DECLARATION"],
    ),
    "member-template": (
        b"struct A { template<class T> void f(T); };",
        1,
        ["ICG_UNSUPPORTED_DECLARATION"],
    ),
    "variable-template": (
        b"template<class T> int value = 0;",
        1,
        ["ICG_UNSUPPORTED_DECLARATION"],
    ),
    "alias-template": (
        b"template<class T> using Alias = T;",
        1,
        ["ICG_UNSUPPORTED_DECLARATION"],
    ),
    "invalid-encoding": (b"/* caf\xe9 */\nstruct A {};", 1, ["ICG_INVALID_ENCODING"]),
    "unattached-encoding": (
        b"// caf\xe9\n#pragma once\nstruct A {};",
        1,
        ["ICG_INVALID_ENCODING"],
    ),
    "selection-file": (b"struct A {};", 2, ["ICG_SELECTION_FILE"]),
    "parse-error": (b"struct A : Missing {};", 1, []),
    "paired-argument": (b"struct A {};", 2, ["ICG_ARGUMENT_VALUE"]),
    "warning": (b"#warning icg-warning\nstruct A {};", 0, []),
}
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "trick_source/codegen/TrickCodeGen/ir/extracted-facts.schema.json"


def validate_cases(cases: dict) -> None:
    if set(cases) != set(CASES):
        raise ValueError("missing or unexpected diagnostic cases")
    for name, (source, exit_code, codes) in CASES.items():
        case = cases[name]
        if (
            case["source_sha256"] != hashlib.sha256(source).hexdigest()
            or case["returncode"] != exit_code
            or case["stdout_empty"] != (exit_code != 0)
            or case["icg_codes"] != codes
        ):
            raise ValueError(f"{name}: changed fail-closed behavior or ICG diagnostics")
        expected = (
            [["error", 1]]
            if name == "parse-error"
            else [["warning", 1]]
            if name == "warning"
            else []
        )
        if case["clang_severities"] != expected:
            raise ValueError(f"{name}: changed Clang diagnostic severities/counts")


def capture(extractor: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    schema = json.loads(SCHEMA.read_text())
    report = {"schema_version": 1, "cases": {}}
    with tempfile.TemporaryDirectory() as directory:
        for name, (source, _, _) in CASES.items():
            header = Path(directory) / f"{name}.hh"
            header.write_bytes(source)
            result = subprocess.run(
                [
                    str(extractor),
                    "--diagnostics-format=json",
                    "--source-root",
                    directory,
                    *(
                        ["--select-file", str(header.parent / "absent.hh")]
                        if name == "selection-file"
                        else []
                    ),
                    str(header),
                    "--",
                    *(["-I", "-DSECRET=1"] if name == "paired-argument" else []),
                ],
                capture_output=True,
                check=False,
            )
            (output / f"{name}.stdout").write_bytes(result.stdout)
            (output / f"{name}.diagnostics.json").write_bytes(result.stderr)
            envelope = json.loads(result.stderr)
            if (
                envelope["document_kind"] != "trick.icg.diagnostics"
                or envelope["schema_version"] != 3
            ):
                raise ValueError(f"{name}: invalid diagnostics envelope")
            diagnostics = envelope["diagnostics"]
            for item in diagnostics:
                ir.Draft202012Validator({
                    "$defs": schema["$defs"],
                    "$ref": "#/$defs/diagnostic",
                }).validate(item)
                if not item["code"].startswith(("ICG_", "CLANG_")):
                    raise ValueError(f"{name}: unclassified diagnostic")
                if item["code"].startswith("ICG_") and item["severity"] != "error":
                    raise ValueError(
                        f"{name}: unsupported construct lost its error severity"
                    )
            if name == "warning":
                document = json.loads(result.stdout)
                ir.validate(schema, document)
                report["frontend_version"] = document["provenance"]["frontend_version"]
                if diagnostics != document["diagnostics"]:
                    raise ValueError("warning facts and stderr disagree")
            report["cases"][name] = {
                "source_sha256": hashlib.sha256(source).hexdigest(),
                "returncode": result.returncode,
                "stdout_empty": result.stdout == b"",
                "icg_codes": sorted({
                    d["code"] for d in diagnostics if d["code"].startswith("ICG_")
                }),
                "clang_severities": sorted(
                    [level, count]
                    for level, count in Counter(
                        d["severity"]
                        for d in diagnostics
                        if d["code"].startswith("CLANG_")
                    ).items()
                ),
            }
    validate_cases(report["cases"])
    (output / "diagnostic-cases.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extractor", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    capture(args.extractor.resolve(strict=True), args.output)
