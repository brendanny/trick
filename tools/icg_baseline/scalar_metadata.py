#!/usr/bin/env python3
"""Compare captured bool/char/float/long metadata with candidate and native C++."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import array_metadata as arrays

HERE = Path(__file__).with_name("scalars")

# Manually audited LP64 layout, independent of generation policy and native probes.
EXPECTED = {
    "ScalarModel": [
        arrays.field("enabled", "bool", 0, description="enabled"),
        arrays.field("code", "char", 1, description="code"),
        arrays.field("gain", "float", 4, units="m", description="gain"),
        arrays.field("counter", "long", 8, description="counter"),
        arrays.field("flags", "bool", 16, (2, 3), description="flags"),
        arrays.field("samples", "float", 24, (3,), "m", "samples"),
        arrays.field("label", "char", 36, (8,), description="label"),
        arrays.field("limits", "long", 48, (2,), description="limits"),
    ],
    "icg_scalar::Aliases": [
        arrays.field("flag", "bool", 0),
        arrays.field("code", "char", 1),
        arrays.field("gain", "float", 4),
        arrays.field("counter", "long", 8),
        arrays.field("counts", "long", 16, (2,)),
    ],
}


def capture(
    extractor: Path,
    output: Path,
    compiler: Path,
) -> dict:
    return arrays.capture(
        extractor,
        output,
        compiler,
        here=HERE,
        expected_records=EXPECTED,
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
