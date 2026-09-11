#!/usr/bin/env python3
"""Exercise template first-use ordering against the unchanged legacy generator."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools/icg_baseline"))
import array_metadata  # noqa: E402
import native  # noqa: E402
import template_metadata  # noqa: E402

from tools.icg_emit import emit  # noqa: E402
from tools.icg_policy import cases, characterize, resolve  # noqa: E402

PREFIX = cases.HEADER + "template<class T> struct Box { T value; };\n"
# Source order, expected symbol, and request are independent of production policy.
CASES = {
    "repeated": (
        "struct Model { Box<int> first; Box<int> chosen; };",
        "Model_first_Box_int_",
        ["Model::first", "Model::chosen"],
        ["Model::first"],
    ),
    "ordinary-root-order": (
        "struct ZFirst { Box<int> first; }; struct ASecond { Box<int> chosen; };",
        "ZFirst_first_Box_int_",
        ["ASecond::chosen"],
        ["ZFirst::first"],
    ),
    "disabled-first": (
        "struct Model { Box<int> ignored; /* ** */\nBox<int> chosen; };",
        "Model_chosen_Box_int_",
        ["Model::chosen"],
        ["Model::chosen"],
    ),
    "alias-array-first": (
        "using Alias = Box<int>; struct Model { Alias first[2]; Box<int> chosen; };",
        "Model_first_Box_int_",
        ["Model::first", "Model::chosen"],
        ["Model::first"],
    ),
    "pointer-first": (
        "struct Model { Box<int>* first; Box<int> chosen; };",
        "Model_first_Box_int_",
        ["Model::chosen"],
        ["Model::first"],
    ),
    "reference-first": (
        "struct Model { Box<int>& first; Box<int> chosen; };",
        "Model_first_Box_int_",
        ["Model::chosen"],
        ["Model::first"],
    ),
    "nested-first": (
        "template<class T> struct Wrapper { T inner; T repeated; };\n"
        "struct Model { Wrapper<Box<int>> outer; Box<int> chosen; };",
        "Wrapper_inner_Box_int_",
        ["Model::chosen", "Wrapper<Box<int>>::repeated"],
        ["Model::outer", "Wrapper<Box<int>>::inner"],
    ),
    "recursive-dependency": (
        "template<class T> struct Wrapper { Box<T> inner; Wrapper<T>* next; };\n"
        "struct Model { Wrapper<int> outer; Box<int> chosen; };",
        "Wrapper_inner_Box_int_",
        ["Model::chosen"],
        ["Model::outer", "Wrapper<int>::inner"],
    ),
}


def capture(
    extractor: Path, legacy: Path, compiler: Path, output: Path, xml: Path
) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    result = output / "comparison.json"
    result.unlink(missing_ok=True)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("TRICK_")
        and k not in ("CPATH", "CPLUS_INCLUDE_PATH", "C_INCLUDE_PATH")
    }
    env.update(
        TRICK_HOME=str(ROOT),
        TRICK_CXX=str(compiler),
        UDUNITS2_XML_PATH=str(xml),
        LC_ALL="C",
        LANG="C",
    )
    report = dict(
        schema_version=1,
        cases={},
        legacy_binary_sha256=hashlib.sha256(legacy.read_bytes()).hexdigest(),
    )
    for name, (body, symbol, requested, expected_path) in CASES.items():
        work = output / name
        (work / "build").mkdir(parents=True, exist_ok=True)
        header = work / "model.hh"
        header.write_text(PREFIX + body + "\n")
        tu = work / "S_source.hh"
        tu.write_text('#include "model.hh"\n')
        characterize.run(
            [str(legacy), "-m", "--icg-std=c++17", str(tu)], work, "legacy", env
        ).check_returncode()
        old = "\n".join(p.read_text() for p in (work / "build").rglob("io_*.cpp"))
        # Exactly one leaf table: repeated use must never invent a second symbol.
        tables = characterize.metadata(old)
        if {s for s in tables if s.endswith("_Box_int_")} != {symbol}:
            raise ValueError(f"{name}: legacy first-use tables changed")
        extracted = characterize.run(
            [
                str(extractor),
                "--source-root",
                str(work),
                "--select-file",
                str(header),
                "--select-file",
                str(tu),
                str(tu),
                "--",
            ],
            work,
            "extractor",
            env,
        )
        extracted.check_returncode()
        facts = json.loads(extracted.stdout)
        (work / "facts.json").write_bytes(extracted.stdout)
        nodes = {n["id"]: n for n in facts["declarations"]}
        ids = sorted(
            n["id"]
            for n in nodes.values()
            if n["kind"] == "field" and n["qualified_name"] in requested
        )
        if len(ids) != len(requested):
            raise ValueError(f"{name}: missing requested field")
        request = resolve.request_for(
            facts, outputs=["template-attributes"], template_field_ids=ids
        )
        model = resolve.resolve(facts, request)
        (instance,) = model["template_instances"]
        if (
            instance["symbol"] != symbol
            or instance["requested_field_ids"] != ids
            or [nodes[i]["qualified_name"] for i in instance["dependency_path"]]
            != expected_path
        ):
            raise ValueError(f"{name}: candidate first-use naming/path changed")
        for label, value in (("request", request), ("resolved", model)):
            (work / f"{label}.json").write_text(json.dumps(value, indent=2) + "\n")
        candidate = emit.render(facts, request, model)
        legacy_leaf = (
            '#include <stdlib.h>\n#include "trick/attributes.h"\n#include "trick/UnitsMap.hh"\n'
            f'#include "{header}"\n' + template_metadata.blocks(old, {symbol})[symbol]
        )
        expected = dict(
            records={"Box<int>": [array_metadata.field("value", "int", 0)]},
            enums={},
            record_bindings={
                "Box<int>": dict(
                    symbol=symbol, cpp_type="Box<int>", units_prefix="Box<int>"
                )
            },
        )
        observations = []
        for label, source in (("legacy", legacy_leaf), ("candidate", candidate)):
            observations.append(
                native.capture(
                    facts, source, expected, dict(id=name), work / label, compiler
                )["observations"]
            )
        if observations[0] != observations[1]:
            raise ValueError(f"{name}: legacy/candidate/native mismatch")
        report["cases"][name] = dict(
            symbol=symbol,
            dependency_path=expected_path,
            header_sha256=hashlib.sha256(header.read_bytes()).hexdigest(),
            observations=observations[0],
        )
    report["status"] = "compared"
    result.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extractor", type=Path, required=True)
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--udunits-xml", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    compiler = shutil.which(args.compiler)
    if compiler is None:
        parser.error("C++ compiler not found")
    capture(
        args.extractor.resolve(),
        args.legacy.resolve(),
        Path(compiler).absolute(),
        args.output.resolve(),
        args.udunits_xml.resolve(),
    )
