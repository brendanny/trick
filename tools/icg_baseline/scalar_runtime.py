#!/usr/bin/env python3
"""Exercise emitted scalar metadata through the configured real MemoryManager."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import array_metadata
import baseline as b
import native
import scalar_metadata


def execute(
    source: str, probe: str, output: Path, compiler: Path, flags: tuple
) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    (output / "metadata.cpp").write_text(
        source.replace("${TRICK_ROOT}", str(native.ROOT))
    )
    (output / "probe.cpp").write_text(probe)
    (output / "native_probe.hh").write_bytes(native.HELPER.read_bytes())
    return native.execute(
        [
            output / "probe.cpp",
            native.ROOT / "trick_source/sim_services/UnitsMap/UnitsMap.cpp",
        ],
        output,
        compiler,
        link_flags=flags,
    )


def scalar_mutations(candidate: str, probe: str) -> tuple:
    return (
        ("long-truncation", candidate.replace("TRICK_LONG", "TRICK_INTEGER"), probe),
        (
            "boolean-checkpoint-disabled",
            candidate.replace("15,TRICK_BOOLEAN", "3,TRICK_BOOLEAN", 1),
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


def capture(
    extractor: Path,
    root: Path,
    output: Path,
    compiler: Path,
    *,
    here: Path = scalar_metadata.HERE,
    expected_records: dict = scalar_metadata.EXPECTED,
    mutations=scalar_mutations,
    label: str = "scalar",
) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = output / "comparison.json"
    result.unlink(missing_ok=True)
    metadata = array_metadata.capture(
        extractor,
        output / "metadata",
        compiler,
        here=here,
        expected_records=expected_records,
    )
    _, legacy = array_metadata.reference(here)
    candidate = (output / "metadata/candidate/candidate.cpp").read_text()
    probe = (here / "runtime.cpp").read_text()
    flags = native.configured_link_flags(root, output)
    old = execute(legacy, probe, output / "legacy", compiler, flags)
    new = execute(candidate, probe, output / "candidate", compiler, flags)
    if old["observations"] != new["observations"]:
        raise b.BaselineError("scalar legacy/candidate runtime observations differ")
    rounds = new["observations"].get("round_trips", [])
    fields = sum(len(rows) for rows in expected_records.values())
    if len(rounds) != 2 or any(len(row) != fields for row in rounds):
        raise b.BaselineError("scalar runtime observations are incomplete")
    checkpoints = {}
    for index in range(2):
        name = f"checkpoint-{index}.txt"
        previous = (output / "legacy" / name).read_bytes()
        current = (output / "candidate" / name).read_bytes()
        if not current or previous != current:
            raise b.BaselineError("scalar legacy/candidate checkpoints differ")
        checkpoints[name] = b.digest(current)
    rejected = {}
    for mutation, source, runtime in mutations(candidate, probe):
        if source == candidate and runtime == probe:
            raise b.BaselineError("scalar runtime mutation did not change its target")
        work = output / "mutations" / mutation
        try:
            execute(source, runtime, work, compiler, flags)
        except ValueError as error:
            last = json.loads((work / "commands.json").read_text())[-1]
            if (
                last["timed_out"]
                or last["returncode"] != 1
                or last["stderr"] != "run.stderr"
                or f"{label} checkpoint values did not round trip"
                not in (work / "run.stderr").read_text()
            ):
                raise b.BaselineError(
                    "scalar mutation failed at the wrong phase: " + mutation
                ) from error
            rejected[mutation] = str(error)
        else:
            raise b.BaselineError("scalar runtime mutation was accepted: " + mutation)
    report = dict(
        status="compared",
        records=len(expected_records),
        fields=fields,
        round_trips=2,
        metadata=metadata,
        legacy=old,
        candidate=new,
        checkpoint_sha256=checkpoints,
        mutations_rejected=rejected,
    )
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
