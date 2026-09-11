#!/usr/bin/env python3
"""Compare complete structured template tables using the real MemoryManager."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import array_metadata
import baseline as b
import differential as d
import native
import template_metadata as leaf

INPUTS = leaf.INPUTS
OUTER = "TTT1<Foo<int>, Foo<double[2]>[3]>"
SYMBOL = "TemplateTest_TTT_var_template_parameters_TTT1_Foo_int___Foo_double_2___3__"
BINDINGS = {
    OUTER: dict(
        symbol=SYMBOL,
        cpp_type=OUTER,
        units_prefix=OUTER,
        field="TemplateTest::TTT_var_template_parameters",
    ),
    **leaf.BINDINGS,
}
# Request the parent only; the two nested leaves must come from dependency closure.
REQUEST_BINDINGS = {
    name: binding for name, binding in BINDINGS.items() if not name.startswith("Foo<")
}
EXPECTED = {
    OUTER: [
        dict(
            array_metadata.field("aa", "TTT1_aa_Foo_int_", 0),
            structured_record="Foo<int>",
        ),
        dict(
            array_metadata.field("bb", "TTT1_bb_Foo_double_2__", 8, (3,)),
            structured_record="Foo<double[2]>",
        ),
    ],
    **leaf.EXPECTED,
}
SYMBOLS = {binding["symbol"] for binding in BINDINGS.values()}
extract = leaf.extract


def reference(root: Path = d.ROOT) -> str:
    return leaf.reference(root, symbols=SYMBOLS).replace(
        "#define TRICK_IN_IOSRC\n",
        '#define TRICK_IN_IOSRC\n#include "trick/MemoryManager.hh"\n',
        1,
    )


def generate(facts: dict, output: Path) -> tuple[dict, str]:
    return leaf.generate(
        facts, output, bindings=BINDINGS, request_bindings=REQUEST_BINDINGS
    )


def install_candidate(facts_path: Path, sim: Path, output: Path) -> tuple[Path, str]:
    return leaf.install_candidate(
        facts_path, sim, output, generator=generate, symbols=SYMBOLS
    )


def mutations(candidate: str) -> dict[str, str]:
    registration = f"    trick_MM->add_attr_info(std::string(attr{SYMBOL}[0].type_name), &attr{SYMBOL}[0], __FILE__, __LINE__);\n"
    changed = {
        "missing-registration": candidate.replace(registration, "", 1),
        "wrong-child-table": candidate.replace(
            '"TTT1_aa_Foo_int_"', '"TTT1_bb_Foo_double_2__"', 1
        ),
        "premature-size": candidate.replace(
            "15,TRICK_STRUCTURED, 0,", "15,TRICK_STRUCTURED, sizeof(Foo<int>),", 1
        ),
        "unguarded-init": candidate.replace(
            "if (initialized) return;", "if (initialized) initialized = false;", 1
        ),
        "missing-child-export": candidate.replace(
            "size_t io_src_sizeof_TTT1_aa_Foo_int_",
            "static size_t io_src_sizeof_TTT1_aa_Foo_int_",
        ),
    }
    if any(value == candidate for value in changed.values()):
        raise b.BaselineError("structured template mutation did not change its target")
    return changed


def check(facts: dict, root: Path, output: Path, compiler: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    result = output / "comparison.json"
    result.unlink(missing_ok=True)
    # Use the configured build's actual archives and external link dependencies.
    # Keep the circular archive grouping used by the production MM unit tests.
    config = {}
    for option in ("--libdir", "--libs", "--ldflags"):
        argv = [str(root / "bin/trick-config"), option]
        run = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=True,
            env=dict(os.environ, TRICK_HOME=str(root)),
            timeout=30,
        )
        config[option] = dict(argv=argv, stdout=run.stdout, stderr=run.stderr)
    libraries = sorted(Path(config["--libdir"]["stdout"].strip()).glob("*.a"))
    if not libraries:
        raise b.BaselineError("structured comparison requires built Trick archives")
    config["archive_sha256"] = {str(p): b.digest(p.read_bytes()) for p in libraries}
    (output / "link-config.json").write_bytes(b.json_bytes(config))
    flags = tuple([
        "-rdynamic",
        "-Wl,--start-group",
        *shlex.split(config["--libs"]["stdout"]),
        "-Wl,--end-group",
        *shlex.split(config["--ldflags"]["stdout"]),
    ])
    model, candidate = generate(facts, output / "generated")
    expected = dict(records=EXPECTED, enums={}, record_bindings=BINDINGS)
    case = dict(id="structured-template-members")
    old = native.capture(
        facts,
        reference(root),
        expected,
        case,
        output / "legacy",
        compiler,
        link_flags=flags,
    )
    new = native.capture(
        facts,
        candidate,
        expected,
        case,
        output / "candidate",
        compiler,
        source_name="candidate.cpp",
        link_flags=flags,
    )
    if old["observations"] != new["observations"]:
        raise b.BaselineError(
            "structured template legacy/candidate/native observations differ"
        )
    rejected = {}
    for label, changed in mutations(candidate).items():
        work = output / "mutations" / label
        try:
            native.capture(
                facts,
                changed,
                expected,
                case,
                work,
                compiler,
                source_name="candidate.cpp",
                link_flags=flags,
            )
        except ValueError as error:
            commands = json.loads((work / "commands.json").read_text())
            # A compile error is not evidence that an initialization mutation was caught.
            phase = "link" if label == "missing-child-export" else "run"
            if (
                commands[-1]["timed_out"]
                or not isinstance(commands[-1]["returncode"], int)
                or commands[-1]["returncode"] == 0
                or commands[-1]["stderr"] != f"{phase}.stderr"
            ):
                raise b.BaselineError(
                    "structured mutation failed at the wrong phase: " + label
                ) from error
            rejected[label] = str(error)
        else:
            raise b.BaselineError("structured template mutation was accepted: " + label)
    nodes = {n["id"]: n for n in facts["declarations"]}
    omissions = [
        (nodes[d["declaration_id"]]["name"], d["rule"])
        for i in model["template_instances"]
        for d in i["fields"]
        if d["decision"] == "omit"
    ]
    if sorted(omissions) != sorted(
        [(name, "IO_DISABLED") for name in ("ttt", "cc", "dd")] * 3
    ):
        raise b.BaselineError("structured template I/O exclusions changed")
    report = dict(
        status="compared",
        excluded_fields=9,
        compared_tables=5,
        compared_fields=8,
        legacy=old,
        candidate=new,
        mutations_rejected=rejected,
        resolved_digest=model["digest"],
    )
    result.write_bytes(b.json_bytes(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=d.ROOT)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    compiler = shutil.which(args.compiler)
    if compiler is None:
        parser.error("C++ compiler not found")
    check(
        json.loads(args.facts.read_text()),
        args.root.resolve(),
        args.output.resolve(),
        Path(compiler).absolute(),
    )
