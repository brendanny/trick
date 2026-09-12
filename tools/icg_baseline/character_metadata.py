#!/usr/bin/env python3
"""Compare UTF-16 storage and characterize rejected wide/UTF-32 legacy metadata."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import array_metadata as arrays
import baseline as b
import native

from tools.icg_policy import resolve, rules

HERE = Path(__file__).with_name("characters")

# Independently audited field selection, spelling, shape, and LP64 layout.
EXPECTED = {
    "Utf16Model": [
        arrays.field("code", "char16_t", 0, description="code unit"),
        arrays.field("text", "char16_t", 2, (6,), description="code units"),
        arrays.field("grid", "char16_t", 14, (2, 3)),
        arrays.field("maximum", "char16_t", 26),
    ],
    "icg_utf16::Aliases": [
        arrays.field("code", "char16_t", 0),
        arrays.field("text", "char16_t", 2, (4,)),
        arrays.field("tail", "char16_t", 10),
    ],
}
REJECTED = {
    "wide": {
        "WideModel": [
            arrays.field("code", "wchar_t", 0),
            arrays.field("text", "wchar_t", 4, (2,)),
        ]
    },
    "utf32": {
        "Utf32Model": [
            arrays.field("code", "char32_t", 0),
            arrays.field("text", "char32_t", 4, (2,)),
        ]
    },
}


def rejections(extractor: Path, output: Path, compiler: Path) -> dict:
    observations = {}
    for case_id, expected in REJECTED.items():
        work = output / case_id
        work.mkdir(parents=True, exist_ok=True)
        result = work / "rejection.json"
        result.unlink(missing_ok=True)
        case, legacy = arrays.reference(HERE, case_id)
        facts = arrays.extract(extractor, work, case)
        # Check every extracted field even when legacy omits its metadata.
        report = arrays.report_for(facts, expected)
        request = resolve.request_for(facts)
        try:
            resolve.resolve(facts, request)
        except rules.PolicyError as error:
            if error.code != "ICG_POLICY_TYPE":
                raise
            diagnostic = dict(code=error.code, message=error.message)
        else:
            raise b.BaselineError(f"{case_id}: unsupported character type admitted")
        if case_id == "utf32":
            report = dict(records={"Utf32Model": []}, enums={})
        compiled = native.capture(
            facts, legacy, report, case, work / "legacy", compiler
        )
        observation = dict(
            status="rejected",
            diagnostic=diagnostic,
            extracted_fields=2,
            legacy_fields=0 if case_id == "utf32" else 2,
            legacy=compiled,
        )
        result.write_bytes(b.json_bytes(observation))
        observations[case_id] = observation
    return observations


def capture(extractor: Path, output: Path, compiler: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = output / "comparison.json"
    result.unlink(missing_ok=True)
    positive = arrays.capture(
        extractor,
        output / "utf16",
        compiler,
        here=HERE,
        expected_records=EXPECTED,
        case_id="utf16",
    )
    report = dict(
        status="compared",
        utf16=positive,
        rejected=rejections(extractor, output / "rejected", compiler),
    )
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
