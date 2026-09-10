"""Validate configured MemoryManager observations against the lifecycle facts."""

from __future__ import annotations

import difflib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

import baseline as b

INPUTS = (
    "tools/icg_baseline/lifecycle/fixtures/Lifecycle.hh",
    "tools/icg_baseline/lifecycle/fixtures/Lifecycle.cpp",
)


def lifecycle_overlay(original: str, candidate: str, expected_symbols: set[str]) -> str:
    """Keep legacy metadata while removing its lifecycle exports from lookup.

    This is an isolated test overlay, never a production generation backend.
    Renamed legacy helpers cannot satisfy MemoryManager's original C-symbol names.
    """
    pattern = r"\bio_src_(?:allocate|destruct|delete)_IcgLifecycle\w+\b"
    found = set(re.findall(pattern, original))
    if found != expected_symbols:
        raise b.BaselineError(
            "legacy lifecycle exports differ from the audited overlay"
        )
    if "icg_baseline_legacy_io_src_" in original:
        raise b.BaselineError("lifecycle overlay already installed")
    renamed = re.sub(pattern, lambda m: "icg_baseline_legacy_" + m[0], original)
    return (
        renamed
        + "\n// Begin independently generated lifecycle candidate.\n"
        + candidate
    )


def install_candidate(facts_path: Path, sim: Path, output: Path) -> tuple[Path, str]:
    import lifecycle as l
    import lifecycle_codegen

    facts = json.loads(facts_path.read_text())
    output.mkdir(parents=True, exist_ok=False)
    model, candidate = lifecycle_codegen.generate(facts, output)
    expected_symbols = {
        f"io_src_{operation}_{name}"
        for name, rule in l.policies(facts).items()
        for operation in ("allocate", "destruct", "delete")
        if rule[operation] != "absent"
    }
    generated_symbols = {
        d["metadata"]["lifecycle"][operation]["symbol"]
        for d in model["declarations"]
        if d["decision"] == "include"
        for operation in ("allocate", "destruct", "delete")
        if d["metadata"]["lifecycle"][operation]["action"] != "absent"
    }
    if generated_symbols != expected_symbols:
        raise b.BaselineError(
            "candidate lifecycle exports differ from independent facts policy"
        )
    sources = [
        path
        for path in (sim / "build").rglob("io_*.cpp")
        if "io_src_allocate_IcgLifecycleTracked(" in path.read_text()
    ]
    if len(sources) != 1:
        raise b.BaselineError("expected one generated lifecycle source for the overlay")
    target = sources[0]
    original = target.read_text()
    overlay = lifecycle_overlay(original, candidate, expected_symbols)
    (output / "legacy-original.cpp").write_text(original)
    (output / "overlay.cpp").write_text(overlay)
    (output / "overlay.json").write_bytes(
        b.json_bytes(
            dict(
                source=str(target),
                legacy_sha256=b.digest(original.encode()),
                candidate_sha256=b.digest(candidate.encode()),
                overlay_sha256=b.digest(overlay.encode()),
                resolved_digest=model["digest"],
                symbols=sorted(expected_symbols),
            )
        )
    )
    target.write_text(overlay)
    return target, overlay


def extract(extractor: Path, root: Path, output: Path) -> Path:
    import lifecycle as l

    # Reuse exactly the source whose legacy capture and instrumented event
    # definitions were audited; a second checkout must contain identical bytes.
    l.reference()
    for relative in INPUTS:
        if (root / relative).read_bytes() != (l.d.ROOT / relative).read_bytes():
            raise b.BaselineError("MemoryManager corpus differs from captured sources")
    command = [
        str(extractor.resolve(strict=True)),
        "--source-root",
        str(root),
        "--diagnostics-format=json",
        str(root / INPUTS[0]),
        "--",
    ]
    result = subprocess.run(command, capture_output=True, timeout=60, check=False)
    (output / "facts.command.json").write_bytes(b.json_bytes(command))
    facts = output / "facts.json"
    facts.write_bytes(result.stdout)
    (output / "facts.diagnostics.json").write_bytes(result.stderr)
    if result.returncode:
        raise b.BaselineError("MemoryManager corpus extraction failed")
    document = json.loads(result.stdout)
    l.d.ir.validate(l.SCHEMA, document)
    source = [
        node
        for node in document["files"]
        if node["path"]["root"] == "source" and node["path"]["portable"] == INPUTS[0]
    ]
    if len(source) != 1 or source[0]["digest"] != b.digest(
        (root / INPUTS[0]).read_bytes()
    ):
        raise b.BaselineError("MemoryManager facts do not identify the fixture bytes")
    return facts


