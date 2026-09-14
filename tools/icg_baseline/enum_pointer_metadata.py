#!/usr/bin/env python3
"""Compare enum pointer rows, native pointer storage and runtime dependencies."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

import array_metadata as arrays
import baseline as b
import native
import record_enum_metadata as records
import template_enum_metadata as enums

from tools.icg_emit import emit
from tools.icg_policy import resolve

HERE = Path(__file__).with_name("enum_pointers")


def pointer(name, enum, offset, dimensions=(), **kwargs):
    return dict(
        records.field(name, enum, offset, (*dimensions, 0), **kwargs), pointer=True
    )


# Manually audited LP64 layout and exact legacy rows, independent of policy.
EXPECTED = {
    "EnumPointerModel": [
        arrays.field("lead", "int", 0),
        pointer("state", "PointerState", 8, description="state target"),
        pointer("phase", "PointerPhase", 16),
        pointer("mode", "enum_pointer::Mode", 24),
        pointer("alias", "PointerState", 32),
        pointer("states", "PointerState", 40, (3,)),
        pointer("matrix", "PointerPhase", 64, (2, 2)),
        records.field("local", "PointerState", 96),
        arrays.field("tail", "int", 100),
    ],
    "enum_pointer::Targets": [
        records.field("states", "PointerState", 0, (3,)),
        records.field("phases", "PointerPhase", 12, (3,)),
        records.field("modes", "enum_pointer::Mode", 24, (3,)),
    ],
}
ENUMS = {
    "PointerState": [
        dict(label="pointer_negative", value="-3", mods=0),
        dict(label="pointer_zero", value="0", mods=0),
        dict(label="pointer_maximum", value="2147483647", mods=0),
    ],
    "PointerPhase": [
        dict(label="pointer_idle", value="0", mods=0),
        dict(label="pointer_running", value="2", mods=0),
        dict(label="pointer_alias", value="2", mods=0),
    ],
    "enum_pointer::Mode": [
        dict(label="enum_pointer::pointer_mode_zero", value="0", mods=0x40000000),
        dict(
            label="enum_pointer::pointer_mode_high", value="2147483647", mods=0x40000000
        ),
    ],
}


def reference():
    return arrays.reference(HERE)[1]


def extract(extractor, output):
    return arrays.extract(extractor, output, arrays.reference(HERE)[0])


def generate(facts, output):
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
                raise b.BaselineError("enum pointer metadata table selection differs")
    return model, candidate


def mutations(candidate):
    registration = "    trick_MM->add_attr_info(std::string(attrEnumPointerModel[1].type_name), &attrEnumPointerModel[1], __FILE__, __LINE__);\n"
    changes = {
        "missing-registration": (candidate.replace(registration, "", 1), "run"),
        "premature-size": (
            candidate.replace("15,TRICK_ENUMERATED, 0,", "15,TRICK_ENUMERATED, 4,", 1),
            "run",
        ),
        "wrong-enum-table": (
            candidate.replace('"state", "PointerState"', '"state", "PointerPhase"', 1),
            "run",
        ),
        "unguarded-init": (
            candidate.replace(
                "if (initialized) return;", "if (initialized) initialized = false;", 1
            ),
            "run",
        ),
        "pointee-size": (
            candidate.replace(
                "return sizeof(::PointerState);", "return sizeof(void*);", 1
            ),
            "field-compare",
        ),
        "pointer-extent": (
            candidate.replace("8, NULL, 1, {{0, 0}", "8, NULL, 1, {{1, 0}", 1),
            "run",
        ),
        "pointer-rank": (
            candidate.replace("8, NULL, 1,", "8, NULL, 0,", 1),
            "field-compare",
        ),
        "pointer-array-shape": (
            candidate.replace("40, NULL, 2, {{3, 0}", "40, NULL, 2, {{2, 0}", 1),
            "field-compare",
        ),
        "missing-enum-size": (
            candidate.replace(
                "size_t io_src_sizeof_PointerState()",
                "static size_t io_src_sizeof_PointerState()",
                1,
            ),
            "link",
        ),
        "wrong-enum-label": (
            candidate.replace(
                '{"pointer_negative", -3, 0x0}', '{"wrong_label", -3, 0x0}', 1
            ),
            "compare",
        ),
        "wrong-unsigned-mods": (
            candidate.replace(
                '{"enum_pointer::pointer_mode_zero", 0, 0x40000000}',
                '{"enum_pointer::pointer_mode_zero", 0, 0x0}',
                1,
            ),
            "compare",
        ),
    }
    if any(source == candidate for source, _ in changes.values()):
        raise b.BaselineError("enum pointer mutation missed its target")
    return changes


def capture(extractor, root, output, compiler):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").unlink(missing_ok=True)
    facts = extract(extractor, output)
    model, candidate = generate(facts, output / "generated")
    return enums.compare(
        facts,
        model,
        candidate,
        reference(),
        records.report_for(facts, EXPECTED, ENUMS),
        output,
        compiler,
        native.configured_link_flags(root, output),
        case_id="enum-pointers",
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
