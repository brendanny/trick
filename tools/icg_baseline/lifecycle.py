#!/usr/bin/env python3
"""Check captured lifecycle wrappers against facts and real C++ operations.

This is a six-record evidence contract, not a general lifecycle-policy emitter.
"""

from __future__ import annotations

import argparse
import difflib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import baseline as b
import differential as d
import native

HERE = Path(__file__).with_suffix("")
HEADER = HERE / "fixtures/Lifecycle.hh"
DEFINITIONS = HERE / "fixtures/Lifecycle.cpp"
SCHEMA = json.loads(
    (
        d.ROOT / "trick_source/codegen/TrickCodeGen/ir/extracted-facts.schema.json"
    ).read_text()
)
NAMES = tuple(
    "IcgLifecycle" + name
    for name in (
        "Tracked",
        "Implicit",
        "Deleted",
        "NoDefault",
        "PrivateDestructor",
        "Abstract",
    )
)


def reference() -> str:
    provenance = json.loads((HERE / "reference/provenance.json").read_text())
    for path in (HEADER, DEFINITIONS):
        if (
            b.digest(path.read_bytes())
            != provenance["source_sha256"][path.relative_to(d.ROOT).as_posix()]
        ):
            raise ValueError("lifecycle fixture differs from captured source")
    if b.digest((HERE / "corpus.json").read_bytes()) != provenance["manifest_sha256"]:
        raise ValueError("lifecycle corpus differs from captured manifest")
    snapshot = HERE / "reference/lifecycle/cold.json"
    metadata = [
        item
        for item in json.loads(snapshot.read_text())["artifacts"].values()
        if item["group"] == "legacy-metadata"
    ]
    if len(metadata) != 1:
        raise ValueError("expected one captured lifecycle translation unit")
    return b.artifact_text(snapshot, metadata[0])


def policies(document: dict) -> dict:
    declarations = {node["id"]: node for node in document["declarations"]}
    records = {
        node["qualified_name"]: node
        for node in declarations.values()
        if node["kind"] == "record"
    }
    if set(records) != set(NAMES) or len(records) != sum(
        node["kind"] == "record" for node in declarations.values()
    ):
        raise ValueError("unexpected lifecycle record set")

    def member(record: dict, kind: str) -> dict:
        slot = next(item for item in record["special_members"] if item["kind"] == kind)
        if slot["state"] == "suppressed":
            return dict(
                available=False, reason_code="NO_DECLARED_SPECIAL_MEMBER", virtual=False
            )
        if slot["state"] == "implicit":
            deleted, access, virtual = slot["deleted"], "public", slot["virtual"]
        elif slot["state"] == "user_declared" and len(slot["declaration_ids"]) == 1:
            declaration = declarations[slot["declaration_ids"][0]]
            deleted, access, virtual = (
                declaration["deleted"],
                declaration["access"],
                declaration["virtual"],
            )
        else:
            raise ValueError("unsupported lifecycle special-member state")
        reason = (
            "DELETED_SPECIAL_MEMBER"
            if deleted
            else "NON_PUBLIC_SPECIAL_MEMBER"
            if access != "public"
            else "SUPPORTED"
        )
        return dict(
            available=reason == "SUPPORTED", reason_code=reason, virtual=virtual
        )

    result = {}
    for name in NAMES:
        node = records[name]
        constructor = member(node, "default_constructor")
        destructor = member(node, "destructor")
        placement = constructor["available"] and not node["abstract"]
        result[name] = dict(
            default_constructor=constructor,
            destructor=destructor,
            default_placement=placement,
            placement_reason_code="ABSTRACT_RECORD"
            if node["abstract"]
            else constructor["reason_code"],
            # Legacy POD allocation is raw storage, including deleted-default PODs.
            allocate="raw_storage"
            if node["pod"]
            else "construct"
            if placement
            else "absent",
            destruct="absent"
            if not destructor["available"]
            else "noop"
            if node["pod"]
            else "loop",
            delete="absent"
            if not destructor["available"]
            else "noop"
            if node["pod"]
            else "scalar",
        )
    return result


