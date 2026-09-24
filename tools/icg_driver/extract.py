#!/usr/bin/env python3
"""Extract development facts using the selected GCC's parse conditions."""

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
from tools.icg_schema import validate as ir  # noqa: E402

SCHEMA = ROOT / "trick_source/codegen/TrickCodeGen/ir/extracted-facts.schema.json"
PAIRED = {
    "-I",
    "-isystem",
    "-iquote",
    "-D",
    "-U",
    "-include",
    "-imacros",
    "--sysroot",
    "-isysroot",
}
RESERVED = {
    "__GNUC__",
    "__GNUC_MINOR__",
    "__GNUC_PATCHLEVEL__",
    "__cplusplus",
    "__STRICT_ANSI__",
    "__clang__",
}


class DriverError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def arguments(flags):
    """Accept only audited semantic flags; never execute arbitrary driver options."""
    index = 0
    dialect = None
    while index < len(flags):
        flag = flags[index]
        macro = None
        if flag in PAIRED:
            index += 1
            if index == len(flags) or not flags[index] or flags[index].startswith("-"):
                raise DriverError(
                    "ICG_ARGUMENT_VALUE", f"Expected a non-flag value for {flag}"
                )
            if flag in ("-D", "-U"):
                macro = flags[index]
        elif flag in ("-std=c++17", "-std=gnu++17"):
            dialect = flag[5:]
        elif flag in ("-m32", "-m64", "-fno-exceptions", "-fno-rtti"):
            pass
        elif flag.startswith(("-I", "-D", "-U")) and len(flag) > 2:
            if flag[:2] in ("-D", "-U"):
                macro = flag[2:]
        elif flag.startswith("--sysroot=") and len(flag) > 10:
            pass
        elif re.fullmatch(r"-W[A-Za-z0-9_=+.-]+", flag) and not flag.startswith((
            "-Wl,",
            "-Wa,",
            "-Wp,",
        )):
            pass
        else:
            raise DriverError(
                "ICG_UNSUPPORTED_ARGUMENT", f"Unsupported GCC argument: {flag}"
            )
        if macro and re.split(r"[=(]", macro, maxsplit=1)[0] in RESERVED:
            raise DriverError(
                "ICG_COMPILER_MACROS",
                f"Cannot override compiler identity or dialect: {macro}",
            )
        index += 1
    return dialect


def executable(value, env):
    found = shutil.which(str(value), path=env.get("PATH", os.defpath))
    if not found:
        raise DriverError(
            "ICG_COMPILER_EXECUTABLE", f"Compiler is not executable: {value}"
        )
    # Preserve argv[0], including a driver's C++ symlink name.
    return str(Path(found).absolute())


