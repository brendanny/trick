#!/usr/bin/env python3
"""Compare bounded policy decisions with live, unchanged legacy ICG output."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.icg_policy import cases, resolve, rules  # noqa: E402


def metadata(text: str) -> dict:
    result = {}
    for table in re.finditer(
        r"^ATTRIBUTES attr(\w+)\[\] = \{\n(.*?)\} \};", text, re.M | re.S
    ):
        rows = list(
            re.finditer(
                r'\{"([^"\n]*)", "[^"\n]*", "([^"\n]*)", "", "",\s*"[^"\n]*",\s*(\d+),TRICK_\w+',
                table[2],
            )
        )
        if not rows or rows[-1][1] or len(rows) != table[2].count('{"'):
            raise ValueError("unrecognized legacy table/sentinel")
        if table[1] in result:
            raise ValueError("duplicate legacy table")
        result[table[1]] = {r[1]: dict(units=r[2], io=int(r[3])) for r in rows[:-1]}
        if len(result[table[1]]) != len(rows) - 1:
            raise ValueError("duplicate legacy field")
    if len(result) != text.count("ATTRIBUTES attr"):
        raise ValueError("missing legacy table")
    return result


def observed(facts: dict, model: dict) -> dict:
    nodes = {n["id"]: n for n in facts["declarations"]}
    decisions = {n["declaration_id"]: n for n in model["declarations"]}
    result = {}
    for decision in model["declarations"]:
        node = nodes[decision["declaration_id"]]
        if node["kind"] != "record" or decision["decision"] != "include":
            continue
        result[decision["metadata"]["symbol"]] = {
            nodes[i]["name"]: {
                k: decisions[i]["metadata"]["annotation"][k] for k in ("units", "io")
            }
            for i in node["field_ids"]
            if decisions[i]["decision"] == "include"
        }
    return result


def run(
    command: list[str], work: Path, name: str, env: dict
) -> subprocess.CompletedProcess:
    (work / f"{name}.command.json").write_text(json.dumps(command, indent=2) + "\n")
    process = subprocess.run(
        command, cwd=work, env=env, capture_output=True, check=False
    )
    (work / f"{name}.stdout").write_bytes(process.stdout)
    (work / f"{name}.stderr").write_bytes(process.stderr)
    return process


def capture(
    extractor: Path, legacy: Path, compiler: Path, output: Path, xml: Path
) -> dict:
    output.mkdir(parents=True, exist_ok=False)
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
        scope="bounded-legacy-policy",
        status="incomplete",
        cases={},
        legacy_binary_digest=hashlib.sha256(legacy.read_bytes()).hexdigest(),
        extractor_binary_digest=hashlib.sha256(extractor.read_bytes()).hexdigest(),
    )
    report["udunits_xml_digests"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(xml.parent.glob("*.xml"))
    }
    report["compiler_version"] = subprocess.check_output(
        [str(compiler), "--version"], text=True
    )
    report["checkout_legacy_source_digests"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((ROOT / "trick_source/codegen/Interface_Code_Gen").glob("*"))
        if p.is_file()
    }
    (output / "comparison.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    for name, source, expected, overrides, rejected_code in [
        (*c, None) for c in cases.cases()
    ] + cases.rejections():
        work = output / name
        (work / "build").mkdir(parents=True)
        header = work / "model.hh"
        header.write_text(source)
        tu = work / "S_source.hh"
        tu.write_text('#include "model.hh"\n')
        case_env = dict(
            env, **{k: v.replace("$HEADER", str(header)) for k, v in overrides.items()}
        )
        old = run(
            [str(legacy), "-m", "--icg-std=c++17", str(tu)], work, "legacy", case_env
        )
        old.check_returncode()
        legacy_metadata = "\n".join(
            p.read_text() for p in (work / "build").rglob("io_*.cpp")
        )
        actual_legacy = metadata(legacy_metadata)
        if actual_legacy != expected:
            raise ValueError(
                f"{name}: legacy changed: {actual_legacy!r} != {expected!r}"
            )
        new = run(
            [
                str(extractor),
                "--source-root",
                str(work),
                "--select-file",
                str(header),
                str(tu),
                "--",
            ],
            work,
            "extractor",
            case_env,
        )
        new.check_returncode()
        facts = json.loads(new.stdout)
        request = resolve.request_for(facts)
        if rejected_code:
            try:
                resolve.resolve(facts, request)
            except rules.PolicyError as error:
                if error.code != rejected_code:
                    raise
                report["cases"][name] = dict(
                    status="rejected", code=error.code, legacy_tables=actual_legacy
                )
                (work / "policy.stderr").write_text(str(error) + "\n")
                (work / "request.json").write_text(json.dumps(request, indent=2) + "\n")
                (output / "comparison.json").write_text(
                    json.dumps(report, indent=2, sort_keys=True) + "\n"
                )
                continue
            raise ValueError(f"{name}: required policy rejection did not occur")
        model = resolve.resolve(facts, request)
        resolve.validate(facts, request, model)
        actual_new = observed(facts, model)
        if actual_new != expected:
            raise ValueError(f"{name}: policy differs: {actual_new!r} != {expected!r}")
        for filename, value in (
            ("request", request),
            ("resolved", model),
            ("observed", actual_legacy),
        ):
            (work / f"{filename}.json").write_text(
                json.dumps(value, indent=2, sort_keys=True) + "\n"
            )
        report["cases"][name] = dict(
            status="compared", tables=actual_new, resolved_digest=model["digest"]
        )
        (output / "comparison.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
    report["status"] = "success"
    (output / "comparison.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extractor", required=True, type=Path)
    parser.add_argument("--legacy", required=True, type=Path)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--udunits-xml", required=True, type=Path)
    args = parser.parse_args()
    compiler = shutil.which(args.compiler)
    if not compiler:
        parser.error("C++ compiler not found")
    # Existing legacy ICG invokes these paths through a shell.
    if any(
        not re.fullmatch(r"[/\w.+-]+", str(p), re.ASCII) for p in (ROOT, Path(compiler))
    ):
        parser.error("legacy root/compiler path is not shell-safe")
    capture(
        args.extractor.resolve(strict=True),
        args.legacy.resolve(strict=True),
        Path(compiler).absolute(),
        args.output.resolve(),
        args.udunits_xml.resolve(strict=True),
    )
