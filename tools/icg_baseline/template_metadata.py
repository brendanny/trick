#!/usr/bin/env python3
"""Compare two captured template-use tables and install a simulation test overlay."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import array_metadata
import baseline as b
import differential as d
import native

from tools.icg_emit import emit
from tools.icg_policy import resolve

INPUTS = (
    "test/SIM_test_templates/models/TemplateTest.hh",
    "test/SIM_test_templates/models/Foo.hh",
)
# Independent expectations from the immutable legacy capture and native types.
BINDINGS = {
    "TTT1<int, double>": dict(
        symbol="TemplateTest_TTT_var_scalar_builtins_TTT1_int__double_",
        cpp_type="TTT1<int, double>",
        units_prefix="TTT1<int, double>",
        field="TemplateTest::TTT_var_scalar_builtins",
    ),
    "TTT1<int[2], double[3]>": dict(
        symbol="TemplateTest_TTT_var_array_builtins_TTT1_int_2___double_3__",
        cpp_type="TTT1<int[2], double[3]>",
        units_prefix="TTT1<int[2], double[3]>",
        field="TemplateTest::TTT_var_array_builtins",
    ),
}
EXPECTED = {
    "TTT1<int, double>": [
        array_metadata.field("aa", "int", 0),
        array_metadata.field("bb", "double", 8),
    ],
    "TTT1<int[2], double[3]>": [
        array_metadata.field("aa", "int", 0, (2,)),
        array_metadata.field("bb", "double", 8, (3,)),
    ],
}
SYMBOLS = {binding["symbol"] for binding in BINDINGS.values()}
MARKER = "// Begin independently generated template candidate."


def blocks(source: str, symbols: set[str]) -> dict[str, str]:
    result = {}
    for symbol in sorted(symbols):
        matches = list(
            re.finditer(
                r'extern "C" \{\s*ATTRIBUTES attr'
                + re.escape(symbol)
                + r"\[\] = \{.*?\} um"
                + re.escape(symbol)
                + r";",
                source,
                re.S,
            )
        )
        if len(matches) != 1:
            raise b.BaselineError(
                "expected one complete legacy template block: " + symbol
            )
        result[symbol] = matches[0][0]
    return result


def reference(root: Path = d.ROOT) -> str:
    provenance = json.loads((d.REFERENCE / "provenance.json").read_text())
    for name in INPUTS:
        if b.digest((root / name).read_bytes()) != provenance["source_sha256"][name]:
            raise b.BaselineError(
                "template fixture differs from captured input: " + name
            )
    snapshot = d.REFERENCE / "templates/cold.json"
    (metadata,) = [
        a
        for name, a in json.loads(snapshot.read_text())["artifacts"].items()
        if name.endswith("/io_TemplateTest.cpp")
    ]
    original = b.artifact_text(snapshot, metadata)
    return (
        '#define TRICK_IN_IOSRC\n#include <stdlib.h>\n#include "trick/attributes.h"\n#include "trick/UnitsMap.hh"\n'
        f'#include "{root / INPUTS[0]}"\n'
        + "\n".join(blocks(original, SYMBOLS).values())
        + "\n"
    )


def request_for(facts: dict) -> dict:
    fields = {
        n["qualified_name"]: n["id"]
        for n in facts["declarations"]
        if n["kind"] == "field"
    }
    return resolve.request_for(
        facts,
        outputs=["template-attributes"],
        template_field_ids=sorted(
            fields[binding["field"]] for binding in BINDINGS.values()
        ),
    )


def generate(facts: dict, output: Path) -> tuple[dict, str]:
    output.mkdir(parents=True, exist_ok=True)
    request = request_for(facts)
    model = resolve.resolve(facts, request)
    for name, value in (("request", request), ("resolved", model)):
        (output / f"{name}.json").write_bytes(b.json_bytes(value))
    path = output / "candidate.cpp"
    emit.write(facts, request, model, path)
    actual = {i["cpp_type"]: i["symbol"] for i in model["template_instances"]}
    if actual != {name: binding["symbol"] for name, binding in BINDINGS.items()}:
        raise b.BaselineError("resolved template symbols differ from captured bindings")
    return model, path.read_text()


def extract(extractor: Path, root: Path, output: Path) -> Path:
    reference(root)
    output.mkdir(parents=True, exist_ok=True)
    header = root / INPUTS[0]
    command = [
        str(extractor.resolve()),
        "--source-root",
        str(root),
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
    result = subprocess.run(command, capture_output=True, env=env, timeout=60)
    (output / "extract.command.json").write_bytes(b.json_bytes(command))
    facts = output / "facts.json"
    facts.write_bytes(result.stdout)
    (output / "extract.stderr").write_bytes(result.stderr)
    result.check_returncode()
    return facts


def check(facts: dict, output: Path, compiler: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    result = output / "comparison.json"
    result.unlink(missing_ok=True)
    legacy = reference()
    model, candidate = generate(facts, output / "candidate")
    report = dict(records=EXPECTED, enums={}, record_bindings=BINDINGS)
    case = dict(id="template-members")
    old = native.capture(facts, legacy, report, case, output / "legacy", compiler)
    new = native.capture(
        facts,
        candidate,
        report,
        case,
        output / "candidate",
        compiler,
        source_name="candidate.cpp",
    )
    if old["observations"] != new["observations"]:
        raise b.BaselineError("template legacy/candidate/native observations differ")
    omissions = [
        d
        for i in model["template_instances"]
        for d in i["fields"]
        if d["decision"] == "omit"
    ]
    nodes = {n["id"]: n for n in facts["declarations"]}
    if sorted(
        (nodes[d["declaration_id"]]["name"], d["rule"]) for d in omissions
    ) != sorted([(name, "IO_DISABLED") for name in ("ttt", "cc", "dd")] * 2):
        raise b.BaselineError("template pointer I/O exclusions differ")
    report.update(
        status="compared",
        legacy=old,
        candidate=new,
        compared_tables=2,
        compared_fields=4,
        excluded_fields=6,
        resolved_digest=model["digest"],
        legacy_sha256=b.digest(legacy.encode()),
        candidate_sha256=b.digest(candidate.encode()),
    )
    result.write_bytes(b.json_bytes(report))
    return report


def capture(extractor: Path, output: Path, compiler: Path) -> dict:
    output = output.resolve()
    (output / "comparison.json").unlink(missing_ok=True)
    return check(
        json.loads(extract(extractor, d.ROOT, output).read_text()), output, compiler
    )


def overlay(original: str, candidate: str, symbols: set[str]) -> str:
    if MARKER in original or "icg_baseline_legacy_attr" in original:
        raise b.BaselineError("template overlay already installed")
    declarations = ['#include "trick/attributes.h"\n']
    for symbol, block in blocks(original, symbols).items():
        names = [
            f"attr{symbol}",
            f"init_attr{symbol}",
            f"init_attr{symbol}_c_intf",
            f"io_src_sizeof_{symbol}",
            f"UnitsMap{symbol}",
            f"um{symbol}",
        ]
        pattern = r"\b(?:" + "|".join(re.escape(n) for n in names) + r")\b"
        original = original.replace(
            block, re.sub(pattern, lambda m: "icg_baseline_legacy_" + m[0], block), 1
        )
        # References in containing-record initialization continue to use the
        # original ABI names, which only the candidate now defines.
        declarations.append(
            f'extern "C" {{ extern ATTRIBUTES attr{symbol}[]; void init_attr{symbol}_c_intf(); size_t io_src_sizeof_{symbol}(); }}\nvoid init_attr{symbol}();\n'
        )
    return "".join(declarations) + original + "\n" + MARKER + "\n" + candidate


def install_candidate(facts_path: Path, sim: Path, output: Path) -> tuple[Path, str]:
    output.mkdir(parents=True, exist_ok=False)
    model, candidate = generate(json.loads(facts_path.read_text()), output)
    sources = [
        p
        for p in (sim / "build").rglob("io_*.cpp")
        if "ATTRIBUTES attrTemplateTest_TTT_var_scalar_builtins_TTT1_int__double_[]"
        in p.read_text()
    ]
    if len(sources) != 1:
        raise b.BaselineError("expected one generated template source for the overlay")
    target = sources[0]
    original = target.read_text()
    replacement = overlay(original, candidate, SYMBOLS)
    (output / "legacy-original.cpp").write_text(original)
    (output / "overlay.cpp").write_text(replacement)
    (output / "overlay.json").write_bytes(
        b.json_bytes(
            dict(
                source=str(target),
                legacy_sha256=b.digest(original.encode()),
                candidate_sha256=b.digest(candidate.encode()),
                overlay_sha256=b.digest(replacement.encode()),
                resolved_digest=model["digest"],
                symbols=sorted(SYMBOLS),
            )
        )
    )
    target.write_text(replacement)
    return target, replacement


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
