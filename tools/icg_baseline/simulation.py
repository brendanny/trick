#!/usr/bin/env python3
"""Capture a configured SIM_test_templates build and actual Python/runtime behavior."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import baseline as b

HERE = Path(__file__).resolve().parent
CASE = "templates"
DIRECTORY = "test/SIM_test_templates"


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


def validate_runtime(output: Path, expected_path: Path) -> dict:
    actual_path = b.contained(output, "observations.json")
    actual = json.loads(actual_path.read_text())
    expected = json.loads(expected_path.read_text())
    # Compare independently specified values, including the changed state and
    # the scheduled observation time. Equality of before/restored alone is weak.
    if b.json_bytes(actual) != b.json_bytes(expected):
        raise b.BaselineError("runtime observations differ from the expected contract")
    checkpoint = b.contained(output, "icg_model_checkpoint")
    raw = checkpoint.read_bytes()
    text = raw.decode("utf-8")
    for marker in (
        "tso.tobj.TTT_var_scalar_builtins.aa",
        "tso.tobj.TTT_var_array_builtins.aa",
        "tso.tobj.TTT_var_enum.aa",
        "tso.tobj.TTT_var_template_parameters.aa.t",
    ):
        if marker not in text:
            raise b.BaselineError(f"checkpoint is missing {marker}")
    if "clear_all_vars();" in text:
        raise b.BaselineError(
            "object-only checkpoint unexpectedly clears all allocations"
        )
    return {
        "observations_sha256": b.digest(actual_path.read_bytes()),
        "checkpoint_sha256": b.digest(raw),
        "checkpoint_bytes": len(raw),
    }


def runtime(sim: Path, output: Path, env: dict, timeout: str, seconds: int) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    binary = executable(sim)
    env = dict(env, ICG_BASELINE_RESULTS=str(output))
    command = [
        timeout,
        "--kill-after=10s",
        f"{seconds}s",
        str(binary),
        str(HERE / "runtime/templates.py"),
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
            validate_runtime(output, HERE / "runtime/templates.expected.json")
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
    sim = b.contained(root, DIRECTORY)
    manifest = b.load_manifest(HERE / "corpus.json", root)
    case = next(case for case in manifest["cases"] if case["id"] == CASE)
    require_fresh_simulation(sim)
    config = root / "share/trick/makefiles/config_user.mk"
    icg = root / "bin/trick-ICG"
    if not config.is_file() or not icg.is_file():
        raise b.BaselineError("configure and build Trick with make no_dp first")
    output = args.output.resolve()
    if output.is_relative_to(sim):
        raise b.BaselineError("store evidence outside the simulation directory")
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, TRICK_HOME=str(root))
    report = {
        "schema_version": 1,
        "scope": "configured-simulation",
        "case": CASE,
        "status": "incomplete",
        "provenance": b.provenance(root, case, HERE / "corpus.json"),
        "legacy_icg_sha256": b.digest(icg.read_bytes()),
        "runtime_input_sha256": b.digest((HERE / "runtime/templates.py").read_bytes()),
        "expected_sha256": b.digest(
            (HERE / "runtime/templates.expected.json").read_bytes()
        ),
        "stages": {},
    }
    report["provenance"]["environment"] = {
        key: env[key] for key in b.ENVIRONMENT if key in env
    }
    b.write_changed(output / "summary.json", b.json_bytes(report))
    for path in (
        config,
        root / "share/trick/makefiles/config_Linux.mk",
        root / "config.log",
        root / "config.status",
    ):
        if path.is_file():
            b.write_changed(output / "configuration" / path.name, path.read_bytes())
    try:
        for label in ("cold", "warm", "forced", "rebuilt"):
            command = [
                str(root / "bin/trick-CP"),
                f"-j{args.jobs}",
                "TRICK_VERBOSE_BUILD=1",
            ]
            if label == "forced":
                command.append("force_ICG")
            argv = [
                sys.executable,
                str(HERE / "baseline.py"),
                "--root",
                str(root),
                "run",
                "--case",
                CASE,
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
                    sim, output / key, env, timeout, args.runtime_timeout
                )
            b.write_changed(output / "summary.json", b.json_bytes(report))
        for label in ("warm", "forced", "rebuilt"):
            with (output / f"cold-{label}.diff").open("w") as stream:
                with contextlib.redirect_stdout(stream):
                    code = b.compare(
                        output / "cold/snapshot.json", output / label / "snapshot.json"
                    )
            report[f"cold_{label}_equal"] = code == 0
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
