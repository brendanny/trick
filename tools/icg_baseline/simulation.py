#!/usr/bin/env python3
"""Capture configured simulation builds and actual Python/runtime behavior."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import baseline as b

HERE = Path(__file__).resolve().parent
RUNTIME_INPUTS = {
    "templates": ("templates.py",),
    "io": ("io.py", "io.restore_input"),
    "memorymanager": ("memorymanager.py",),
}


def validate_io_logs(text: str) -> None:
    # Only the deliberate permission failures may pass this negative probe.
    # Check message multiplicity too: extra/missing failures are regressions.
    expected = json.loads((HERE / "runtime/io.expected-diagnostics.json").read_text())
    messages = []
    for line in re.sub(r"\x1b\[[0-9;]*m", "", text).splitlines():
        match = re.search(
            r"Checkpoint Agent (?:ERROR|WARNING):.*|ERROR:.*|Cannot assign to .*"
            r"|reference attributes not found .*",
            line,
        )
        if match:
            messages.append(match.group().strip())
    if Counter(messages) != Counter(expected):
        raise b.BaselineError(
            "I/O diagnostics differ from the expected permission failures"
        )


def require_fresh_simulation(sim: Path) -> None:
    generated = [sim / name for name in ("build", "S_source.hh", "S_sie.resource")]
    generated.extend(sim.glob("S_main*"))
    if any(path.exists() or path.is_symlink() for path in generated):
        raise b.BaselineError("simulation has generated output; use a fresh checkout")


def executable(sim: Path) -> Path:
    candidates = [
        path
        for path in sim.glob("S_main*.exe")
        if path.is_file() and os.access(path, os.X_OK)
    ]
    if len(candidates) != 1:
        raise b.BaselineError("expected exactly one built S_main*.exe")
    binary = candidates[0].resolve()
    if not binary.is_relative_to(sim.resolve()):
        raise b.BaselineError("simulation executable escapes its directory")
    return binary


def validate_runtime(
    output: Path,
    expected_path: Path,
    case_id: str = "templates",
    facts: Path | None = None,
) -> dict:
    # Legacy read_checkpoint logs a parser failure but can still return zero.
    logs = "\n".join(
        b.contained(output, name).read_text() for name in ("stdout.log", "stderr.log")
    )
    if "Traceback (most recent call last):" in logs:
        raise b.BaselineError("runtime log contains a Python error")
    if case_id == "io":
        validate_io_logs(logs)
    elif case_id == "memorymanager":
        import memorymanager

        memorymanager.validate_logs(logs)
    elif "Checkpoint restore failed." in logs or "Checkpoint Agent ERROR:" in logs:
        raise b.BaselineError("runtime log contains a checkpoint restore error")
    actual_path = b.contained(output, "observations.json")
    actual = json.loads(actual_path.read_text())
    expected = json.loads(expected_path.read_text())
    # Compare independently specified values, including the changed state and
    # the scheduled observation time. Equality of before/restored alone is weak.
    if b.json_bytes(actual) != b.json_bytes(expected):
        raise b.BaselineError("runtime observations differ from the expected contract")
    if case_id == "memorymanager":
        if facts is None:
            raise b.BaselineError("MemoryManager runtime requires extracted facts")
        return dict(
            observations_sha256=b.digest(actual_path.read_bytes()),
            **memorymanager.validate(facts, b.contained(output, "memorymanager.json")),
        )
    checkpoint = b.contained(output, "icg_model_checkpoint")
    raw = checkpoint.read_bytes()
    text = raw.decode("utf-8")
    if case_id == "io":
        assignments = re.findall(
            r"(?m)^\s*(/\* OUTPUT-ONLY: )?(test_io\.d\d+)\s*=\s*([^;]+);(\*/)?\s*$",
            text,
        )
        expected_assignments = {
            (i < 8, f"test_io.d{i}"): expected["before_checkpoint"][i]
            for i in (4, 5, 6, 7, 12, 13, 14, 15)
        }
        if (
            len(assignments) != len(expected_assignments)
            or any(bool(start) != bool(end) for start, _, _, end in assignments)
            or {
                (bool(start), name): float(value)
                for start, name, value, _ in assignments
            }
            != expected_assignments
        ):
            raise b.BaselineError(
                "checkpoint assignments violate the I/O output contract"
            )
    else:
        for marker in (
            "tso.tobj.TTT_var_scalar_builtins.aa",
            "tso.tobj.TTT_var_array_builtins.aa",
            "tso.tobj.TTT_var_enum.aa",
            "tso.tobj.TTT_var_template_parameters.aa.t",
        ):
            if marker not in text:
                raise b.BaselineError(f"checkpoint is missing {marker}")
    if re.search(r"\bclear_all_vars\s*\(", text):
        raise b.BaselineError(
            "object-only checkpoint unexpectedly clears all allocations"
        )
    return {
        "observations_sha256": b.digest(actual_path.read_bytes()),
        "checkpoint_sha256": b.digest(raw),
        "checkpoint_bytes": len(raw),
    }


def runtime(
    sim: Path,
    output: Path,
    env: dict,
    timeout: str,
    seconds: int,
    case_id: str = "templates",
    facts: Path | None = None,
) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    binary = executable(sim)
    env = dict(env, ICG_BASELINE_RESULTS=str(output))
    if case_id == "io":
        env["ICG_BASELINE_RESTORE_INPUT"] = str(HERE / "runtime/io.restore_input")
    command = [
        timeout,
        "--kill-after=10s",
        f"{seconds}s",
        str(binary),
        str(HERE / f"runtime/{case_id}.py"),
        "-O",
        str(output),
    ]
    report = {"status": "incomplete", "binary_sha256": b.digest(binary.read_bytes())}
    b.write_changed(output / "report.json", b.json_bytes(report))
    report["measurement"] = b.measure(command, sim, output, env=env)
    try:
        if report["measurement"]["returncode"] != 0:
            raise b.BaselineError("simulation command failed or timed out")
        report.update(
            validate_runtime(
                output, HERE / f"runtime/{case_id}.expected.json", case_id, facts
            )
        )
        report["status"] = "success"
    except (b.BaselineError, OSError, ValueError) as exc:
        report.update(status="failed", error=str(exc))
        raise
    finally:
        b.write_changed(output / "report.json", b.json_bytes(report))
    return report


def capture(args: argparse.Namespace) -> int:
    if sys.platform != "linux":
        raise b.BaselineError(
            "this configured simulation lane currently supports Linux"
        )
    timeout = shutil.which("timeout")
    if timeout is None:
        raise b.BaselineError("GNU timeout is required")
    root = args.root.resolve()
    manifest = b.load_manifest(HERE / "corpus.json", root)
    case_id = args.case
    if case_id in ("memorymanager", "templates") and args.extractor is None:
        raise b.BaselineError(f"--case {case_id} requires --extractor")
    case = next(case for case in manifest["cases"] if case["id"] == case_id)
    sim = b.contained(root, case["directory"])
    require_fresh_simulation(sim)
    config = root / "share/trick/makefiles/config_user.mk"
    icg = root / "bin/trick-ICG"
    if not config.is_file() or not icg.is_file():
        raise b.BaselineError("configure and build Trick with make no_dp first")
    output = args.output.resolve()
    if output.is_relative_to(sim):
        raise b.BaselineError("store evidence outside the simulation directory")
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, TRICK_HOME=str(root), MAKEFLAGS=f"-j{args.jobs}")
    report = {
        "schema_version": 1,
        "scope": "configured-simulation",
        "case": case_id,
        "status": "incomplete",
        "provenance": b.provenance(root, case, HERE / "corpus.json"),
        "legacy_icg_sha256": b.digest(icg.read_bytes()),
        "runtime_input_sha256": b.digest((HERE / f"runtime/{case_id}.py").read_bytes()),
        "runtime_inputs": {
            name: b.digest((HERE / "runtime" / name).read_bytes())
            for name in RUNTIME_INPUTS[case_id]
        },
        "expected_sha256": b.digest(
            (HERE / f"runtime/{case_id}.expected.json").read_bytes()
        ),
        "stages": {},
    }
    if case_id == "io":
        report["expected_diagnostics_sha256"] = b.digest(
            (HERE / "runtime/io.expected-diagnostics.json").read_bytes()
        )
    report["provenance"]["environment"] = {
        key: env[key] for key in b.ENVIRONMENT if key in env
    }
    b.write_changed(output / "summary.json", b.json_bytes(report))
    inputs = [*RUNTIME_INPUTS[case_id], f"{case_id}.expected.json"]
    if case_id == "io":
        inputs.append("io.expected-diagnostics.json")
    for name in inputs:
        b.write_changed(
            output / "runtime-inputs" / name, (HERE / "runtime" / name).read_bytes()
        )
    for path in (
        config,
        root / "share/trick/makefiles/config_Linux.mk",
        root / "config.log",
        root / "config.status",
    ):
        if path.is_file():
            b.write_changed(output / "configuration" / path.name, path.read_bytes())
    try:
        facts = None
        if case_id in ("memorymanager", "templates"):
            import memorymanager
            import template_metadata

            candidate_module = (
                memorymanager if case_id == "memorymanager" else template_metadata
            )
            facts = candidate_module.extract(args.extractor, root, output)
            report["extractor_sha256"] = b.digest(args.extractor.read_bytes())
            report[
                "lifecycle_source_sha256"
                if case_id == "memorymanager"
                else "template_source_sha256"
            ] = {
                name: b.digest((root / name).read_bytes())
                for name in candidate_module.INPUTS
            }
            report["comparison_inputs_sha256"] = {
                name: b.digest((HERE / name).read_bytes())
                for name in (
                    ("memorymanager.py", "lifecycle.py")
                    if case_id == "memorymanager"
                    else ("template_metadata.py", "native.py", "native_probe.hh")
                )
            }
        for label in ("cold", "warm", "forced", "rebuilt"):
            # trick-CP forwards unrecognized arguments to the S_define parser.
            # Parallelism belongs in MAKEFLAGS; named targets go to Make.
            command = (
                ["make", "-f", "makefile", "force_ICG", "TRICK_VERBOSE_BUILD=1"]
                if label == "forced"
                else [str(root / "bin/trick-CP"), "TRICK_VERBOSE_BUILD=1"]
            )
            argv = [
                sys.executable,
                str(HERE / "baseline.py"),
                "--root",
                str(root),
                "run",
                "--case",
                case_id,
                "--output",
                str(output / label),
                "--stage",
                "icg-make-target" if label == "forced" else "build",
                "--label",
                label,
                "--",
                timeout,
                "--kill-after=10s",
                f"{args.build_timeout}s",
                *command,
            ]
            code = subprocess.run(argv, env=env, check=False).returncode
            if code != 0:
                raise b.BaselineError(f"{label} build/capture failed (exit {code})")
            executable(sim)  # An artifact-only success cannot stand in for linking.
            report["stages"][label] = "success"
            if label in ("warm", "rebuilt"):
                key = f"runtime-{label}"
                report["stages"][key] = runtime(
                    sim,
                    output / key,
                    env,
                    timeout,
                    args.runtime_timeout,
                    case_id,
                    facts,
                )
            b.write_changed(output / "summary.json", b.json_bytes(report))
        for label in ("warm", "forced", "rebuilt"):
            with (output / f"cold-{label}.diff").open("w") as stream:
                with contextlib.redirect_stdout(stream):
                    code = b.compare(
                        output / "cold/snapshot.json", output / label / "snapshot.json"
                    )
            report[f"cold_{label}_equal"] = code == 0
        if case_id in ("memorymanager", "templates"):
            # Preserve the completed legacy run. The overlay removes old
            # definitions of exactly the candidate's audited ABI entries.
            candidate_kind = "lifecycle" if case_id == "memorymanager" else "templates"
            candidate_output = output / f"candidate-{candidate_kind}"
            target, overlay = candidate_module.install_candidate(
                facts, sim, candidate_output
            )
            old_binary = b.digest(executable(sim).read_bytes())
            command = [
                timeout,
                "--kill-after=10s",
                f"{args.build_timeout}s",
                str(root / "bin/trick-CP"),
                "TRICK_VERBOSE_BUILD=1",
            ]
            (candidate_output / "build.command.json").write_bytes(b.json_bytes(command))
            with (candidate_output / "build.log").open("w") as stream:
                code = subprocess.run(
                    command,
                    cwd=sim,
                    env=env,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    check=False,
                ).returncode
            if code or target.read_text() != overlay:
                raise b.BaselineError(
                    "candidate rebuild failed or regenerated the overlay"
                )
            if b.digest(executable(sim).read_bytes()) == old_binary:
                raise b.BaselineError("candidate executable was not relinked")
            report["stages"]["candidate-build"] = "success"
            report["stages"]["runtime-candidate"] = runtime(
                sim,
                output / "runtime-candidate",
                env,
                timeout,
                args.runtime_timeout,
                case_id,
                facts,
            )
            for name in (
                ("observations.json", "memorymanager.json")
                if case_id == "memorymanager"
                else ("observations.json",)
            ):
                previous = json.loads((output / "runtime-rebuilt" / name).read_text())
                candidate = json.loads(
                    (output / "runtime-candidate" / name).read_text()
                )
                if b.json_bytes(previous) != b.json_bytes(candidate):
                    raise b.BaselineError("candidate runtime differs from legacy")
        # Full generated snapshots are observations, not yet approved portable
        # goldens. Runtime expectations above are the explicit behavioral gate.
        report["status"] = "success"
    except (b.BaselineError, OSError, ValueError) as exc:
        report.update(status="failed", error=str(exc))
        raise
    finally:
        b.write_changed(output / "summary.json", b.json_bytes(report))
    print(output / "summary.json")
    return 0


def positive_integer(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=b.DEFAULT_ROOT)
    parser.add_argument("--case", choices=RUNTIME_INPUTS, default="templates")
    parser.add_argument(
        "--extractor",
        type=Path,
        help="required for template and MemoryManager candidate comparisons",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=positive_integer, default=2)
    parser.add_argument("--build-timeout", type=positive_integer, default=1200)
    parser.add_argument("--runtime-timeout", type=positive_integer, default=60)
    args = parser.parse_args(argv)
    try:
        return capture(args)
    except (b.BaselineError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"icg-simulation-baseline: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
