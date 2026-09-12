#!/usr/bin/env python3
"""Compare captured legacy and candidate fixed-array metadata with native C++."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import baseline as b
import differential as d
import native

from tools.icg_emit import emit
from tools.icg_policy import resolve

HERE = Path(__file__).with_name("arrays")
REFERENCE = HERE / "reference"


def field(name, kind, offset, dimensions=(), units="1", description="", io=15, mods=0):
    return dict(
        name=name,
        type=kind,
        offset_bits=offset * 8,
        bit_width=None,
        dimensions=list(dimensions),
        legacy_units=units,
        legacy_description=description,
        legacy_io=io,
        legacy_mods=mods,
    )


# Manually specified expectations, independent of policy and emitted source.
EXPECTED = {
    "ArrayModel": [
        field("lead", "int", 0),
        field("vector", "int", 4, (3,), description="vector"),
        field("matrix", "double", 16, (2, 3), "m", "positions"),
        field(
            "cube", "unsigned int", 64, (2, 1, 4), description="counts", io=5, mods=4
        ),
        field("rank8", "int", 96, (1, 2, 1, 2, 1, 2, 1, 2)),
    ],
    "icg_array::Aliases": [
        field("count", "unsigned int", 0),
        field("counts", "unsigned int", 4, (2,)),
        field("rows", "double", 16, (2, 3), "rad", "angles"),
        field("tail", "double", 64),
    ],
}


def reference(here: Path = HERE, case_id: str | None = None) -> tuple[dict, str]:
    reference = here / "reference"
    manifest = json.loads((here / "corpus.json").read_text())
    provenance = json.loads((reference / "provenance.json").read_text())
    if b.digest((here / "corpus.json").read_bytes()) != provenance["manifest_sha256"]:
        raise ValueError("metadata manifest differs from captured input")
    (case,) = [c for c in manifest["cases"] if case_id is None or c["id"] == case_id]
    if (
        b.digest((d.ROOT / case["header"]).read_bytes())
        != provenance["source_sha256"][case["header"]]
    ):
        raise ValueError("metadata fixture differs from captured input")
    path = reference / case["id"] / "cold.json"
    (metadata,) = [
        a
        for a in json.loads(path.read_text())["artifacts"].values()
        if a["group"] == "legacy-metadata"
    ]
    return case, b.artifact_text(path, metadata)


def report_for(facts: dict, expected_records: dict = EXPECTED) -> dict:
    nodes = {n["id"]: n for n in facts["declarations"]}
    types = {t["id"]: t for t in facts["types"]}
    records = {n["qualified_name"]: n for n in nodes.values() if n["kind"] == "record"}
    if set(records) != set(expected_records) or any(
        n["kind"] == "enum" for n in nodes.values()
    ):
        raise ValueError("metadata fixture record/enum selection differs")
    for name, expected in expected_records.items():
        fields = [nodes[i] for i in records[name]["field_ids"]]
        if [f["name"] for f in fields] != [f["name"] for f in expected]:
            raise ValueError("metadata field order/selection differs")
        for node, row in zip(fields, expected, strict=True):
            shape = []
            type_node = types[types[node["type_id"]]["canonical_id"]]
            while type_node["kind"] == "array":
                shape.append(int(type_node["extent"]))
                type_node = types[types[type_node["element_id"]]["canonical_id"]]
            if (
                shape != row["dimensions"]
                or type_node["spelling"] != row["type"]
                or any(type_node["qualifiers"].values())
                or node["bitfield"]
                or int(node["offset_bits"]) != row["offset_bits"]
            ):
                raise ValueError(
                    "metadata facts differ from independent type/shape/layout expectations"
                )
    return dict(records=expected_records, enums={})


def check(
    facts: dict,
    output: Path,
    compiler: Path,
    *,
    here: Path = HERE,
    expected_records: dict = EXPECTED,
    case_id: str | None = None,
) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = output / "comparison.json"
    result.unlink(missing_ok=True)
    case, legacy = reference(here, case_id)
    request = resolve.request_for(facts)
    model = resolve.resolve(facts, request)
    report = report_for(facts, expected_records)
    for name, value in (("facts", facts), ("request", request), ("resolved", model)):
        (output / f"{name}.json").write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n"
        )
    candidate_path = output / "candidate/candidate.cpp"
    emit.write(facts, request, model, candidate_path)
    candidate = candidate_path.read_text()
    for source in (legacy, candidate):
        symbols = re.findall(r"^ATTRIBUTES attr(\w+)\[\]", source, re.M)
        if (
            sorted(symbols) != sorted(n.replace("::", "__") for n in expected_records)
            or "ENUM_ATTR enum" in source
        ):
            raise ValueError("metadata source table selection differs")
    old = native.capture(facts, legacy, report, case, output / "legacy", compiler)
    new = native.capture(
        facts,
        candidate,
        report,
        case,
        candidate_path.parent,
        compiler,
        source_name="candidate.cpp",
    )
    if old["observations"] != new["observations"]:
        raise ValueError("legacy/candidate/native metadata observations differ")
    report.update(
        status="compared",
        legacy=old,
        candidate=new,
        legacy_sha256=b.digest(legacy.encode()),
        candidate_sha256=b.digest(candidate.encode()),
        resolved_digest=model["digest"],
    )
    result.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def capture(
    extractor: Path,
    output: Path,
    compiler: Path,
    *,
    here: Path = HERE,
    expected_records: dict = EXPECTED,
    case_id: str | None = None,
) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").unlink(missing_ok=True)
    case, _ = reference(here, case_id)
    facts = extract(extractor, output, case)
    return check(
        facts,
        output,
        compiler,
        here=here,
        expected_records=expected_records,
        case_id=case_id,
    )


def extract(extractor: Path, output: Path, case: dict) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = output / "S_source.hh"
    source.write_text(f'#include "{d.ROOT / case["header"]}"\n')
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("TRICK_")
        and k not in ("CPATH", "CPLUS_INCLUDE_PATH", "C_INCLUDE_PATH")
    }
    command = [
        str(extractor),
        "--source-root",
        str(d.ROOT),
        "--path-root",
        f"evidence={output}",
        "--select-file",
        str(d.ROOT / case["header"]),
        str(source),
        "--",
    ]
    p = subprocess.run(command, env=env, capture_output=True)
    (output / "extract.command.json").write_text(json.dumps(command, indent=2) + "\n")
    (output / "facts.json").write_bytes(p.stdout)
    (output / "extract.stderr").write_bytes(p.stderr)
    p.check_returncode()
    return json.loads(p.stdout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extractor", type=Path, required=True)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    compiler = shutil.which(args.compiler)
    if not compiler:
        parser.error(f"C++ compiler not found: {args.compiler}")
    capture(args.extractor.resolve(), args.output, Path(compiler).absolute())
