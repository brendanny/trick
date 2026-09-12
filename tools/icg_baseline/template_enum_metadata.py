#!/usr/bin/env python3
"""Compare enum template tables and dependencies using the real MemoryManager."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import array_metadata as arrays
import baseline as b
import native
import template_metadata as templates

from tools.icg_emit import emit
from tools.icg_policy import resolve

HERE = Path(__file__).with_name("template_enums")
BINDINGS = {
    "EnumBox<EnumBox<EnumState>>": dict(
        symbol="EnumConsumers_nested_EnumBox_EnumBox_enum_EnumState___",
        cpp_type="EnumBox<EnumBox<enum EnumState> >",
        units_prefix="EnumBox<EnumBox<enum EnumState> >",
        field="EnumConsumers::nested",
    ),
    "EnumBox<EnumState>": dict(
        symbol="EnumConsumers_plain_EnumBox_enum_EnumState_",
        cpp_type="EnumBox<enum EnumState>",
        units_prefix="EnumBox<enum EnumState>",
        field="EnumConsumers::repeated",
    ),
    "EnumBox<EnumPhase>": dict(
        symbol="EnumConsumers_scoped_EnumBox_enum_EnumPhase_",
        cpp_type="EnumBox<enum EnumPhase>",
        units_prefix="EnumBox<enum EnumPhase>",
        field="EnumConsumers::scoped",
    ),
    "EnumBox<enum_fixture::Mode>": dict(
        symbol="EnumConsumers_namespaced_EnumBox_enum_enum_fixture__Mode_",
        cpp_type="EnumBox<enum enum_fixture::Mode>",
        units_prefix="EnumBox<enum enum_fixture::Mode>",
        field="EnumConsumers::namespaced",
    ),
    "EnumBox<EnumPhase[2]>": dict(
        symbol="EnumConsumers_array_argument_EnumBox_enum_EnumPhase_2__",
        cpp_type="EnumBox<enum EnumPhase[2]>",
        units_prefix="EnumBox<enum EnumPhase[2]>",
        field="EnumConsumers::array_argument",
    ),
}


def field(name: str, enum: str, offset: int, dimensions=(), description="") -> dict:
    return dict(
        arrays.field(name, enum, offset, dimensions, description=description),
        enum_type=enum,
    )


# Independently audited offsets, array order, type names and enum label/value rows.
EXPECTED = {
    "EnumBox<EnumBox<EnumState>>": [
        dict(
            arrays.field(
                "value",
                "EnumConsumers_plain_EnumBox_enum_EnumState_",
                0,
                description="selected value",
            ),
            structured_record="EnumBox<EnumState>",
        ),
        dict(
            arrays.field(
                "values", "EnumConsumers_plain_EnumBox_enum_EnumState_", 28, (2,)
            ),
            structured_record="EnumBox<EnumState>",
        ),
        dict(
            arrays.field(
                "matrix", "EnumConsumers_plain_EnumBox_enum_EnumState_", 84, (2, 2)
            ),
            structured_record="EnumBox<EnumState>",
        ),
    ],
    "EnumBox<EnumState>": [
        field("value", "EnumState", 0, description="selected value"),
        field("values", "EnumState", 4, (2,)),
        field("matrix", "EnumState", 12, (2, 2)),
    ],
    "EnumBox<EnumPhase>": [
        field("value", "EnumPhase", 0, description="selected value"),
        field("values", "EnumPhase", 4, (2,)),
        field("matrix", "EnumPhase", 12, (2, 2)),
    ],
    "EnumBox<enum_fixture::Mode>": [
        field("value", "enum_fixture::Mode", 0, description="selected value"),
        field("values", "enum_fixture::Mode", 4, (2,)),
        field("matrix", "enum_fixture::Mode", 12, (2, 2)),
    ],
    "EnumBox<EnumPhase[2]>": [
        field("value", "EnumPhase", 0, (2,), "selected value"),
        field("values", "EnumPhase", 8, (2, 2)),
        field("matrix", "EnumPhase", 24, (2, 2, 2)),
    ],
}
ENUMS = {
    "EnumState": [
        dict(label="state_negative", value="-3", mods=0),
        dict(label="state_zero", value="0", mods=0),
        dict(label="state_maximum", value="2147483647", mods=0),
    ],
    "EnumPhase": [
        dict(label="phase_idle", value="0", mods=0),
        dict(label="phase_running", value="2", mods=0),
        dict(label="phase_alias", value="2", mods=0),
    ],
    "enum_fixture::Mode": [
        dict(label="enum_fixture::mode_zero", value="0", mods=0x40000000),
        dict(label="enum_fixture::mode_high", value="2147483647", mods=0x40000000),
    ],
}
SYMBOLS = {v["symbol"] for v in BINDINGS.values()}


def reference() -> str:
    _, original = arrays.reference(HERE)
    # The captured generator emits enum blocks before all record blocks. Keep
    # the exact enum exports and five template blocks; exclude the consumer table.
    prefix, separator, _ = original.partition('extern "C" {\n\nATTRIBUTES')
    if not separator or set(re.findall(r"ENUM_ATTR enum(\w+)\[\]", prefix)) != {
        n.replace("::", "__") for n in ENUMS
    }:
        raise b.BaselineError("legacy enum dependency block selection differs")
    return prefix + "\n".join(templates.blocks(original, SYMBOLS).values()) + "\n"


def extract(extractor: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    case, _ = arrays.reference(HERE)
    header = native.ROOT / case["header"]
    command = [
        str(extractor),
        "--source-root",
        str(native.ROOT),
        "--select-file",
        str(header),
        str(header),
        "--",
    ]
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("TRICK_")
        and k not in ("CPATH", "CPLUS_INCLUDE_PATH", "C_INCLUDE_PATH")
    }
    result = subprocess.run(command, env=env, capture_output=True, timeout=60)
    (output / "extract.command.json").write_bytes(b.json_bytes(command))
    (output / "facts.json").write_bytes(result.stdout)
    (output / "extract.stderr").write_bytes(result.stderr)
    result.check_returncode()
    return json.loads(result.stdout)


def generate(facts: dict, output: Path) -> tuple[dict, str]:
    output.mkdir(parents=True, exist_ok=True)
    request = templates.request_for(facts, BINDINGS)
    model = resolve.resolve(facts, request)
    actual = {i["cpp_type"]: i["symbol"] for i in model["template_instances"]}
    if actual != {v["cpp_type"]: v["symbol"] for v in BINDINGS.values()}:
        raise b.BaselineError("enum template first-use names differ from legacy")
    nodes = {n["id"]: n for n in facts["declarations"]}
    if {
        nodes[d["declaration_id"]]["qualified_name"]
        for d in model["declarations"]
        if d["decision"] == "include"
    } != set(ENUMS):
        raise b.BaselineError("enum template dependency selection differs")
    for name, value in (("request", request), ("resolved", model)):
        (output / f"{name}.json").write_bytes(b.json_bytes(value))
    path = output / "candidate.cpp"
    emit.write(facts, request, model, path)
    return model, path.read_text()


def report_for(facts: dict) -> dict:
    nodes = {n["id"]: n for n in facts["declarations"]}
    records = {n["qualified_name"]: n for n in nodes.values() if n["kind"] == "record"}
    types = {t["id"]: t for t in facts["types"]}
    for name, rows in EXPECTED.items():
        fields = [nodes[i] for i in records[name]["field_ids"]]
        if [n["name"] for n in fields] != [r["name"] for r in rows]:
            raise b.BaselineError("enum template field selection differs")
        for node, row in zip(fields, rows, strict=True):
            base = types[types[node["type_id"]]["canonical_id"]]
            shape = []
            while base["kind"] == "array":
                shape.append(int(base["extent"]))
                base = types[types[base["element_id"]]["canonical_id"]]
            if (
                base["kind"] != ("record" if "structured_record" in row else "enum")
                or nodes[base["declaration_id"]]["qualified_name"]
                != row.get("enum_type", row.get("structured_record"))
                or any(base["qualifiers"].values())
                or shape != row["dimensions"]
                or int(node["offset_bits"]) != row["offset_bits"]
                or node["bitfield"]
            ):
                raise b.BaselineError("enum template facts differ from audited storage")
    return dict(records=EXPECTED, enums=ENUMS, record_bindings=BINDINGS)


def mutations(candidate: str) -> dict[str, tuple[str, str]]:
    symbol = BINDINGS["EnumBox<EnumState>"]["symbol"]
    registration = f"    trick_MM->add_attr_info(std::string(attr{symbol}[0].type_name), &attr{symbol}[0], __FILE__, __LINE__);\n"
    changes = {
        "missing-registration": (candidate.replace(registration, "", 1), "run"),
        "premature-size": (
            candidate.replace("15,TRICK_ENUMERATED, 0,", "15,TRICK_ENUMERATED, 4,", 1),
            "run",
        ),
        "wrong-enum-table": (
            candidate.replace('"value", "EnumState"', '"value", "EnumPhase"', 1),
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
                "size_t io_src_sizeof_EnumState()",
                "static size_t io_src_sizeof_EnumState()",
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
                '{"enum_fixture::mode_zero", 0, 0x40000000}',
                '{"enum_fixture::mode_zero", 0, 0x0}',
                1,
            ),
            "compare",
        ),
    }
    if any(source == candidate for source, _ in changes.values()):
        raise b.BaselineError("enum metadata mutation did not change its target")
    return changes


def capture(extractor: Path, root: Path, output: Path, compiler: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = output / "comparison.json"
    result.unlink(missing_ok=True)
    facts = extract(extractor, output)
    model, candidate = generate(facts, output / "generated")
    report = report_for(facts)
    flags = native.configured_link_flags(root, output)
    observed = []
    for label, source in (("legacy", reference()), ("candidate", candidate)):
        observed.append(
            native.capture(
                facts,
                source,
                report,
                dict(id="template-enums"),
                output / label,
                compiler,
                source_name=label + ".cpp",
                link_flags=flags,
            )
        )
    if observed[0]["observations"] != observed[1]["observations"]:
        raise b.BaselineError(
            "enum template legacy/candidate/native observations differ"
        )
    rejected = {}
    for name, (source, phase) in mutations(candidate).items():
        work = output / "mutations" / name
        try:
            native.capture(
                facts,
                source,
                report,
                dict(id="template-enums"),
                work,
                compiler,
                source_name="candidate.cpp",
                link_flags=flags,
            )
        except ValueError as error:
            last = json.loads((work / "commands.json").read_text())[-1]
            if (
                last["timed_out"]
                or last["stderr"]
                != ("run" if phase == "compare" else phase) + ".stderr"
                or (last["returncode"] == 0) != (phase == "compare")
                or (phase == "run" and last["returncode"] != 1)
            ):
                raise b.BaselineError(
                    "enum metadata mutation failed at wrong phase: " + name
                ) from error
            if (
                phase == "compare"
                and "compiled/native enum value, label, or signedness differs"
                not in str(error)
            ):
                raise
            rejected[name] = str(error)
        else:
            raise b.BaselineError("enum metadata mutation was accepted: " + name)
    report = dict(
        status="compared",
        records=5,
        fields=15,
        enum_tables=3,
        enumerators=8,
        legacy=observed[0],
        candidate=observed[1],
        resolved_digest=model["digest"],
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
