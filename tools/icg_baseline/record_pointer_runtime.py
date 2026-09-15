#!/usr/bin/env python3
"""Round-trip record pointer addresses and symbolic target values against legacy."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

import native
import record_pointer_metadata as records
import scalar_runtime


def mutations(candidate, probe):
    changes = []
    for label, field in (
        ("pointer-checkpoint-disabled", "head"),
        ("pointer-array-checkpoint-disabled", "nodes"),
    ):
        changes.append((
            label,
            re.sub(
                rf'("{field}", "record_pointer::Node",[^}}]*?\n  )15,TRICK_STRUCTURED',
                r"\g<1>3,TRICK_STRUCTURED",
                candidate,
                count=1,
            ),
            probe,
        ))
    changes.append((
        "target-checkpoint-disabled",
        re.sub(
            r"(ATTRIBUTES attrrecord_pointer__Node\[\] = \{[^}]*?\n  )15,TRICK_INTEGER",
            r"\g<1>3,TRICK_INTEGER",
            candidate,
            count=1,
        ),
        probe,
    ))
    changes.append((
        "restore-omitted",
        candidate,
        probe.replace("mm.read_checkpoint_from_string(checkpoint.str().c_str())", "0"),
    ))
    for label, statement in (
        ("alias-restore-corrupted", "model.alias=&nodes[0];"),
        ("null-restore-corrupted", "model.nodes[1]=&nodes[0];"),
        ("self-cycle-corrupted", "nodes[0].next=&nodes[1];"),
        ("mutual-cycle-corrupted", "peers[0].owner=&nodes[1];"),
    ):
        changes.append((
            label,
            candidate,
            probe.replace("bool matches", statement + "\n            bool matches", 1),
        ))
    return tuple(changes)


def capture(extractor, root, output, compiler):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").unlink(missing_ok=True)
    metadata = records.capture(extractor, root, output / "metadata", compiler)
    candidate = (output / "metadata/generated/candidate.cpp").read_text()
    return scalar_runtime.compare(
        records.reference(),
        candidate,
        (records.HERE / "runtime.cpp").read_text(),
        output,
        compiler,
        native.configured_link_flags(root, output),
        metadata=metadata,
        expected_records=records.EXPECTED,
        mutations=mutations,
        label="record pointer",
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
