#!/usr/bin/env python3
"""Compare ordinary enum field metadata through the real MemoryManager."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

import array_metadata as arrays
import baseline as b
import native
import template_enum_metadata as enum_probe

from tools.icg_emit import emit
from tools.icg_policy import resolve

HERE = Path(__file__).with_name("record_enums")


def field(name: str, enum: str, offset: int, dimensions=(), description="") -> dict:
    return dict(
        arrays.field(name, enum, offset, dimensions, description=description),
        enum_type=enum,
    )


# Independent, manually audited layouts, names, annotations and enum label rows.
EXPECTED = {
    "EnumRecord": [
        arrays.field("lead", "int", 0),
        field("state", "RecordState", 4, description="selected state"),
        field("phase", "RecordPhase", 8),
        field("states", "RecordState", 12, (3,)),
        field("phases", "RecordPhase", 24, (2, 2)),
        field("mode", "record_enum::Mode", 40),
        arrays.field("tail", "double", 48, units="m", description="position"),
    ],
    "record_enum::Aliases": [
        field("mode", "record_enum::Mode", 0),
        field("pairs", "RecordPhase", 4, (2, 2)),
        field("repeated", "RecordState", 20),
    ],
}
ENUMS = {
    "RecordState": [
        dict(label="state_negative", value="-3", mods=0),
        dict(label="state_zero", value="0", mods=0),
        dict(label="state_maximum", value="2147483647", mods=0),
    ],
    "RecordPhase": [
        dict(label="phase_idle", value="0", mods=0),
        dict(label="phase_running", value="2", mods=0),
        dict(label="phase_alias", value="2", mods=0),
    ],
    "record_enum::Mode": [
        dict(label="record_enum::mode_zero", value="0", mods=0x40000000),
        dict(label="record_enum::mode_high", value="2147483647", mods=0x40000000),
    ],
}


def reference() -> str:
    return arrays.reference(HERE)[1]


def extract(extractor: Path, output: Path) -> dict:
    return arrays.extract(extractor, output, arrays.reference(HERE)[0])


def generate(facts: dict, output: Path) -> tuple[dict, str]:
    output.mkdir(parents=True, exist_ok=True)
    request = resolve.request_for(facts)
    model = resolve.resolve(facts, request)
    for name, value in (("request", request), ("resolved", model)):
        (output / f"{name}.json").write_bytes(b.json_bytes(value))
    path = output / "candidate.cpp"
    emit.write(facts, request, model, path)
    candidate = path.read_text()
    for source in (reference(), candidate):
        for prefix, names in (("ATTRIBUTES attr", EXPECTED), ("ENUM_ATTR enum", ENUMS)):
            if sorted(re.findall(prefix + r"(\w+)\[\]", source)) != sorted(
                n.replace("::", "__") for n in names
            ):
                raise b.BaselineError("ordinary enum metadata table selection differs")
    return model, candidate


def report_for(facts: dict) -> dict:
    nodes = {n["id"]: n for n in facts["declarations"]}
    records = {n["qualified_name"]: n for n in nodes.values() if n["kind"] == "record"}
    types = {t["id"]: t for t in facts["types"]}
    for name, rows in EXPECTED.items():
        fields = [nodes[i] for i in records[name]["field_ids"]]
        if [n["name"] for n in fields] != [r["name"] for r in rows]:
            raise b.BaselineError("ordinary enum field selection differs")
        for node, row in zip(fields, rows, strict=True):
            base = types[types[node["type_id"]]["canonical_id"]]
            shape = []
            while base["kind"] == "array":
                shape.append(int(base["extent"]))
                base = types[types[base["element_id"]]["canonical_id"]]
            type_name = (
                nodes[base["declaration_id"]]["qualified_name"]
                if base["kind"] == "enum"
                else base["spelling"]
            )
            if (
                base["kind"] != ("enum" if "enum_type" in row else "builtin")
                or type_name != row["type"]
                or any(base["qualifiers"].values())
                or shape != row["dimensions"]
                or int(node["offset_bits"]) != row["offset_bits"]
                or node["bitfield"]
            ):
                raise b.BaselineError("ordinary enum facts differ from audited storage")
    return dict(records=EXPECTED, enums=ENUMS)


def mutations(candidate: str) -> dict[str, tuple[str, str]]:
    registration = "    trick_MM->add_attr_info(std::string(attrEnumRecord[1].type_name), &attrEnumRecord[1], __FILE__, __LINE__);\n"
    changes = {
        "missing-registration": (candidate.replace(registration, "", 1), "run"),
        "premature-size": (
            candidate.replace("15,TRICK_ENUMERATED, 0,", "15,TRICK_ENUMERATED, 4,", 1),
            "run",
        ),
        "wrong-enum-table": (
            candidate.replace('"state", "RecordState"', '"state", "RecordPhase"', 1),
            "run",
        ),
        "unguarded-init": (
            candidate.replace(
                "if (initialized) return;", "if (initialized) initialized = false;", 1
            ),
            "run",
        ),
        "missing-enum-size": (
            candidate.replace(
                "size_t io_src_sizeof_RecordState()",
                "static size_t io_src_sizeof_RecordState()",
                1,
            ),
            "link",
        ),
        "wrong-enum-label": (
            candidate.replace(
                '{"state_negative", -3, 0x0}', '{"wrong_label", -3, 0x0}', 1
            ),
            "compare",
        ),
        "wrong-unsigned-mods": (
            candidate.replace(
                '{"record_enum::mode_zero", 0, 0x40000000}',
                '{"record_enum::mode_zero", 0, 0x0}',
                1,
            ),
            "compare",
        ),
    }
    if any(source == candidate for source, _ in changes.values()):
        raise b.BaselineError("ordinary enum mutation did not change its target")
    return changes


def capture(extractor: Path, root: Path, output: Path, compiler: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").unlink(missing_ok=True)
    facts = extract(extractor, output)
    model, candidate = generate(facts, output / "generated")
    return enum_probe.compare(
        facts,
        model,
        candidate,
        reference(),
        report_for(facts),
        output,
        compiler,
        native.configured_link_flags(root, output),
        case_id="record-enums",
        changes=mutations(candidate),
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
