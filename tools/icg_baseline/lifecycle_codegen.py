#!/usr/bin/env python3
"""Compare generated lifecycle exports with captured legacy and native behavior."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import lifecycle as baseline

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.icg_emit import emit  # noqa: E402
from tools.icg_policy import resolve  # noqa: E402


def generate(facts: dict, output: Path) -> tuple[dict, str]:
    output.mkdir(parents=True, exist_ok=True)
    request = resolve.request_for(facts, outputs=["lifecycle"])
    model = resolve.resolve(facts, request)
    for name, value in (("request", request), ("resolved", model)):
        (output / f"{name}.json").write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n"
        )
    emit.write(facts, request, model, output / "candidate.cpp")
    return model, (output / "candidate.cpp").read_text()


def capture(
    extractor: Path, compiler: Path, output: Path, *, sanitize=False, leak_check=False
) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    report = output / "comparison.json"
    report.unlink(missing_ok=True)
    old = baseline.capture(
        extractor, compiler, output / "legacy", sanitize=sanitize, leak_check=leak_check
    )
    facts = json.loads((output / "legacy/facts.json").read_text())
    model, source = generate(facts, output / "candidate")
    rules = {
        d["metadata"]["symbol"]: d["metadata"]["lifecycle"]
        for d in model["declarations"]
        if d["decision"] == "include"
    }
    # This oracle derives its own decisions from facts; it does not import the
    # generation policy. The instrumented reference remains immutable.
    for name, rule in baseline.policies(facts).items():
        if any(
            rules[name][op]["action"] != rule[op]
            for op in ("allocate", "destruct", "delete")
        ):
            raise ValueError(
                "generated lifecycle decisions differ from the independent oracle"
            )
    new = baseline.check(
        facts,
        source,
        output / "candidate",
        compiler,
        sanitize=sanitize,
        leak_check=leak_check,
        source_name="candidate.cpp",
    )
    if old["observations"] != new["observations"]:
        raise ValueError("candidate/legacy lifecycle observations differ")
    result = dict(
        status="compared",
        records=len(rules),
        lookups=sum(len(r["symbols"]) for r in new["observations"]["records"]),
        executions=len(new["observations"]["executions"]),
        resolved_digest=model["digest"],
        candidate_sha256=new["source_sha256"],
        legacy_sha256=old["legacy_sha256"],
        sanitizers=new["sanitizers"],
        leak_check=leak_check,
        not_executed=new["not_executed"],
    )
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extractor", type=Path, required=True)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sanitize", action="store_true")
    parser.add_argument("--leak-check", action="store_true")
    args = parser.parse_args()
    compiler = shutil.which(args.compiler)
    if compiler is None:
        parser.error("C++ compiler not found")
    capture(
        args.extractor.resolve(),
        Path(compiler).absolute(),
        args.output.resolve(),
        sanitize=args.sanitize or args.leak_check,
        leak_check=args.leak_check,
    )