def validate(document: dict, observed: dict) -> dict:
    policy = policies(document)
    records = {
        node["qualified_name"]: node
        for node in document["declarations"]
        if node["kind"] == "record"
    }
    expected_records = []
    for name in NAMES:
        node, rule = records[name], policy[name]
        expected_records.append(
            dict(
                name=name,
                size_bytes=int(node["size_bits"]) // 8,
                pod=node["pod"],
                abstract=node["abstract"],
                default_placement=rule["default_placement"],
                default_constructible=rule["default_placement"]
                and rule["destructor"]["available"],
                destructible=rule["destructor"]["available"],
                virtual_destructor=rule["destructor"]["virtual"],
                symbols={
                    key: rule[key] != "absent"
                    for key in ("allocate", "destruct", "delete")
                },
            )
        )
    if observed.get("records") != expected_records:
        difference = "\n".join(
            difflib.unified_diff(
                json.dumps(expected_records, indent=2, sort_keys=True).splitlines(),
                json.dumps(
                    observed.get("records"), indent=2, sort_keys=True
                ).splitlines(),
                fromfile="facts",
                tofile="native probe",
                lineterm="",
            )
        )
        raise ValueError(
            "lifecycle symbols or exact-operation traits differ from facts:\n"
            + difference
        )

    def event(kind, value, offset=0):
        return dict(kind=kind, value=value, offset_bytes=offset)

    def execution(name, operation, count, initial, events, zeroed=False):
        return dict(
            name="IcgLifecycle" + name,
            operation=operation,
            count=count,
            initial=initial,
            events=events,
            zeroed=zeroed,
        )

    # Values/events belong to the digest-checked fixture definitions; they are
    # not extracted initializer/body facts. Sizes/strides come from the facts.
    expected = []
    for count in (1, 3):
        for suffix, initial, constructor in (
            ("Tracked", 41, True),
            ("Implicit", 17, False),
        ):
            stride = int(records["IcgLifecycle" + suffix]["size_bits"]) // 8
            events = (
                [event(1, initial, i * stride) for i in range(count)]
                if constructor
                else []
            )
            events += [event(2, 101 + i, i * stride) for i in range(count)]
            expected.append(
                execution(
                    suffix, "allocate_destruct_free", count, [initial] * count, events
                )
            )
        expected.append(
            execution("Deleted", "raw_storage_noops_free", count, [], [], True)
        )
        stride = int(records["IcgLifecycleNoDefault"]["size_bits"]) // 8
        events = [event(1, 61 + i, i * stride) for i in range(count)]
        events += [event(2, 101 + i, i * stride) for i in range(count)]
        expected.append(
            execution(
                "NoDefault",
                "explicit_construct_destruct_free",
                count,
                list(range(61, 61 + count)),
                events,
            )
        )
    for suffix, initial, constructor in (
        ("Tracked", 41, True),
        ("Implicit", 17, False),
        ("NoDefault", 61, True),
    ):
        events = [event(1, initial)] if constructor else []
        expected.append(
            execution(
                suffix, "new_scalar_delete", 1, [initial], events + [event(2, 201)]
            )
        )
    expected.append(
        execution(
            "Abstract", "derived_new_base_delete", 1, [], [event(3, 0), event(2, 0)]
        )
    )
    if set(observed) != {"records", "executions"} or observed["executions"] != expected:
        raise ValueError(
            "lifecycle event order, count, value, stride, or raw-storage behavior differs"
        )
    return policy


