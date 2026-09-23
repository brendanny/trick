#!/usr/bin/env python3
"""Compare audited builtin double-pointer metadata against legacy and native storage."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import array_metadata as arrays
import baseline as b
import native

HERE = Path(__file__).with_name("double_pointers")


def pointer(name, kind, offset, dimensions=(), **kwargs):
    return dict(
        arrays.field(name, kind, offset, (*dimensions, 0, 0), **kwargs),
        pointer=True,
        pointer_depth=2,
    )


# Manually audited LP64 layout and legacy rows; never import generation policy.
EXPECTED = {
    "DoublePointerModel": [
        pointer("enabled", "bool", 0),
        pointer("text", "char", 8),
        pointer("signed_code", "signed char", 16),
        pointer("unsigned_code", "unsigned char", 24),
        pointer("small", "short", 32),
        pointer("unsigned_small", "unsigned short", 40),
        pointer("count", "int", 48),
        pointer("unsigned_count", "unsigned int", 56),
        pointer("large", "long", 64),
        pointer("unsigned_large", "unsigned long", 72),
        pointer("huge", "long long", 80),
        pointer("unsigned_huge", "unsigned long long", 88),
        pointer("gain", "float", 96),
        pointer("position", "double", 104, units="m", description="position target"),
        pointer("code", "char16_t", 112),
        pointer("alias", "int", 120),
        pointer("pairs", "int", 128, (2, 2)),
        arrays.field("tail", "int", 160),
        dict(arrays.field("local", "int", 168, (0,)), pointer=True),
    ]
}


def mutations(candidate):
    return {
        "pointee-size": candidate.replace(
            "sizeof(int), 0, 0,", "sizeof(void*), 0, 0,", 1
        ),
        "pointer-extent": candidate.replace(
            "0, NULL, 2, {{0, 0}", "0, NULL, 2, {{1, 0}", 1
        ),
        "inner-pointer-extent": candidate.replace(
            "0, NULL, 2, {{0, 0}, {0, 0}", "0, NULL, 2, {{0, 0}, {1, 0}", 1
        ),
        "pointer-rank": candidate.replace(
            "0, NULL, 2, {{0, 0}", "0, NULL, 0, {{0, 0}", 1
        ),
        "pointer-offset": candidate.replace("48, NULL, 2,", "56, NULL, 2,", 1),
        "pointee-kind": candidate.replace("TRICK_DOUBLE", "TRICK_FLOAT", 1),
        "pointer-array-shape": candidate.replace(
            "{{2, 0}, {2, 0}, {0, 0}", "{{4, 0}, {1, 0}, {0, 0}", 1
        ),
        "pointer-units": candidate.replace(
            '"DoublePointerModel_position", "m"',
            '"DoublePointerModel_position", "rad"',
            1,
        ),
    }


def capture(extractor: Path, output: Path, compiler: Path) -> dict:
    output = output.resolve()
    report = arrays.capture(
        extractor,
        output,
        compiler,
        here=HERE,
        expected_records=EXPECTED,
        case_id="double-pointers",
    )
    result = output / "comparison.json"
    result.unlink()
    facts = json.loads((output / "facts.json").read_text())
    candidate = (output / "candidate/candidate.cpp").read_text()
    case, _ = arrays.reference(HERE, "double-pointers")
    rejected = {}
    for label, changed in mutations(candidate).items():
        if changed == candidate:
            raise b.BaselineError("pointer mutation missed its target: " + label)
        work = output / "mutations" / label
        try:
            native.capture(facts, changed, report, case, work, compiler)
        except ValueError as error:
            commands = json.loads((work / "commands.json").read_text())
            if any(c["timed_out"] for c in commands) or any(
                c["returncode"] for c in commands[:-1]
            ):
                raise b.BaselineError(
                    "pointer mutation failed before native execution"
                ) from error
            if commands[-1]["stderr"] != "run.stderr" or commands[-1][
                "returncode"
            ] not in (0, 1):
                raise b.BaselineError(
                    "pointer mutation failed at wrong phase"
                ) from error
            if commands[-1]["returncode"] == 0 and "DoublePointerModel::" not in str(
                error
            ):
                raise b.BaselineError(
                    "pointer mutation failed outside field comparison"
                ) from error
            rejected[label] = str(error)
        else:
            raise b.BaselineError("pointer mutation accepted: " + label)
    report["negative_controls"] = rejected
    result.write_bytes(b.json_bytes(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extractor", type=Path, required=True)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    compiler = shutil.which(args.compiler)
    if compiler is None:
        parser.error("C++ compiler not found")
    capture(args.extractor.resolve(), args.output, Path(compiler).absolute())
