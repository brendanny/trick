#!/usr/bin/env python3
"""Compare captured integer width/signedness metadata with candidate and native C++."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import array_metadata as arrays

HERE = Path(__file__).with_name("integers")

# Manually audited LP64 layout and legacy annotations, independent of generation.
EXPECTED = {
    "IntegerModel": [
        arrays.field("signed_code", "signed char", 0, description="signed code"),
        arrays.field("byte", "unsigned char", 1, description="byte"),
        arrays.field("small", "short", 2, units="m", description="small"),
        arrays.field("small_count", "unsigned short", 4, description="small count"),
        arrays.field("count", "unsigned long", 8, description="count"),
        arrays.field("wide", "long long", 16, units="m", description="wide"),
        arrays.field("wide_count", "unsigned long long", 24, description="wide count"),
        arrays.field("signed_codes", "signed char", 32, (2,)),
        arrays.field("bytes", "unsigned char", 34, (3,)),
        arrays.field("smalls", "short", 38, (2, 3)),
        arrays.field("small_counts", "unsigned short", 50, (2,)),
        arrays.field("counts", "unsigned long", 56, (2,)),
        arrays.field("wides", "long long", 72, (2,)),
        arrays.field("wide_counts", "unsigned long long", 88, (2,)),
    ],
    "icg_integer::Aliases": [
        arrays.field("signed_code", "signed char", 0),
        arrays.field("byte", "unsigned char", 1),
        arrays.field("small", "short", 2),
        arrays.field("small_count", "unsigned short", 4),
        arrays.field("count", "unsigned long", 8),
        arrays.field("wide", "long long", 16),
        arrays.field("wide_count", "unsigned long long", 24),
        arrays.field("wide_counts", "unsigned long long", 32, (2,)),
    ],
}


def capture(extractor: Path, output: Path, compiler: Path) -> dict:
    return arrays.capture(
        extractor, output, compiler, here=HERE, expected_records=EXPECTED
    )


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