def check(
    document: dict,
    legacy: str,
    output: Path,
    compiler: Path,
    *,
    sanitize: bool = False,
    leak_check: bool = False,
    source_name: str = "legacy.cpp",
) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "lifecycle.json"
    report_path.unlink(missing_ok=True)
    if leak_check and (not sanitize or sys.platform != "linux"):
        raise ValueError("leak checks require the sanitized Linux probe")
    d.ir.validate(SCHEMA, document)
    policies(document)
    if any(ch in str(d.ROOT) for ch in ('"', "\\", "\r", "\n")):
        raise ValueError("repository path cannot be represented in a C++ include")
    materialized = legacy.replace("${TRICK_ROOT}", str(d.ROOT))
    if "${" in materialized:
        raise ValueError("unresolved normalization token in lifecycle source")
    if source_name not in ("legacy.cpp", "candidate.cpp"):
        raise ValueError("unexpected lifecycle source name")
    (output / source_name).write_text(materialized)
    (output / "native_probe.hh").write_bytes(native.HELPER.read_bytes())
    (output / "probe.cpp").write_text(
        (HERE / "probe.cpp")
        .read_text()
        .replace('#include "legacy.cpp"', f'#include "{source_name}"')
    )
    sanitizer_flags = (
        (
            "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all",
            "-fno-omit-frame-pointer",
        )
        if sanitize
        else ()
    )
    # Export actual C symbols for the same named lookup used by MemoryManager.
    export_flags = (
        ("-Wl,-export_dynamic",) if sys.platform == "darwin" else ("-rdynamic", "-ldl")
    )
    runtime_environment = (
        {
            "ASAN_OPTIONS": "alloc_dealloc_mismatch=1:abort_on_error=1:detect_leaks="
            + ("1" if leak_check else "0"),
            "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1",
        }
        if sanitize
        else {}
    )
    evidence = native.execute(
        [
            output / "probe.cpp",
            DEFINITIONS,
            d.ROOT / "trick_source/sim_services/UnitsMap/UnitsMap.cpp",
        ],
        output,
        compiler,
        compile_flags=sanitizer_flags,
        link_flags=export_flags + sanitizer_flags,
        runtime_environment=runtime_environment,
    )
    policy = validate(document, evidence["observations"])
    evidence.update(
        policy=policy,
        graph_digest=document["provenance"]["graph_digest"],
        source_name=source_name,
        source_sha256=b.digest(legacy.encode()),
        sanitizers=list(sanitizer_flags),
        leak_check=leak_check,
        not_executed={
            "IcgLifecyclePrivateDestructor.allocate": "NON_PUBLIC_SPECIAL_MEMBER",
            "IcgLifecycleAbstract.destruct": "ABSTRACT_RECORD",
        },
        not_covered=[
            "zero/negative counts",
            "allocation failure",
            "throwing constructors/destructors",
            "over-alignment",
            "MemoryManager registration/dispatch",
            "general lifecycle policy",
        ],
    )
    if source_name == "legacy.cpp":
        evidence["legacy_sha256"] = evidence["source_sha256"]
    evidence["input_sha256"][str(Path(__file__))] = b.digest(
        Path(__file__).read_bytes()
    )
    report_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return evidence


def capture(
    extractor: Path,
    compiler: Path,
    output: Path,
    *,
    sanitize: bool = False,
    leak_check: bool = False,
) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    (output / "lifecycle.json").unlink(missing_ok=True)
    legacy = reference()
    result = subprocess.run(
        [
            str(extractor),
            "--source-root",
            str(d.ROOT),
            "--diagnostics-format=json",
            str(HEADER),
            "--",
        ],
        capture_output=True,
        check=False,
        timeout=30,
    )
    (output / "facts.json").write_bytes(result.stdout)
    (output / "diagnostics.json").write_bytes(result.stderr)
    result.check_returncode()
    document = json.loads(result.stdout)
    inputs = [
        node
        for node in document["files"]
        if node["path"]["root"] == "source"
        and node["path"]["portable"] == HEADER.relative_to(d.ROOT).as_posix()
    ]
    if len(inputs) != 1 or inputs[0]["digest"] != b.digest(HEADER.read_bytes()):
        raise ValueError("lifecycle extraction differs from captured input")
    return check(
        document, legacy, output, compiler, sanitize=sanitize, leak_check=leak_check
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extractor", type=Path, required=True)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sanitize", action="store_true")
    parser.add_argument(
        "--leak-check", action="store_true", help="also enable Linux LeakSanitizer"
    )
    args = parser.parse_args()
    compiler = shutil.which(args.compiler)
    if not compiler:
        parser.error(f"C++ compiler not found: {args.compiler}")
    capture(
        args.extractor.resolve(strict=True),
        Path(compiler).absolute(),
        args.output,
        sanitize=args.sanitize or args.leak_check,
        leak_check=args.leak_check,
    )
