#!/usr/bin/env python3
"""Capture unchanged legacy ICG output in isolated, disposable header workspaces."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import baseline as b

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "legacy/corpus.json"
PASSES = ("cold", "warm", "forced")


def compare_to_file(old: Path, new: Path, log: Path) -> bool:
    with log.open("w") as stream, contextlib.redirect_stdout(stream):
        return not b.compare(old, new)


def load_corpus(path: Path, root: Path) -> dict:
    manifest = json.loads(path.read_text())
    if (
        manifest.get("schema_version") != 1
        or manifest.get("scope") != "isolated-legacy-headers"
    ):
        raise b.BaselineError("unsupported legacy header corpus")
    ids = set()
    for case in manifest["cases"]:
        name = case["id"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or name in ids:
            raise b.BaselineError("invalid or duplicate legacy case ID")
        ids.add(name)
        header = b.contained(root, case["header"])
        if any(character in str(header) for character in ('"', "\n", "\r", "\\")):
            raise b.BaselineError("header path cannot be represented in a C++ include")
        if not header.is_file():
            raise b.BaselineError(f"missing header: {case['header']}")
    if not ids:
        raise b.BaselineError("empty legacy corpus")
    groups = set()
    for group in manifest["artifacts"]:
        if group["id"] in groups or not group["patterns"]:
            raise b.BaselineError("duplicate or empty legacy artifact group")
        groups.add(group["id"])
        for pattern in group["patterns"]:
            if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
                raise b.BaselineError("legacy artifact pattern escapes workspace")
    if not groups:
        raise b.BaselineError("empty legacy artifact specification")
    return manifest


def environment(root: Path, compiler: Path) -> dict:
    # Do not let local exclusion/annotation policies silently change the corpus.
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("TRICK_")
        and key not in ("CPATH", "CPLUS_INCLUDE_PATH", "C_INCLUDE_PATH")
    }
    env.update(TRICK_HOME=str(root), TRICK_CXX=str(compiler), LC_ALL="C", LANG="C")
    return env


def source_fingerprints(root: Path, manifest: dict) -> dict:
    paths = set((root / "trick_source/codegen/Interface_Code_Gen").glob("*"))
    paths.update([
        root / "trick_source/sim_services/UdUnits/map_trick_units_to_udunits.cpp",
        root / "include/trick/map_trick_units_to_udunits.hh",
        root / "bin/trick-gte",
        root / "libexec/trick/pm/gte.pm",
    ])
    for case in manifest["cases"]:
        # Sibling headers include Foo.hh in the template case. This is explicit
        # source evidence, not a claim to cover all system/transitive inputs.
        paths.update((root / case["header"]).parent.glob("*"))
    return {
        path.relative_to(root).as_posix(): b.digest(path.read_bytes())
        for path in sorted(paths)
        if path.is_file()
    }


def run_pass(
    manifest: dict,
    case: dict,
    root: Path,
    work: Path,
    output: Path,
    command: list[str],
    env: dict,
    label: str,
) -> int:
    before = b.collect_artifacts(manifest, root, work, required=False)
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "schema_version": 1,
        "scope": "isolated-legacy-headers",
        "case": case["id"],
        "stage": "icg",
        "label": label,
        "status": "incomplete",
    }
    b.write_changed(output / "report.json", b.json_bytes(report))
    report["measurement"] = b.measure(command, work, output, env=env)
    if report["measurement"]["returncode"] != 0:
        report["status"] = "command_failed"
        b.write_changed(output / "report.json", b.json_bytes(report))
        return 3
    try:
        after = b.collect_artifacts(manifest, root, work)
    except (b.BaselineError, OSError, UnicodeError) as exc:
        report.update(status="capture_failed", error=str(exc))
        b.write_changed(output / "report.json", b.json_bytes(report))
        raise
    report.update(
        status="success",
        generated_files=len(after),
        generated_bytes=sum(a["bytes"] for a in after.values()),
        churn=b.churn(before, after),
        observed_artifacts={
            name: {key: item[key] for key in ("raw_sha256", "bytes", "mtime_ns")}
            for name, item in after.items()
        },
    )
    for item in after.values():
        b.write_changed(
            output / "objects" / f"{item['sha256']}.txt", item["text"].encode()
        )
    b.write_changed(
        output / "snapshot.json", b.json_bytes(b.snapshot(manifest, case, after))
    )
    b.write_changed(output / "report.json", b.json_bytes(report))
    return 0


def capture(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    if not re.fullmatch(r"[/\w.+-]+", str(root), flags=re.ASCII):
        raise b.BaselineError("legacy checkout path is not shell-safe")
    manifest = load_corpus(args.manifest, root)
    build = args.build_dir.resolve()
    icg = build / "trick-ICG-baseline"
    if not icg.is_file():
        raise b.BaselineError(f"missing evidence-only legacy binary: {icg}")
    compiler_name = shutil.which(args.compiler)
    if compiler_name is None:
        raise b.BaselineError(f"cannot find compiler: {args.compiler}")
    compiler = Path(compiler_name).absolute()
    # Legacy HeaderSearchDirs invokes the compiler through a shell. Do not pass
    # shell syntax (including whitespace) into that existing implementation.
    if not re.fullmatch(r"[/\w.+-]+", str(compiler), flags=re.ASCII):
        raise b.BaselineError("legacy compiler path is not shell-safe")
    for path in (root, args.output.absolute()):
        if any(character in str(path) for character in ('"', "\n", "\r", "\\")):
            raise b.BaselineError("path cannot be represented in a C++ include")
    env = environment(root, compiler)
    xml = args.udunits_xml.resolve()
    if not xml.is_file():
        raise b.BaselineError(f"missing UDUNITS database: {xml}")
    env["UDUNITS2_XML_PATH"] = str(xml)
    build_files = {
        name: (build / name).read_bytes()
        for name in ("build-info.txt", "CMakeCache.txt", "compile_commands.json")
    }
    provenance = {
        "git_revision": subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip(),
        "git_status": subprocess.check_output(
            ["git", "-C", str(root), "status", "--porcelain"], text=True
        ).strip(),
        "source_sha256": source_fingerprints(root, manifest),
        "manifest_sha256": b.digest(args.manifest.read_bytes()),
        "binary_sha256": b.digest(icg.read_bytes()),
        "build_file_sha256": {name: b.digest(raw) for name, raw in build_files.items()},
        "compiler_version": subprocess.check_output(
            [str(compiler), "--version"], env=env, text=True
        ),
        "environment": {key: env[key] for key in b.ENVIRONMENT if key in env},
        "udunits_xml_path": env.get("UDUNITS2_XML_PATH"),
        "udunits_sibling_xml_sha256": {
            path.name: b.digest(path.read_bytes())
            for path in sorted(xml.parent.glob("*.xml"))
        },
        "python": sys.version,
        "platform": sys.platform,
    }
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    summary = {
        "schema_version": 1,
        "scope": "isolated-legacy-headers",
        "status": "incomplete",
        "provenance": provenance,
        "cases": {},
    }
    b.write_changed(output / "summary.json", b.json_bytes(summary))
    for name, raw in build_files.items():
        b.write_changed(output / "build" / name, raw)
    for case in manifest["cases"]:
        work = output / "work" / case["id"]
        (work / "build").mkdir(parents=True)
        tu = work / "input.cpp"
        b.write_changed(tu, f'#include "{root / case["header"]}"\n'.encode())
        command = [str(icg), "-m", "--icg-std=c++17", str(tu)]
        case_output = output / case["id"]
        result = {}
        summary["cases"][case["id"]] = result
        for label in PASSES:
            code = run_pass(
                manifest,
                case,
                root,
                work,
                case_output / label,
                command + (["--force"] if label == "forced" else []),
                env,
                label,
            )
            result[label] = "success" if code == 0 else "command_failed"
            b.write_changed(output / "summary.json", b.json_bytes(summary))
            if code:
                summary["status"] = "command_failed"
                b.write_changed(output / "summary.json", b.json_bytes(summary))
                return code
        for label in ("warm", "forced"):
            result[f"cold_{label}_equal"] = compare_to_file(
                case_output / "cold/snapshot.json",
                case_output / label / "snapshot.json",
                case_output / f"cold-{label}.diff",
            )
        if args.reference:
            for label in PASSES:
                result[f"{label}_reference_equal"] = compare_to_file(
                    args.reference / case["id"] / f"{label}.json",
                    case_output / label / "snapshot.json",
                    case_output / f"{label}-reference.diff",
                )
        b.write_changed(output / "summary.json", b.json_bytes(summary))
    equal = all(
        value
        for result in summary["cases"].values()
        for key, value in result.items()
        if key.endswith("_reference_equal")
    )
    summary["status"] = "success" if equal else "different"
    b.write_changed(output / "summary.json", b.json_bytes(summary))
    print(output / "summary.json")
    return 0 if equal else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--compiler", default="c++")
    parser.add_argument("--udunits-xml", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args(argv)
    try:
        return capture(args)
    except (
        b.BaselineError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"icg-legacy-baseline: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
