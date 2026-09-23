#!/usr/bin/env python3
"""Verify pointer identities, target values and checkpoint bytes with legacy."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import array_metadata as arrays
import double_pointer_metadata as metadata
import native
import scalar_runtime


def mutations(candidate, probe):
    changes = [
        (
            "outer-pointer-checkpoint-disabled",
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
    ]
    for label, statement in (
        ("outer-alias-corrupted", "m.alias = &std::get<6>(slots)[0];"),
        ("outer-null-corrupted", "m.pairs[1][0] = &std::get<6>(slots)[0];"),
        ("inner-alias-corrupted", "std::get<6>(slots)[1] = &std::get<6>(targets)[0];"),
        ("inner-null-corrupted", "std::get<6>(slots)[2] = &std::get<6>(targets)[0];"),
        ("terminal-value-corrupted", "std::get<6>(targets)[1] = 0;"),
        ("terminal-string-corrupted", "std::get<1>(slots)[0][0] = 'Z';"),
        (
            "terminal-string-alias-corrupted",
            "std::get<1>(slots)[1] = std::get<1>(slots)[0];",
        ),
    ):
        changes.append((
            label,
            candidate,
            probe.replace(
                "probe::require(restored == 0",
                statement + "\n            probe::require(restored == 0",
                1,
            ),
        ))
    return tuple(changes)


def capture(extractor, root, output, compiler):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").unlink(missing_ok=True)
    report = metadata.capture(extractor, output / "metadata", compiler)
    _, legacy = arrays.reference(metadata.HERE, "double-pointers")
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
        label="double pointer",
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
