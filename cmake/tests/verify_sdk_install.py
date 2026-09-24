"""Install and exercise the core SDK with its producer trees inaccessible.

Run after other build-tree tests, never concurrently with a build. The producer
paths are restored in finally blocks, including after failed subprocesses.
"""

import argparse
import contextlib
import os
import signal
import subprocess
from pathlib import Path


def run(command, cwd, env=None, success=True):
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    with (cwd / "install-validation.log").open("a") as log:
        log.write("$ " + " ".join(map(str, command)) + "\n")
        log.write(result.stdout + result.stderr)
    if (result.returncode == 0) != success:
        raise RuntimeError(
            f"Unexpected exit {result.returncode}: {command}\n{result.stdout}{result.stderr}"
        )
    return result


@contextlib.contextmanager
def hidden(paths):
    moved = []
    try:
        for path in paths:
            destination = path.with_name(path.name + f".sdk-hidden-{os.getpid()}")
            if destination.exists():
                raise RuntimeError(f"Refusing to overwrite {destination}")
            path.rename(destination)
            moved.append((path, destination))
        yield
    finally:
        for path, destination in reversed(moved):
            destination.rename(path)


def terminate(signum, frame):
    # Raise through the context manager so SIGTERM restores renamed trees.
    raise SystemExit(128 + signum)


