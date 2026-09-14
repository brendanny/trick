#!/usr/bin/env python3
"""Round-trip enum pointer addresses and symbolic target values against legacy."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

import enum_pointer_metadata as enums
import native
import scalar_runtime


def mutations(candidate, probe):
    return (
        (
            "enum-size-truncation",
            candidate.replace(
                "return sizeof(::PointerState);", "return sizeof(short);", 1
            ),
            probe,
        ),
        (
            "pointer-checkpoint-disabled",
            re.sub(
                r'("state", "PointerState",[^}]*?\n  )15,TRICK_ENUMERATED',
                r"\g<1>3,TRICK_ENUMERATED",
                candidate,
                count=1,
            ),
            probe,
        ),
        (
            "pointer-array-checkpoint-disabled",
            re.sub(
                r'("states", "PointerState",[^}]*?\n  )15,TRICK_ENUMERATED',
                r"\g<1>3,TRICK_ENUMERATED",
                candidate,
                count=1,
            ),
            probe,
        ),
        (
            "target-checkpoint-disabled",
            re.sub(
                r"(ATTRIBUTES attrenum_pointer__Targets\[\] = \{[^}]*?\n  )15,TRICK_ENUMERATED",
                r"\g<1>3,TRICK_ENUMERATED",
                candidate,
                count=1,
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
                "model.alias = &targets.states[0];\n            probe::require(restored == 0",
                1,
            ),
        ),
        (
            "null-restore-corrupted",
            candidate,
            probe.replace(
                "probe::require(restored == 0",
                "model.states[1] = &model.local;\n            probe::require(restored == 0",
                1,
            ),
        ),
    )


def capture(extractor, root, output, compiler):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").unlink(missing_ok=True)
    metadata = enums.capture(extractor, root, output / "metadata", compiler)
    candidate = (output / "metadata/generated/candidate.cpp").read_text()
    return scalar_runtime.compare(
        enums.reference(),
        candidate,
        (enums.HERE / "runtime.cpp").read_text(),
        output,
        compiler,
        native.configured_link_flags(root, output),
        metadata=metadata,
        expected_records=enums.EXPECTED,
        mutations=mutations,
        label="enum pointer",
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
