#!/usr/bin/env python3
"""Compare record pointer rows, native pointer storage and runtime dependencies."""

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

HERE = Path(__file__).with_name("record_pointers")


def pointer(name, record, offset, dimensions=(), **kwargs):
    return dict(
        arrays.field(name, record, offset, (*dimensions, 0), **kwargs),
        structured_record=record,
        pointer=True,
    )


# Manually audited LP64 layout and legacy rows, independent of generation policy.
EXPECTED = {
    "RecordPointerModel": [
        arrays.field("lead", "int", 0),
        pointer("head", "record_pointer::Node", 8),
        pointer("peer", "record_pointer::Peer", 16),
        pointer("alias", "record_pointer::Node", 24),
        pointer("nodes", "record_pointer::Node", 32, (3,)),
        pointer("matrix", "record_pointer::Node", 56, (2, 2)),
        arrays.field("tail", "int", 88),
    ],
    "record_pointer::Node": [
        arrays.field("value", "int", 0),
        pointer("next", "record_pointer::Node", 8, description="next node"),
        pointer("peer", "record_pointer::Peer", 16),
    ],
    "record_pointer::Peer": [
        arrays.field("value", "double", 0),
        pointer("owner", "record_pointer::Node", 8),
    ],
}
ENUMS = {}


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
                raise b.BaselineError("record pointer metadata table selection differs")
    return model, candidate


def mutations(candidate):
    registration = "    trick_MM->add_attr_info(std::string(attrRecordPointerModel[1].type_name), &attrRecordPointerModel[1], __FILE__, __LINE__);\n"
    changes = {
        "missing-registration": (candidate.replace(registration, "", 1), "run"),
        "premature-size": (
            candidate.replace("15,TRICK_STRUCTURED, 0,", "15,TRICK_STRUCTURED, 24,", 1),
            "run",
        ),
        "wrong-record-table": (
            candidate.replace(
                '"head", "record_pointer::Node"', '"head", "record_pointer::Peer"', 1
            ),
            "run",
        ),
        "unguarded-root-init": (
            candidate.replace(
                "if (initialized) return;", "if (initialized) initialized = false;", 1
            ),
            "run",
        ),
        "pointee-size": (
            candidate.replace(
                "return sizeof(::record_pointer::Node);", "return sizeof(void*);", 1
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
            candidate.replace("32, NULL, 2, {{3, 0}", "32, NULL, 2, {{2, 0}", 1),
            "field-compare",
        ),
        "missing-record-size": (
            candidate.replace(
                "size_t io_src_sizeof_record_pointer__Node()",
                "static size_t io_src_sizeof_record_pointer__Node()",
                1,
            ),
            "link",
        ),
    }
    if any(source == candidate for source, _ in changes.values()):
        raise b.BaselineError("record pointer mutation missed its target")
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
        case_id="record-pointers",
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
