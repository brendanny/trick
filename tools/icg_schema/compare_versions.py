#!/usr/bin/env python3
"""Require validated, exact fixture graph equivalence across LLVM 17–23."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import validate as ir
from capture_diagnostics import validate_cases
from jsonschema import SchemaError, ValidationError

VERSIONS = tuple(range(17, 24))
FIXTURES = (
    "record",
    "structured",
    "contexts",
    "enums-bitfields",
    "inheritance",
    "callables",
    "templates",
    "linkage",
)


def compare(schema: dict, lanes: dict[int, Path]) -> dict:
    if set(lanes) != set(VERSIONS):
        raise ValueError("exactly one lane for each LLVM major 17–23 is required")
    report = {}
    for fixture in FIXTURES:
        reference = None
        evidence = {}
        for major in VERSIONS:
            files = sorted(lanes[major].rglob(f"{fixture}.json"))
            if len(files) != 1:
                raise ValueError(
                    f"LLVM {major} / {fixture}: expected one facts file, found {len(files)}"
                )
            document = json.loads(files[0].read_text(encoding="utf-8"))
            try:
                ir.validate(schema, document)
            except (ValueError, ValidationError) as error:
                raise ValueError(f"LLVM {major} / {fixture}: {error}") from error
            provenance = document["provenance"]
            version = provenance["frontend_version"]
            match = re.search(r"\bclang version (\d+)\.", version)
            if not match or int(match[1]) != major:
                raise ValueError(
                    f"LLVM {major} / {fixture}: wrong frontend {version!r}"
                )
            observed = {
                "target_triple": provenance["target_triple"],
                "language_standard": provenance["language_standard"],
                "graph_digest": provenance["graph_digest"],
            }
            if reference is None:
                reference = observed
            elif observed != reference:
                raise ValueError(
                    f"LLVM {major} / {fixture}: differs from LLVM 17; "
                    f"expected {reference}, got {observed}. "
                    "Inspect the full facts artifacts; no display or semantic facts are omitted."
                )
            evidence[str(major)] = {"frontend_version": version, **observed}
        report[fixture] = evidence
    reference = None
    evidence = {}
    for major in VERSIONS:
        files = sorted(lanes[major].rglob("diagnostic-cases.json"))
        if len(files) != 1:
            raise ValueError(f"LLVM {major}: expected one diagnostic-cases.json")
        captured = json.loads(files[0].read_text(encoding="utf-8"))
        if (
            captured["schema_version"] != 1
            or captured["frontend_version"]
            != report["record"][str(major)]["frontend_version"]
        ):
            raise ValueError(f"LLVM {major}: diagnostic frontend/version mismatch")
        validate_cases(captured["cases"])
        if reference is None:
            reference = captured["cases"]
        elif captured["cases"] != reference:
            raise ValueError(
                f"LLVM {major}: diagnostic/failure behavior differs from LLVM 17"
            )
        evidence[str(major)] = captured
    report["diagnostics"] = evidence
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--lane", action="append", required=True, metavar="MAJOR=DIR")
    args = parser.parse_args()
    try:
        lanes = {}
        for lane in args.lane:
            number, separator, directory = lane.partition("=")
            major = int(number)
            if not separator or not directory or major in lanes:
                raise ValueError(f"invalid or duplicate lane: {lane!r}")
            lanes[major] = Path(directory)
        report = compare(json.loads(args.schema.read_text(encoding="utf-8")), lanes)
    except (OSError, ValueError, SchemaError) as error:
        print(f"ICG version comparison failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
