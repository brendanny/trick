#!/usr/bin/env python3
"""Verify pointer identities, target values and checkpoint bytes with legacy."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import array_metadata as arrays
import native
import pointer_metadata as metadata
import scalar_runtime


def mutations(candidate, probe):
    return (
        (
            "pointer-checkpoint-disabled",
            candidate.replace("15,TRICK_INTEGER", "3,TRICK_INTEGER", 1),
            probe,
        ),
        (
            "pointer-array-checkpoint-disabled",
            candidate.replace(
                '"pairs", "int", "1", "", "",\n  "",\n  15,',
                '"pairs", "int", "1", "", "",\n  "",\n  3,',
                1,
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
        (
            "alias-restore-corrupted",
            candidate,
            probe.replace(
                "probe::require(restored == 0",
                "m.alias = &std::get<6>(targets)[0];\n            probe::require(restored == 0",
                1,
            ),
        ),
        (
            "null-restore-corrupted",
            candidate,
            probe.replace(
                "probe::require(restored == 0",
                "m.pairs[1][0] = &m.tail;\n            probe::require(restored == 0",
                1,
            ),
        ),
    )


def capture(extractor, root, output, compiler):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").unlink(missing_ok=True)
    report = metadata.capture(extractor, output / "metadata", compiler)
    _, legacy = arrays.reference(metadata.HERE, "pointers")
    candidate = (output / "metadata/candidate/candidate.cpp").read_text()
    return scalar_runtime.compare(
        legacy,
        candidate,
        (metadata.HERE / "runtime.cpp").read_text(),
        output,
        compiler,
        native.configured_link_flags(root, output),
        metadata=report,
        expected_records=metadata.EXPECTED,
        mutations=mutations,
        label="pointer",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extractor", type=Path, required=True)
    parser.add_argument("--trick-root", type=Path, default=native.ROOT)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    compiler = shutil.which(args.compiler)
    if compiler is None:
        parser.error("C++ compiler not found")
    capture(
        args.extractor.resolve(),
        args.trick_root.resolve(),
        args.output,
        Path(compiler).absolute(),
    )
