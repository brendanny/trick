#!/usr/bin/env python3
"""Round-trip generated enum template fields through the real MemoryManager."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import native
import scalar_runtime
import template_enum_metadata as enums


def mutations(candidate: str, probe: str) -> tuple:
    return (
        (
            "enum-size-truncation",
            candidate.replace(
                "return sizeof(::EnumState);", "return sizeof(short);", 1
            ),
            probe,
        ),
        (
            "checkpoint-disabled",
            candidate.replace("15,TRICK_ENUMERATED", "3,TRICK_ENUMERATED", 1),
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
        label="template enum",
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