def run_probe(compiler, flags, env):
    command = [compiler, *flags]
    try:
        result = subprocess.run(
            command, input="", text=True, capture_output=True, env=env, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as error:
        raise DriverError(
            "ICG_COMPILER_PROBE", f"Compiler probe failed: {error}"
        ) from error
    if result.returncode:
        raise DriverError(
            "ICG_COMPILER_PROBE",
            f"Compiler probe exited {result.returncode}: {result.stderr}",
        )
    return result


def probe(compiler, flags, *, env=None):
    explicit = arguments(flags)  # Validate before running the selected program.
    env = dict(os.environ if env is None else env)
    compiler = executable(compiler, env)
    env["LC_ALL"] = "C"
    commands = [
        ["-dumpfullversion", "-dumpversion"],
        ["-dumpmachine"],
        ["--version"],
        [
            *(flag for flag in flags if flag.startswith("-std=")),
            "-dM",
            "-E",
            "-x",
            "c++",
            "-",
        ],
        [*flags, "-dM", "-E", "-x", "c++", "-"],
    ]
    results = [run_probe(compiler, command, env) for command in commands]
    version, target, display, predefined, definitions = [
        r.stdout.strip() for r in results
    ]
    if not re.fullmatch(r"[1-9][0-9]?\.(?:0|[1-9][0-9]?)\.(?:0|[1-9][0-9]?)", version):
        raise DriverError(
            "ICG_COMPILER_VERSION", f"Expected a complete GCC version, got: {version!r}"
        )
    if tuple(map(int, version.split("."))) < (8, 5, 0):
        raise DriverError(
            "ICG_COMPILER_VERSION", f"GCC 8.5 or newer is required: {version}"
        )
    if not re.fullmatch(r"[A-Za-z0-9_]+(?:-[A-Za-z0-9_.]+)+", target):
        raise DriverError("ICG_COMPILER_TARGET", f"Invalid GCC target: {target!r}")
    macros = dict(re.findall(r"^#define (\w+) (.*)$", predefined, re.MULTILINE))
    if "__clang__" in macros or not all(
        name in macros for name in ("__GNUC__", "__GNUC_MINOR__", "__GNUC_PATCHLEVEL__")
    ):
        raise DriverError(
            "ICG_COMPILER_FAMILY",
            "This adapter requires GCC; Clang/AppleClang are not supported",
        )
    observed = ".".join(
        macros[name] for name in ("__GNUC__", "__GNUC_MINOR__", "__GNUC_PATCHLEVEL__")
    )
    if observed != version:
        raise DriverError(
            "ICG_COMPILER_MACROS",
            f"GCC version {version} disagrees with effective macros {observed}",
        )
    effective = dict(re.findall(r"^#define (\w+) (.*)$", definitions, re.MULTILINE))
    if any(macros.get(name) != effective.get(name) for name in RESERVED):
        raise DriverError(
            "ICG_COMPILER_MACROS",
            "Build flags or forced includes changed compiler identity/dialect macros",
        )
    if macros.get("__cplusplus") != "201703L" or macros.get("__STRICT_ANSI__") not in (
        None,
        "1",
    ):
        raise DriverError(
            "ICG_COMPILER_DIALECT",
            "Effective GCC mode is outside C++17; select -std=c++17 or -std=gnu++17 in the build",
        )
    dialect = "c++17" if "__STRICT_ANSI__" in macros else "gnu++17"
    if explicit is not None and explicit != dialect:
        raise DriverError(
            "ICG_COMPILER_DIALECT",
            "Effective GCC macros disagree with the requested dialect",
        )
    normalized = [f"--target={target}", *flags]
    if explicit is None:
        normalized.append(f"-std={dialect}")
    normalized.append(f"-fgnuc-version={version}")
    with open(compiler, "rb") as stream:
        binary_digest = hashlib.file_digest(stream, "sha256").hexdigest()
    profile = {
        "adapter_version": 1,
        "family": "gcc",
        "executable": compiler,
        "real_path": str(Path(compiler).resolve()),
        "executable_digest": binary_digest,
        "version": version,
        "version_output": display,
        "target": target,
        "arguments": list(flags),
        "normalized_arguments": normalized,
        "language_standard": dialect,
        "dialect_source": "explicit" if explicit else "compiler-default",
        "macro_digest": hashlib.sha256(results[-1].stdout.encode()).hexdigest(),
        "probe_arguments": commands,
        "probe_stderr": [r.stderr for r in results],
        "environment": {
            k: env[k]
            for k in (
                "LC_ALL",
                "PATH",
                "CPATH",
                "CPLUS_INCLUDE_PATH",
                "C_INCLUDE_PATH",
                "GCC_EXEC_PREFIX",
                "COMPILER_PATH",
                "LIBRARY_PATH",
                "SDKROOT",
                "MACOSX_DEPLOYMENT_TARGET",
            )
            if k in env
        },
    }
    return profile, env


def extract(
    extractor,
    compiler,
    header,
    flags=(),
    *,
    source_root=None,
    path_roots=(),
    select_files=(),
    env=None,
):
    profile, env = probe(compiler, list(flags), env=env)
    command = [
        str(extractor),
        "--diagnostics-format=json",
        "--source-root",
        str(source_root or Path.cwd()),
    ]
    for root in path_roots:
        command.extend(("--path-root", str(root)))
    for selected in select_files:
        command.extend(("--select-file", str(selected)))
    command.extend((
        str(Path(header).absolute()),
        "--",
        *profile["normalized_arguments"],
    ))
    result = subprocess.run(
        command, capture_output=True, text=True, env=env, timeout=120
    )
    report = json.loads(result.stderr)
    if result.returncode:
        if result.stdout:
            raise DriverError(
                "ICG_EXTRACTOR_PROTOCOL", "Failed extractor published partial facts"
            )
        return None, report, result.returncode
    document = json.loads(result.stdout)
    schema = json.loads(SCHEMA.read_text())
    ir.validate(schema, document)
    if (
        document["provenance"]["language_standard"] != profile["language_standard"]
        or document["provenance"]["gcc_compatibility_version"] != profile["version"]
    ):
        raise DriverError(
            "ICG_COMPILER_CONDITIONS",
            "Extractor did not honor the selected GCC parse conditions",
        )
    document["provenance"]["build_compiler"] = profile
    for stderr in profile["probe_stderr"]:
        if stderr:
            diagnostic = {
                "severity": "warning",
                "code": "ICG_COMPILER_PROBE_OUTPUT",
                "message": stderr.rstrip(),
                "source": None,
            }
            document["diagnostics"].append(diagnostic)
            report["diagnostics"].append(diagnostic)
    document["provenance"].pop("input_digest")
    document["provenance"]["input_digest"] = hashlib.sha256(
        json.dumps(
            document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    ir.validate(schema, document)
    return document, report, 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extractor", required=True, type=Path)
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--path-root", action="append", default=[])
    parser.add_argument("--select-file", action="append", default=[])
    parser.add_argument("header", type=Path)
    if "--" not in argv:
        parser.error("provide an explicit -- separator before GCC flags")
    separator = argv.index("--")
    args = parser.parse_args(argv[:separator])
    try:
        document, report, status = extract(
            args.extractor,
            args.compiler,
            args.header,
            argv[separator + 1 :],
            source_root=args.source_root,
            path_roots=args.path_root,
            select_files=args.select_file,
        )
    except (
        ValueError,
        OSError,
        subprocess.TimeoutExpired,
        ir.ValidationError,
        ir.SchemaError,
    ) as error:
        document, status = None, 2
        report = {
            "schema_version": 3,
            "document_kind": "trick.icg.diagnostics",
            "files": [],
            "diagnostics": [
                {
                    "severity": "error",
                    "code": getattr(error, "code", "ICG_DRIVER_FAILED"),
                    "message": str(error),
                    "source": None,
                }
            ],
        }
    print(json.dumps(report, sort_keys=True), file=sys.stderr)
    if document is not None:
        print(
            json.dumps(
                document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
        )
    return status


if __name__ == "__main__":
    sys.exit(main())
