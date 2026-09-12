#!/usr/bin/env python3
"""Exercise integer metadata through real MemoryManager checkpoint boundaries."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import integer_metadata
import native
import scalar_runtime


def mutations(candidate: str, probe: str) -> tuple:
    return (
        (
            "short-truncation",
            candidate.replace("TRICK_SHORT", "TRICK_CHARACTER", 1),
            probe,
        ),
        (
            "unsigned-long-truncation",
            candidate.replace("TRICK_UNSIGNED_LONG,", "TRICK_UNSIGNED_INTEGER,", 1),
            probe,
        ),
        (
            "long-long-truncation",
            candidate.replace("TRICK_LONG_LONG,", "TRICK_INTEGER,", 1),
            probe,
        ),
        (
            "unsigned-long-long-truncation",
            candidate.replace(
                "TRICK_UNSIGNED_LONG_LONG,", "TRICK_UNSIGNED_INTEGER,", 1
            ),
            probe,
        ),
        (
            "unsigned-checkpoint-disabled",
            candidate.replace(
                "15,TRICK_UNSIGNED_CHARACTER", "3,TRICK_UNSIGNED_CHARACTER", 1
            ),
            probe,
        ),
        (
            "restore-omitted",
            candidate,
            probe.replace(
                "mm.read_checkpoint_from_string(checkpoint.str().c_str())", "0"
            ),
        ),
    )


def capture(extractor: Path, root: Path, output: Path, compiler: Path) -> dict:
    return scalar_runtime.capture(
        extractor,
        root,
        output,
        compiler,
        here=integer_metadata.HERE,
        expected_records=integer_metadata.EXPECTED,
        mutations=mutations,
        label="integer",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extractor", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=native.ROOT)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    compiler = shutil.which(args.compiler)
    if compiler is None:
        parser.error("C++ compiler not found")
    capture(
        args.extractor.resolve(),
        args.root.resolve(),
        args.output,
        Path(compiler).absolute(),
    )