def validate(args):
    source, build, work = (p.resolve() for p in (args.source, args.build, args.work))
    if source in build.parents or build in source.parents:
        raise RuntimeError(
            "Use independent source/build directories for isolation tests"
        )
    if (
        work == source
        or work == build
        or source in work.parents
        or build in work.parents
    ):
        raise RuntimeError("Validation work must be outside source/build")
    work.mkdir(parents=True, exist_ok=True)
    cache = (build / "CMakeCache.txt").read_text()
    original_libdir = next(
        line.split("=", 1)[1]
        for line in cache.splitlines()
        if line.startswith("CMAKE_INSTALL_LIBDIR:PATH=")
    )
    cmake = str(Path(args.cmake).resolve()) if "/" in args.cmake else args.cmake
    env = os.environ.copy()
    for name in (
        "TRICK_HOME",
        "TRICK_PYTHON_PATH",
        "PYTHONPATH",
        "MAKEFLAGS",
        "DESTDIR",
    ):
        env.pop(name, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    hints = work / "package-consumer-hints.cmake"
    hints.write_text((build / "package-consumer-hints.cmake").read_text())
    try:
        for libdir in ("lib", "lib64"):
            run(
                [
                    cmake,
                    "-S",
                    str(source),
                    "-B",
                    str(build),
                    f"-DCMAKE_INSTALL_LIBDIR={libdir}",
                ],
                work,
                env,
            )
            run(
                [
                    cmake,
                    "--build",
                    str(build),
                    "--config",
                    args.config,
                    "--target",
                    "trick_sdk",
                    "--parallel",
                    "3",
                ],
                work,
                env,
            )
            stage = work / ("destdir-" + libdir)
            stage.mkdir(exist_ok=True)
            stage_env = dict(env, DESTDIR=str(stage))
            run(
                [
                    cmake,
                    "--install",
                    str(build),
                    "--config",
                    args.config,
                    "--prefix",
                    "/opt/trick-sdk",
                ],
                work,
                stage_env,
            )
            installed = stage / "opt/trick-sdk"
            # A normal nondefault prefix uses the same native install rules.
            direct = work / ("direct-" + libdir)
            run(
                [
                    cmake,
                    "--install",
                    str(build),
                    "--config",
                    args.config,
                    "--prefix",
                    str(direct),
                ],
                work,
                env,
            )
            blocked = work / ("not-a-directory-" + libdir)
            blocked.write_text("install must not replace this file\n")
            run(
                [
                    cmake,
                    "--install",
                    str(build),
                    "--config",
                    args.config,
                    "--prefix",
                    str(blocked),
                ],
                work,
                env,
                success=False,
            )
            if hasattr(os, "geteuid") and os.geteuid() != 0:
                unwritable = work / ("unwritable-" + libdir)
                unwritable.mkdir(exist_ok=True)
                unwritable.chmod(0o555)
                try:
                    run(
                        [
                            cmake,
                            "--install",
                            str(build),
                            "--config",
                            args.config,
                            "--prefix",
                            str(unwritable),
                        ],
                        work,
                        env,
                        success=False,
                    )
                finally:
                    unwritable.chmod(0o755)
            moved = work / ("relocated-" + libdir)
            if moved.exists():
                raise RuntimeError(f"Use a fresh work directory: {moved}")
            installed.rename(moved)
            readme = moved / "share/trick/trickops/README.md"
            if (
                readme.is_symlink()
                or readme.read_bytes()
                != (
                    source / "docs/documentation/miscellaneous_trick_tools/TrickOps.md"
                ).read_bytes()
            ):
                raise RuntimeError("Installed resource symlink was not materialized")
            if (moved / "include/er7_utils").exists():
                raise RuntimeError(
                    "Duplicate ER7 headers can mask a missing trick_source include interface"
                )
            # Scan configuration text, not debug strings in native binaries.
            configs = list(moved.rglob("*.cmake")) + list(moved.rglob("*.mk"))
            configs.append(moved / "share/trick/sdk.env")
            for config in configs:
                text = config.read_text()
                if str(source) in text or str(build) in text:
                    raise RuntimeError(
                        f"Installed configuration leaks a producer path: {config}"
                    )
            for suffix in (" space", "#hash", "$dollar"):
                invalid = work / ("invalid-" + libdir + suffix)
                moved.rename(invalid)
                try:
                    result = run(
                        [str(invalid / "bin/trick-gte"), "TRICK_HOME"],
                        work,
                        env,
                        success=False,
                    )
                    if "SDK paths must not contain" not in result.stderr:
                        raise RuntimeError("Missing SDK path diagnostic")
                finally:
                    invalid.rename(moved)
            marker = moved / "share/trick/sdk.env"
            marker.rename(marker.with_suffix(".hidden"))
            try:
                header = work / "MissingMarker.hh"
                header.write_text("struct MissingMarker { int value; };\n")
                result = run(
                    [str(moved / "bin/trick-ICG"), str(header)],
                    work,
                    env,
                    success=False,
                )
                if "Incomplete SDK" not in result.stderr:
                    raise RuntimeError("Missing SDK marker diagnostic")
            finally:
                marker.with_suffix(".hidden").rename(marker)
            with hidden((source, build)):
                for sdk, name in ((direct, "direct"), (moved, "relocated")):
                    if not (sdk / libdir / "libtrick.a").is_file():
                        raise RuntimeError(f"Missing archive under {libdir}")
                    run(
                        [
                            cmake,
                            f"-DSDK={sdk}",
                            f"-DFIXTURE={sdk}/share/trick/examples/SIM_sdk",
                            f"-DTEST_ROOT={work}/{name}-simulation-{libdir}",
                            "-P",
                            str(sdk / "share/trick/tests/SDK.cmake"),
                        ],
                        work,
                        env,
                    )
                run(
                    [
                        cmake,
                        f"-DPACKAGE_ROOT={moved}/{libdir}/cmake/Trick",
                        f"-DCONSUMER={moved}/share/trick/examples/consumer",
                        f"-DTEST_ROOT={work}/package-{libdir}",
                        f"-DHINTS={hints}",
                        f"-DFORBIDDEN_SOURCE={source}",
                        f"-DFORBIDDEN_BUILD={build}",
                        "-P",
                        str(moved / "share/trick/tests/Package.cmake"),
                    ],
                    work,
                    env,
                )
                # Standalone installed ICG must discover its SDK without TRICK_HOME.
                header = work / "Standalone.hh"
                header.write_text(
                    '#include "trick/SimObject.hh"\nstruct InstalledModel { int value; };\n'
                )
                run(
                    [str(moved / "bin/trick-ICG"), f"-I{moved}/include", str(header)],
                    work,
                    env,
                )
                trickified = work / ("trickified-" + libdir)
                trickified.mkdir()
                (trickified / "Model.hh").write_text(
                    "struct SDKTrickified { double value; };\n"
                )
                (trickified / "S_source.hh").write_text('#include "Model.hh"\n')
                run(
                    [
                        "make",
                        "-f",
                        str(moved / "share/trick/makefiles/trickify.mk"),
                        "TRICKIFY_CXX_FLAGS=-I.",
                    ],
                    trickified,
                    dict(env, TRICK_HOME=str(moved)),
                )
                if (
                    not (trickified / "trickified.o").is_file()
                    or not (trickified / "python").is_file()
                ):
                    raise RuntimeError(
                        "Trickification did not produce its object and Python archive"
                    )
    finally:
        run(
            [
                cmake,
                "-S",
                str(source),
                "-B",
                str(build),
                f"-DCMAKE_INSTALL_LIBDIR={original_libdir}",
            ],
            work,
            env,
        )
        run(
            [
                cmake,
                "--build",
                str(build),
                "--config",
                args.config,
                "--target",
                "trick_sdk",
                "--parallel",
                "3",
            ],
            work,
            env,
        )
    print(
        "Installed SDK passed: lib/lib64, direct/DESTDIR, relocation, hidden producers, simulation and trickification"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument("--config", default="Release")
    signal.signal(signal.SIGTERM, terminate)
    validate(parser.parse_args())