def validate_logs(text: str) -> None:
    expected = Counter()
    for name in ("IcgLifecycleNoDefault", "IcgLifecycleAbstract"):
        expected.update({
            f"missing allocator: {name}": 1,
            f"MemoryManager:ERROR:io_src_allocate_class ({name},1) failed to allocate any memory.": 1,
        })
    actual = []
    for line in re.sub(r"\x1b\[[0-9;]*m", "", text).splitlines():
        if re.search(
            r"MemoryManager:|\bERROR:|\bWARNING:|Traceback \(|Checkpoint restore failed",
            line,
        ):
            # The dynamic loader prefixes this text with the executable path.
            # Ignore only that path; the exact missing symbol and multiplicity
            # remain part of the negative contract.
            missing = re.fullmatch(
                r'MemoryManager:ERROR:Couldn\'t find function "io_src_allocate_'
                r'(IcgLifecycleNoDefault|IcgLifecycleAbstract)\(\)"\. dlerror= '
                r".+: undefined symbol: io_src_allocate_\1",
                line,
            )
            actual.append("missing allocator: " + missing[1] if missing else line)
    if Counter(actual) != expected:
        raise b.BaselineError(
            "MemoryManager diagnostics differ from the two rejected allocations: "
            + repr(Counter(actual))
        )


def expected(document: dict) -> dict:
    import lifecycle as l

    l.d.ir.validate(l.SCHEMA, document)
    rules = l.policies(document)
    for suffix, allocation, deletion in (
        ("Tracked", "construct", "scalar"),
        ("Implicit", "construct", "scalar"),
        ("Deleted", "raw_storage", "noop"),
        ("NoDefault", "absent", "scalar"),
        ("Abstract", "absent", "scalar"),
    ):
        rule = rules["IcgLifecycle" + suffix]
        if rule["allocate"] != allocation or rule["delete"] != deletion:
            raise b.BaselineError(
                "MemoryManager lifecycle policy differs from the audited corpus"
            )
    records = {
        node["qualified_name"]: node
        for node in document["declarations"]
        if node["kind"] == "record"
    }

    def event(kind, value, offset=0):
        return dict(kind=kind, value=value, offset_bytes=offset, registered=False)

    def execution(
        suffix,
        operation,
        count,
        initial,
        events,
        *,
        storage="local",
        allocator="malloc",
        zeroed=False,
        after=-1,
    ):
        name = "IcgLifecycle" + suffix
        size = int(records[name]["size_bits"]) // 8
        return dict(
            type=name,
            operation=operation,
            allocation=dict(
                type=name,
                size_bytes=size,
                range_bytes=count * size,
                count=count,
                storage=storage,
                allocator=allocator,
                cpp=True,
                structured=True,
                named=True,
                interior_lookup=True,
                dimensions=[] if count == 1 else [count],
            ),
            delete_status=0,
            unregistered=True,
            name_removed=True,
            zeroed=zeroed,
            events_after_unregister=after,
            initial=initial,
            events=events,
        )

    executions = []
    for count in (1, 3):
        for suffix, value, constructor in (
            ("Tracked", 41, True),
            ("Implicit", 17, False),
        ):
            size = int(records["IcgLifecycle" + suffix]["size_bits"]) // 8
            events = (
                [event(1, value, i * size) for i in range(count)] if constructor else []
            )
            events += [event(2, 101 + i, i * size) for i in range(count)]
            executions.append(
                execution(
                    suffix,
                    "declare_delete_name" if count == 1 else "declare_delete_address",
                    count,
                    [value] * count,
                    events,
                )
            )
        executions.append(
            execution(
                "Deleted",
                "raw_delete_name" if count == 1 else "raw_delete_address",
                count,
                [],
                [],
                zeroed=True,
            )
        )
    executions.append(
        execution(
            "Tracked",
            "external_unregister",
            1,
            [301],
            [event(1, 41), event(2, 301)],
            storage="external",
            allocator="other",
            after=1,
        )
    )
    for suffix, initial in (("Tracked", 41), ("NoDefault", 61)):
        executions.append(
            execution(
                suffix,
                "swig_named_delete",
                1,
                [initial],
                [event(1, initial), event(2, 201)],
                allocator="new",
            )
        )
    return dict(
        executions=executions,
        rejections=[
            dict(type="IcgLifecycle" + suffix, null=True, allocation_delta=0, events=0)
            for suffix in ("NoDefault", "Abstract")
        ],
        allocation_delta=0,
    )


def validate(facts: Path, observations: Path) -> dict:
    import lifecycle as l

    l.reference()
    document = json.loads(facts.read_text())
    actual = json.loads(observations.read_text())
    predicted = expected(document)
    if b.json_bytes(actual) != b.json_bytes(predicted):
        difference = "\n".join(
            difflib.unified_diff(
                b.json_bytes(predicted).decode().splitlines(),
                b.json_bytes(actual).decode().splitlines(),
                fromfile="facts and lifecycle contract",
                tofile="MemoryManager",
                lineterm="",
            )
        )
        raise b.BaselineError(
            "MemoryManager observations differ from facts and the lifecycle contract:\n"
            + difference
        )
    return dict(
        memorymanager_sha256=b.digest(observations.read_bytes()),
        graph_digest=document["provenance"]["graph_digest"],
        executions=9,
        rejected_allocations=2,
    )
