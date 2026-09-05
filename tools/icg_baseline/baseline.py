#!/usr/bin/env python3
"""Phase 0 legacy codegen evidence collector; Python 3.11+, standard library only."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

VERSION = 1
HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[1]
# Explicit allowlist: do not serialize arbitrary environment variables/secrets.
ENVIRONMENT = (
    "PATH",
    "CC",
    "CXX",
    "LLVM_HOME",
    "JAVA_HOME",
    "MAKEFLAGS",
    "CPATH",
    "CPLUS_INCLUDE_PATH",
    "C_INCLUDE_PATH",
    "LIBRARY_PATH",
    "LD_LIBRARY_PATH",
    "SDKROOT",
    "LANG",
    "LC_ALL",
    "SOURCE_DATE_EPOCH",
    "TRICK_HOME",
    "TRICK_CC",
    "TRICK_CXX",
    "TRICK_CFLAGS",
    "TRICK_CXXFLAGS",
    "TRICK_SYSTEM_CFLAGS",
    "TRICK_SYSTEM_CXXFLAGS",
    "TRICK_ICGFLAGS",
    "TRICK_CPFLAGS",
    "TRICK_SFLAGS",
    "TRICK_SYSTEM_SFLAGS",
    "TRICK_ICG_EXCLUDE",
    "TRICK_SYSTEM_ICG_EXCLUDE",
    "TRICK_EXCLUDE",
    "TRICK_EXT_LIB_DIRS",
    "TRICK_EXT_LIB_DIRS_OVERRIDES",
    "TRICK_ICG_NOCOMMENT",
    "TRICK_ICG_COMPAT15",
    "TRICK_ICG_IGNORE_TYPES",
    "TRICK_SWIG_EXCLUDE",
    "TRICK_CONVERT_SWIG_FLAGS",
)


class BaselineError(Exception):
    """Invalid or incomplete evidence (CLI exit 2)."""


def json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode()


def write_changed(path: Path, data: bytes) -> None:
    """Atomic replacement; identical bytes leave the file and its mtime alone."""
    if path.exists() and path.read_bytes() == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            name = stream.name
            stream.write(data)
        os.replace(name, path)
    finally:
        if name is not None and os.path.exists(name):
            os.unlink(name)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def contained(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise BaselineError(f"path escapes root: {relative}")
    return path


def load_manifest(path: Path, root: Path) -> dict:
    manifest = json.loads(path.read_text())
    if manifest.get("schema_version") != VERSION:
        raise BaselineError("unsupported corpus schema_version")
    cases = manifest.get("cases", [])
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise BaselineError("corpus cases must be nonempty and have unique IDs")
    for case in cases:
        sim = contained(root, case["directory"])
        if not (sim / "S_define").is_file():
            raise BaselineError(f"missing S_define for {case['id']}: {sim}")
    groups = manifest.get("artifacts", [])
    if not groups or len({group["id"] for group in groups}) != len(groups):
        raise BaselineError("artifact groups must be nonempty and have unique IDs")
    for group in groups:
        if not group["patterns"]:
            raise BaselineError(f"empty artifact group: {group['id']}")
        for pattern in group["patterns"]:
            if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
                raise BaselineError(f"artifact glob escapes simulation: {pattern}")
    return manifest


def normalize(text: str, root: Path, sim: Path) -> str:
    """Replace only configured absolute roots, longest first; retain all other text."""
    roots = {str(root.resolve()): "${TRICK_ROOT}", str(sim.resolve()): "${SIM_ROOT}"}
    pattern = "|".join(re.escape(p) for p in sorted(roots, key=len, reverse=True))
    # A boundary prevents /tmp/trick from also masking /tmp/trick-other.
    return re.sub(f"({pattern})(?=/|$|[\\s\"':])", lambda m: roots[m[1]], text)


def collect(manifest: dict, root: Path, case: dict, *, required: bool = True) -> dict:
    sim = contained(root, case["directory"])
    artifacts = {}
    for group in manifest["artifacts"]:
        matches = sorted({
            p for glob in group["patterns"] for p in sim.glob(glob) if p.is_file()
        })
        if required and group.get("required", False) and not matches:
            raise BaselineError(f"missing required artifact group: {group['id']}")
        for path in matches:
            if not path.resolve().is_relative_to(sim):
                raise BaselineError(f"artifact symlink escapes simulation: {path}")
            raw = path.read_bytes()
            # Fail on unexpected binary output instead of silently losing bytes.
            text = normalize(raw.decode("utf-8"), root, sim)
            name = normalize(path.relative_to(sim).as_posix(), root, sim)
            if name in artifacts:
                raise BaselineError(
                    f"overlapping artifact patterns or normalized path: {name}"
                )
            artifacts[name] = {
                "group": group["id"],
                "text": text,
                "sha256": digest(text.encode()),
                "raw_sha256": digest(raw),
                "bytes": len(raw),
                "mtime_ns": path.stat().st_mtime_ns,
            }
    return artifacts


def churn(before: dict, after: dict) -> dict:
    common = before.keys() & after.keys()
    changed = sorted(
        k for k in common if before[k]["raw_sha256"] != after[k]["raw_sha256"]
    )
    rewritten = sorted(
        k
        for k in common
        if before[k]["raw_sha256"] == after[k]["raw_sha256"]
        and before[k]["mtime_ns"] != after[k]["mtime_ns"]
    )
    return {
        "added": sorted(after.keys() - before.keys()),
        "removed": sorted(before.keys() - after.keys()),
        "content_changed": changed,
        "rewritten_unchanged": rewritten,
    }


def provenance(root: Path, case: dict, manifest_path: Path) -> dict:
    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(root), *args], text=True
        ).strip()

    # Hash the tracked simulation inputs, including local edits. This is a corpus
    # fingerprint, NOT a complete transitive dependency/cache key.
    paths = (
        subprocess
        .check_output([
            "git",
            "-C",
            str(root),
            "ls-files",
            "-z",
            "--",
            case["directory"],
        ])
        .decode()
        .split("\0")
    )
    inputs = {
        p: digest((root / p).read_bytes()) if (root / p).is_file() else None
        for p in paths
        if p
    }
    return {
        "git_revision": git("rev-parse", "HEAD"),
        "git_status": git("status", "--porcelain", "--untracked-files=normal"),
        "tracked_simulation_inputs": inputs,
        "manifest_sha256": digest(manifest_path.read_bytes()),
        "python": sys.version,
        "platform": platform.platform(),
        "root": str(root),
        "simulation": str(contained(root, case["directory"])),
        "environment": {
            key: os.environ[key] for key in ENVIRONMENT if key in os.environ
        },
    }


def snapshot(manifest: dict, case: dict, artifacts: dict) -> dict:
    # Volatile measurement data belongs in report.json, never snapshot.json.
    return {
        "schema_version": VERSION,
        "normalization_version": VERSION,
        "case": case["id"],
        "artifact_spec": manifest["artifacts"],
        "artifacts": {
            k: {field: value[field] for field in ("group", "text", "sha256")}
            for k, value in sorted(artifacts.items())
        },
    }


def measure(command: list[str], cwd: Path, output: Path) -> dict:
    """Use a fresh worker so RUSAGE_CHILDREN cannot include earlier measurements."""
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "_measure",
            str(cwd),
            str(output),
            *command,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def measurement_worker(cwd: str, output: str, command: list[str]) -> int:
    import resource  # Unix only; kept out of snapshot/comparison paths.

    start = time.perf_counter()
    error = None
    with (
        (Path(output) / "stdout.log").open("wb") as stdout,
        (Path(output) / "stderr.log").open("wb") as stderr,
    ):
        try:
            process = subprocess.run(
                command, cwd=cwd, stdout=stdout, stderr=stderr, check=False
            )
            returncode = process.returncode
        except OSError as exc:
            error = str(exc)
            returncode = 127
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    rss_factor = 1 if sys.platform == "darwin" else 1024
    print(
        json.dumps({
            "argv": command,
            "cwd": cwd,
            "returncode": returncode,
            "error": error,
            "wall_seconds": time.perf_counter() - start,
            "user_seconds": usage.ru_utime,
            "system_seconds": usage.ru_stime,
            "max_rss_bytes": usage.ru_maxrss * rss_factor,
            "rss_scope": "waited-for child process high-water mark; not aggregate concurrent RSS",
        })
    )
    return 0


def compare(old_path: Path, new_path: Path) -> int:
    old, new = (json.loads(p.read_text()) for p in (old_path, new_path))
    for value in (old, new):
        if (
            value.get("schema_version") != VERSION
            or value.get("normalization_version") != VERSION
        ):
            raise BaselineError("unsupported snapshot version")
        if not value.get("artifacts"):
            raise BaselineError("empty snapshot is not compatibility evidence")
        for artifact in value["artifacts"].values():
            if artifact["sha256"] != digest(artifact["text"].encode()):
                raise BaselineError("snapshot content digest mismatch")
    if old["case"] != new["case"] or old["artifact_spec"] != new["artifact_spec"]:
        raise BaselineError(
            "snapshots must use the same case and artifact specification"
        )
    different = False
    for name in sorted(old["artifacts"].keys() | new["artifacts"].keys()):
        left, right = old["artifacts"].get(name), new["artifacts"].get(name)
        if left == right:
            continue
        different = True
        if left is None or right is None:
            print(f"{'added' if left is None else 'removed'}: {name}")
        else:
            print(f"changed: {name}")
            sys.stdout.writelines(
                difflib.unified_diff(
                    left["text"].splitlines(keepends=True),
                    right["text"].splitlines(keepends=True),
                    fromfile=f"old/{name}",
                    tofile=f"new/{name}",
                )
            )
    return int(different)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--manifest", type=Path, default=HERE / "corpus.json")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("list", help="validate and list the checked-in corpus")
    for action in ("capture", "run"):
        sub = commands.add_parser(action)
        sub.add_argument("--case", required=True)
        sub.add_argument(
            "--output", type=Path, required=True, help="new directory for evidence"
        )
        if action == "run":
            sub.add_argument(
                "--stage",
                required=True,
                help="e.g. build, icg, generated-compile, link",
            )
            sub.add_argument(
                "--label",
                required=True,
                help="e.g. cold or warm; no cleanup is implied",
            )
            sub.add_argument(
                "command", nargs=argparse.REMAINDER, help="command argv after --"
            )
    diff = commands.add_parser("compare")
    diff.add_argument("old", type=Path)
    diff.add_argument("new", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.action == "compare":
            return compare(args.old, args.new)
        root = args.root.resolve()
        manifest = load_manifest(args.manifest, root)
        if args.action == "list":
            for case in manifest["cases"]:
                print(
                    f"{case['id']}: {case['directory']} ({', '.join(case['covers'])})"
                )
            return 0
        case = next((c for c in manifest["cases"] if c["id"] == args.case), None)
        if case is None:
            raise BaselineError(f"unknown corpus case: {args.case}")
        command = []
        if args.action == "run":
            command = args.command[1:] if args.command[:1] == ["--"] else args.command
            if not command:
                raise BaselineError("run requires a command after --")
            if sys.platform not in ("linux", "darwin"):
                raise BaselineError("resource measurement supports Linux and macOS")
        sim = contained(root, case["directory"])
        output = args.output.resolve()
        if output.is_relative_to(sim):
            raise BaselineError("store evidence outside the measured simulation")
        report = {
            "schema_version": VERSION,
            "case": case["id"],
            "status": "incomplete",
            "provenance": provenance(root, case, args.manifest),
        }
        if command:
            report.update(
                stage=args.stage, label=args.label, argv=command, cwd=str(sim)
            )
        before = collect(manifest, root, case, required=False) if command else {}
        output.mkdir(parents=True, exist_ok=False)
        # A failed/interrupted run must not leave an apparently successful snapshot.
        write_changed(output / "report.json", json_bytes(report))
        if command:
            report["measurement"] = measure(command, sim, output)
            if report["measurement"]["returncode"] != 0:
                report["status"] = "command_failed"
                write_changed(output / "report.json", json_bytes(report))
                print(f"command failed; see {output / 'report.json'}", file=sys.stderr)
                return 3
        try:
            after = collect(manifest, root, case)
        except (BaselineError, OSError, UnicodeError) as exc:
            report.update(status="capture_failed", error=str(exc))
            write_changed(output / "report.json", json_bytes(report))
            raise
        report.update(
            status="success",
            generated_files=len(after),
            generated_bytes=sum(a["bytes"] for a in after.values()),
            observed_artifacts={
                k: {f: a[f] for f in ("raw_sha256", "bytes", "mtime_ns")}
                for k, a in after.items()
            },
        )
        if command:
            report["churn"] = churn(before, after)
        write_changed(
            output / "snapshot.json", json_bytes(snapshot(manifest, case, after))
        )
        write_changed(output / "report.json", json_bytes(report))
        print(output / "snapshot.json")
        return 0
    except (
        BaselineError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"icg-baseline: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    if sys.version_info < (3, 11):
        sys.exit("icg-baseline requires Python 3.11 or newer")
    if len(sys.argv) > 1 and sys.argv[1] == "_measure":
        sys.exit(measurement_worker(sys.argv[2], sys.argv[3], sys.argv[4:]))
    sys.exit(main())
