#!/usr/bin/env python3
"""Compile scoped-enum candidate/legacy/native evidence and known rejections."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import baseline as b
import differential as d
import native

from tools.icg_emit import emit
from tools.icg_policy import resolve, rules

HERE = Path(__file__).with_name("enums")
REFERENCE = HERE / "reference"
EXCLUDED = {
    "icg_enum::v1::Owner::Hidden": "private nested enum",
    "icg_enum::Opaque": "opaque enum declaration has no legacy table",
}

# Independent expectations, not generated from the resolver or captured C++.
VALUES = {
    "GlobalMode": ("", 0, [("off", -3), ("on", 7)]),
    "icg_enum::Plain": (
        "icg_enum",
        0,
        [("minimum", -2147483648), ("maximum", 2147483647)],
    ),
    "icg_enum::Signed": (
        "icg_enum",
        0,
        [("negative", -21), ("zero", 0), ("alias", 0), ("positive", 3)],
    ),
    "icg_enum::Byte": ("icg_enum", 0x40000000, [("zero", 0), ("last", 127)]),
    "icg_enum::Word": ("icg_enum", 0x40000000, [("zero", 0), ("last", 32767)]),
    "icg_enum::DWord": ("icg_enum", 0x40000000, [("zero", 0), ("last", 2147483647)]),
    "icg_enum::QWord": ("icg_enum", 0x40000000, [("last", 2147483647)]),
    "icg_enum::Empty": ("icg_enum", 0, []),
    "icg_enum::v1::Mode": ("icg_enum::v1", 0, [("off", 0), ("on", 1)]),
    "icg_enum::v1::Owner::State": (
        "icg_enum::v1::Owner",
        0,
        [("idle", -1), ("active", 2)],
    ),
}
EXPECTED = {
    name: [
        dict(label=f"{scope}::{label}" if scope else label, value=str(value), mods=mods)
        for label, value in rows
    ]
    for name, (scope, mods, rows) in VALUES.items()
}


def reference(case_id: str) -> tuple[dict, str]:
    manifest = json.loads((HERE / "corpus.json").read_text())
    provenance = json.loads((REFERENCE / "provenance.json").read_text())
    if b.digest((HERE / "corpus.json").read_bytes()) != provenance["manifest_sha256"]:
        raise ValueError("enum corpus differs from the captured manifest")
    case = next(c for c in manifest["cases"] if c["id"] == case_id)
    header = d.ROOT / case["header"]
    if b.digest(header.read_bytes()) != provenance["source_sha256"][case["header"]]:
        raise ValueError("enum fixture differs from captured source")
    path = REFERENCE / case_id / "cold.json"
    metadata = [
        a
        for a in json.loads(path.read_text())["artifacts"].values()
        if a["group"] == "legacy-metadata"
    ]
    if len(metadata) != 1:
        raise ValueError("expected one captured enum metadata source")
    return case, b.artifact_text(path, metadata[0])


def report_for(facts: dict, legacy: str) -> dict:
    report = d.compare(
        facts, legacy, "scoped-enums", record_exclusions={}, enum_exclusions=EXCLUDED
    )
    if report["enums"] != EXPECTED:
        raise ValueError(
            "enum corpus differs from independent label/value expectations"
        )
    return report


def check(facts: dict, output: Path, compiler: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result_path = output / "comparison.json"
    result_path.unlink(missing_ok=True)
    case, legacy = reference("scoped-enums")
    request = resolve.request_for(facts)
    model = resolve.resolve(facts, request)
    report = report_for(facts, legacy)
    for name, value in (("facts", facts), ("request", request), ("resolved", model)):
        (output / f"{name}.json").write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n"
        )
    # Legacy reopens inline namespaces without 'inline'. Preserve its source and
    # warning; relax only this Clang warning's -Werror promotion in the old lane.
    # Candidate compilation keeps the full warnings-as-errors contract.
    version = subprocess.check_output([str(compiler), "--version"], text=True)
    legacy_flags = (
        ("-Wno-error=inline-namespace-reopened-noninline",)
        if "clang" in version.lower()
        else ()
    )
    old = native.capture(
        facts,
        legacy,
        report,
        case,
        output / "legacy",
        compiler,
        compile_flags=legacy_flags,
    )
    path = output / "candidate" / "candidate.cpp"
    emit.write(facts, request, model, path)
    candidate = path.read_text()
    if report_for(facts, candidate) != report:
        raise ValueError("candidate tables differ from legacy evidence")
    new = native.capture(
        facts,
        candidate,
        report,
        case,
        path.parent,
        compiler,
        source_name="candidate.cpp",
    )
    if new["observations"] != old["observations"]:
        raise ValueError("candidate/legacy/native enum observations differ")
    report.update(
        status="compared",
        legacy=old,
        candidate=new,
        legacy_sha256=b.digest(legacy.encode()),
        candidate_sha256=b.digest(candidate.encode()),
        resolved_digest=model["digest"],
        legacy_diagnostic_exceptions=list(legacy_flags),
    )
    result_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def check_rejection(facts: dict, output: Path, compiler: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result_path = output / "rejection.json"
    result_path.unlink(missing_ok=True)
    _, legacy = reference("unsigned-narrow")
    (output / "legacy.cpp").write_text(legacy.replace("${TRICK_ROOT}", str(d.ROOT)))
    (output / "probe.cpp").write_bytes((HERE / "rejection_probe.cpp").read_bytes())
    evidence = native.execute([output / "probe.cpp"], output, compiler)
    if evidence["observations"] != {
        "Boolean": [-1, 1],
        "Byte": [-128, 128, -1, 255],
        "Word": [-32768, 32768, -1, 65535],
    }:
        raise ValueError(
            "legacy unsigned-narrow sign extension differs from observations"
        )
    request = resolve.request_for(facts)
    (output / "facts.json").write_text(
        json.dumps(facts, indent=2, sort_keys=True) + "\n"
    )
    (output / "request.json").write_text(
        json.dumps(request, indent=2, sort_keys=True) + "\n"
    )
    candidate = output / "candidate.cpp"
    candidate.unlink(missing_ok=True)
    try:
        model = resolve.resolve(facts, request)
        emit.write(facts, request, model, candidate)
    except rules.PolicyError as error:
        if error.code != "ICG_POLICY_ENUM_SIGN_EXTENSION":
            raise
        evidence.update(
            status="rejected",
            code=error.code,
            diagnostic=str(error),
            legacy_sha256=b.digest(legacy.encode()),
        )
        (output / "policy.stderr").write_text(str(error) + "\n")
    else:
        raise ValueError("unsigned-narrow request incorrectly produced a candidate")
    if candidate.exists():
        raise ValueError("rejected enum request published source")
    result_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return evidence


def capture(extractor: Path, output: Path, compiler: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").unlink(missing_ok=True)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("TRICK_")
        and k not in ("CPATH", "CPLUS_INCLUDE_PATH", "C_INCLUDE_PATH")
    }
    results = {}
    for name, check_case in (
        ("scoped-enums", check),
        ("unsigned-narrow", check_rejection),
    ):
        case, _ = reference(name)
        work = output / name
        work.mkdir(exist_ok=True)
        source = work / "S_source.hh"
        source.write_text(f'#include "{d.ROOT / case["header"]}"\n')
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
        (work / "extract.command.json").write_text(json.dumps(command, indent=2) + "\n")
        (work / "facts.json").write_bytes(p.stdout)
        (work / "extract.stderr").write_bytes(p.stderr)
        p.check_returncode()
        results[name] = check_case(json.loads(p.stdout), work, compiler)
    (output / "comparison.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n"
    )
    return results


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
