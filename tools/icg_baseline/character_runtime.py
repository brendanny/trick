#!/usr/bin/env python3
"""Check UTF-16 readback and rejected character profiles in real MemoryManager."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import array_metadata
import baseline as b
import character_metadata as characters
import native
import scalar_runtime


def mutations(candidate: str, probe: str) -> tuple:
    return (
        (
            "code-unit-truncation",
            candidate.replace("TRICK_UNSIGNED_SHORT", "TRICK_UNSIGNED_CHARACTER", 1),
            probe,
        ),
        (
            "checkpoint-disabled",
            candidate.replace("15,TRICK_UNSIGNED_SHORT", "3,TRICK_UNSIGNED_SHORT", 1),
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
    result = output / "comparison.json"
    result.unlink(missing_ok=True)
    utf16 = scalar_runtime.capture(
        extractor,
        root,
        output / "utf16",
        compiler,
        here=characters.HERE,
        expected_records=characters.EXPECTED,
        case_id="utf16",
        mutations=mutations,
        label="UTF-16",
    )
    rejected = characters.rejections(extractor, output / "rejected", compiler)
    flags = native.configured_link_flags(root, output)
    probe = (characters.HERE / "rejection.cpp").read_text()
    # These expectations come from actual legacy execution, never generation policy.
    expected = {
        "wide": dict(
            input=20013, stored=45, code_kind="TRICK_WCHAR", bare_character=True
        ),
        "utf32": dict(
            rows=0, checkpoint_has_field=False, code=0x1F600, text=[65, 0x10FFFF]
        ),
    }
    for case_id, observation in expected.items():
        _, legacy = array_metadata.reference(characters.HERE, case_id)
        source = ("#define PROBE_WIDE\n" if case_id == "wide" else "") + probe
        runtime = scalar_runtime.execute(
            legacy, source, output / "rejected" / case_id / "runtime", compiler, flags
        )
        if runtime["observations"] != observation:
            raise b.BaselineError(f"{case_id}: legacy runtime limitation changed")
        rejected[case_id]["runtime"] = runtime
    report = dict(status="compared", utf16=utf16, rejected=rejected)
    result.write_bytes(b.json_bytes(report))
    return report


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
